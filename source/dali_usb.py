import errno
import logging
import queue
import struct
import threading
import time

import usb
import DALI

logger = logging.getLogger(__name__)

DALI_USB_VENDOR = 0x17b5
DALI_USB_PRODUCT = 0x0020

DALI_USB_DIRECTION_FROM_DALI = 0x11
DALI_USB_DIRECTION_TO_DALI = 0x12
DALI_USB_TYPE_NO = 0x01
DALI_USB_TYPE_8BIT = 0x02
DALI_USB_TYPE_16BIT = 0x03
DALI_USB_TYPE_25BIT = 0x04
DALI_USB_TYPE_24BIT = 0x06
DALI_USB_TYPE_STATUS = 0x07
DALI_USB_RECEIVE_MASK = 0x70


class DALI_Usb:
    def __init__(self, vendor=DALI_USB_VENDOR, product=DALI_USB_PRODUCT):
        # lookup devices by vendor and DALI_USB_PRODUCT
        self.interface = 0
        self.queue = queue.Queue(maxsize=40)
        self.worker_running = False
        self.message_counter = 1

        logger.debug("Try to discover DALI interfaces")
        devices = [dev for dev in usb.core.find(
            find_all=True,
            idVendor=vendor,
            idProduct=product
        )]

        logger.info(F"DALI interfaces found: {devices}")

        # if not found
        if not devices:
            raise usb.core.USBError("DALI interface not found")

        # use first device from list
        self.device = devices[0]
        self.device.reset()

        # detach kernel driver if necessary
        if self.device.is_kernel_driver_active(self.interface) is True:
            self.device.detach_kernel_driver(self.interface)

        # set device configuration
        self.device.set_configuration()

        # claim interface
        usb.util.claim_interface(self.device, self.interface)

        # get active configuration
        cfg = self.device.get_active_configuration()
        intf = cfg[(0, 0)]

        # get read and write endpoints
        self.ep_write = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )

        self.ep_read = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
        )

        if not self.ep_read or not self.ep_write:
            raise usb.core.USBError(F"Could not determine read or write endpoint on {self.device}")

        # read pending messages and disregard
        try:
            while True:
                self.ep_read.read(self.ep_read.wMaxPacketSize, timeout=10)
                logger.info("DALI interface - disregard pending messages")
        except Exception:
            pass

    def read_raw(self, timeout=None):
        """Read data from USB device.
        """
        return self.ep_read.read(self.ep_read.wMaxPacketSize, timeout=timeout)

    def write(self, cmd):
        """ Write data to DALI bus.
            cmd : tupel of bytes to send
            
            Data expected by DALI USB
            dr sn ?? ty ?? ec ad oc.. .. .. .. .. .. .. ..
            12 xx 00 03 00 00 ff 08 00 00 00 00 00 00 00 00

            dr: direction
                0x12 = USB side
            sn: sequence number
            ec: eCommand
            ad: address
            oc: opcode
        """
        dr = DALI_USB_DIRECTION_TO_DALI
        sn = self.message_counter
        self.message_counter = (self.message_counter + 1) & 0xff
        if len(cmd) == 3:
            ec = cmd[0]
            ad = cmd[1]
            oc = cmd[2]
            ty = DALI_USB_TYPE_24BIT
        elif len(cmd) == 2:
            ec = 0x00
            ad = cmd[0]
            oc = cmd[1]
            ty = DALI_USB_TYPE_16BIT
        elif len(cmd) == 1:
            ec = 0x00
            ad = 0x00
            oc = cmd[0]
            ty = DALI_USB_TYPE_8BIT
        else:
            raise Exception(F"DALI commands must be 1-3 bytes long but {cmd} is {len(cmd)} bytes long")

        data = struct.pack("BBxBxBBB" + (64 - 8) * 'x', dr, sn, ty, ec, ad, oc)

        logger.debug(F"DALI[OUT]: SN=0x{sn:02X} TY=0x{ty:02X} EC=0x{ec:02X} AD=0x{ad:02X} OC=0x{oc:02X}")

        return self.ep_write.write(data)

    def close(self):
        """Close connection to USB device.
        """
        self.worker_running = False
        usb.util.dispose_resources(self.device)

    def read_worker_thread(self):
        logger.debug("read_worker_thread() started")
        raw = DALI.Raw_Frame()
        while self.worker_running:
            try:
                data = self.read_raw(timeout=200)
                """ raw data received from DALI USB:
                dr ty ?? ec ad cm st st sn .. .. .. .. .. .. ..
                11 73 00 00 ff 93 ff ff 00 00 00 00 00 00 00 00

                dr: [0]: direction
                    0x11 = DALI side
                    0x12 = USB side
                ty: [1]: type
                ec: [2]: ecommand
                ad: [3]: address
                cm: [4] command
                    also serves as response code for 72
                st: [5] status
                    internal status code, value unknown
                sn: [6] seqnum
                """
                if data:
                    if data[0] == DALI_USB_DIRECTION_FROM_DALI:
                        logger.debug(F"DALI[IN]: SN=0x{data[8]:02X} TY=0x{data[1]:02X} EC=0x{data[3]:02X} AD=0x{data[4]:02X} OC=0x{data[5]:02X}")
                        raw.type = raw.COMMAND
                        raw.timestamp = time.time()
                        if data[1] == (DALI_USB_RECEIVE_MASK + DALI_USB_TYPE_8BIT):
                            raw.length = 8
                            raw.data = data[5]
                        elif data[1] == (DALI_USB_RECEIVE_MASK + DALI_USB_TYPE_16BIT):
                            raw.length = 16
                            raw.data = data[5] + (data[4]<<8)
                        elif data[1] == (DALI_USB_RECEIVE_MASK + DALI_USB_TYPE_24BIT):
                            raw.length = 24
                            raw.data = data[5] + (data[4]<<8) + (data[3]<<16)
                        elif data[1] == (DALI_USB_RECEIVE_MASK + DALI_USB_TYPE_STATUS):
                            raw.type = raw.ERROR
                            raw.data = 0
                            if data[5] == 0x04:
                                raw.length = DALI.DALIError.RECOVER
                            elif data[5] == 0x03:
                                raw.length = DALI.DALIError.FRAME
                            else:
                                raw.length = DALI.DALIError.GENERAL
                        self.queue.put(raw)

                    if data[0] == DALI_USB_DIRECTION_TO_DALI:
                        logger.debug(F"DALI[OUT]: SN=0x{data[8]:02X} TY=0x{data[1]:02X} EC=0x{data[3]:02X} AD=0x{data[4]:02X} OC=0x{data[5]:02X}")

            except usb.USBError as e:
                if e.errno not in (errno.ETIMEDOUT, errno.ENODEV):
                    raise e

    def start_read(self):
        logger.debug("Start read")
        self.worker_running = True
        thread = threading.Thread(target=self.read_worker_thread, args=())
        thread.daemon = True
        thread.start()


    def read_raw_frame(self):
        return self.queue.get(block=True)


    def clear_buffers(self):
        while not self.queue.empty():
            self.queue.get(block=False)

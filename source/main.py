import getopt
import sys
import logging
from datetime import datetime

from termcolor import cprint

import DALI
import dali_serial
import dali_usb


def print_local_time_color(enabled):
    if enabled:
        time_string = datetime.now().strftime("%H:%M:%S")
        cprint(F"{time_string} | ", color="yellow", end="")


def print_local_time(enabled):
    if enabled:
        time_string = datetime.now().strftime("%H:%M:%S")
        print(F"{time_string} | ", end="")


def print_command_color(absolute_time, timestamp, delta, dali_command):
    print_local_time_color(absolute_time)
    cprint(F"{timestamp:.03f} | {delta:8.03f} | {dali_command} | ", color="green", end="")
    cprint(F"{dali_command.cmd()}", color="white")


def print_command(absolute_time, timestamp, delta, dali_command):
    print_local_time(absolute_time)
    print(F"{timestamp:.03f} | {delta:8.03f} | {dali_command} | {dali_command.cmd()}")


def print_error_color(absolute_time, raw, delta):
    print_local_time_color(absolute_time)
    cprint(F"{raw.timestamp:.03f} | {delta:8.03f} | ", color="green", end="")
    cprint(F"{DALI.DALIError(raw.length, raw.data)}", color="red")


def print_error(absolute_time, raw, delta):
    print_local_time(absolute_time)
    print(F"{raw.timestamp:.03f} | {delta:8.03f} | {DALI.DALIError(raw.length, raw.data)}")


def main(source, use_color, absolute_time):
    last_timestamp = 0
    delta = 0
    active_device_type = DALI.DeviceType.NONE
    source.start_read()
    while True:
        raw = source.read_raw_frame()
        if not raw.type == raw.INVALID:
            if last_timestamp != 0:
                delta = raw.timestamp - last_timestamp
            if raw.type == raw.COMMAND:
                dali_command = DALI.Decode(raw, active_device_type)
                if use_color:
                    print_command_color(absolute_time, raw.timestamp, delta, dali_command)
                else:
                    print_command(absolute_time, raw.timestamp, delta, dali_command)
                active_device_type = dali_command.get_next_device_type()
            else:
                if use_color:
                    print_error_color(absolute_time, raw, delta)
                else:
                    print_error(absolute_time, raw, delta)
            last_timestamp = raw.timestamp


def show_version():
    print("dali_py version 1.0.8 - SevenLab 2022")


def show_help():
    show_version()
    print("usage: -h : help")
    print("       --help")
    print("       --port, -p <port> : use serial port")
    print("       --version, -v : show version information")
    print("       --nocolor : don\"t use colors")
    print("       --absolute : add stamp with absolute time")
    print("       --transparent : print all input lines")
    print("       --lunatone, -l : use lunatone usb interface")
    print("       --debug : set messages to debug level")
    print("output colums:")
    print("       if enabled: absolute timestamp (from this machine)")
    print("       relative timestamp in seconds (from interface)")
    print("       delta time to previous command")
    print("       hex data received")
    print("       DALI command translation")


# - - - - - - - - - - - - - - - - - - - -
if __name__ == "__main__":
    serial_port = None
    color = True
    absolute_time = False
    transparent = False
    source_is_usb = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hpvl:", [
                                   "help", "port=", "version", "lunatone", "nocolor", "absolute", "transparent", "debug"])
    except getopt.GetoptError:
        show_help()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            show_help()
            sys.exit()
        if opt in ("-p", "--port"):
            serial_port = arg
        if opt in ("-l", "--lunatone"):
            source_is_usb = True
        if opt in ("-v", "--version"):
            show_version()
        if opt == "--nocolor":
            color = False
        if opt == "--absolute":
            absolute_time = True
        if opt == "--transparent":
            transparent = True
        if opt == "--debug":
            logging.basicConfig(level=logging.DEBUG)

    my_source = None
    if serial_port and not source_is_usb:
        my_source = dali_serial.DALI_Serial(port=serial_port,transparent=transparent)

    if source_is_usb and not serial_port:
        my_source = dali_usb.DALI_Usb()

    if my_source == None:
        print ("illegal source settings")
        sys.exit(2)

    try:
        main(my_source, color, absolute_time)
    except KeyboardInterrupt:
        print("\rinterrupted")
        my_source.close()
        sys.exit(0)


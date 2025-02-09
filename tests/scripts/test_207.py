import pytest
import os
import sys
# locate the DALI module
here = os.path.dirname(__file__)
sys.path.append(os.path.join(here, '../../source'))

import DALI

# refer to iec62386 207 Table 6
@pytest.mark.parametrize("name,opcode",
    [("REFERENCE SYSTEM POWER", 0xE0),
     ("SELECT DIMMING CURVE (DTR0)", 0xE3),
     ("SET FAST FADE TIME (DTR0)", 0xE4),
     ("QUERY CONTROL GEAR TYPE", 0xED),
     ("QUERY DIMMING CURVE", 0xEE),
     ("QUERY FEATURES", 0xF0),
     ("QUERY LOAD DECREASE", 0xF4),
     ("QUERY LOAD INCREASE", 0xF5),
     ("QUERY THERMAL SHUTDOWN", 0xF7),
     ("QUERY THERMAL OVERLOAD", 0xF8),
     ("QUERY REFERENCE RUNNING", 0xF9),
     ("QUERY REFERENCE MEASUREMENT FAILED", 0xFA),
     ("QUERY FAST FADE TIME", 0xFD),
     ("QUERY MIN FAST FADE TIME", 0xFE),
     ("QUERY EXTENDED VERSION NUMBER", 0xFF)
    ]
)
def test_dt6_command(name,opcode):
    frame = DALI.Raw_Frame()
    frame.length = 16
    # broadcast
    frame.data = 0xFF00 + opcode
    decoded_command = DALI.Decode(frame, DALI.DeviceType.LED)
    target_command = "BC".ljust(10) + name
    assert decoded_command.cmd() == target_command
    # broadcast unadressed
    frame.data = 0xFD00 + opcode
    decoded_command = DALI.Decode(frame, DALI.DeviceType.LED)
    target_command = "BC unadr.".ljust(10) + name
    assert decoded_command.cmd() == target_command
    # short address
    for short_address in range (0,0x40):
        frame.data = 0x0100 + (short_address << 9) + opcode
        decoded_command = DALI.Decode(frame, DALI.DeviceType.LED)
        target_command = F"A{short_address:02}".ljust(10) + name
        assert decoded_command.cmd() == target_command
    # group address
    for group_address in range (0,0x10):
        frame.data = 0x8100 + (group_address << 9) + opcode
        decoded_command = DALI.Decode(frame, DALI.DeviceType.LED)
        target_command = F"G{group_address:02}".ljust(10) + name
        assert decoded_command.cmd() == target_command

@pytest.mark.parametrize("opcode",[
    0xE1,0xE2,0xE5,0xE6,0xE7,0xE8,0xE9,0xEA,0xEB,0xEC,0xEF,
    0xF2,0xF3,0xF6,0xFB,0xFC])
def test_dt6_undefined_codes(opcode):
    frame = DALI.Raw_Frame()
    frame.length = 16
    # broadcast
    frame.data = 0xFF00 + opcode
    decoded_command = DALI.Decode(frame, DALI.DeviceType.LED)
    target_command = "BC".ljust(10) + "---"
    assert decoded_command.cmd()[:len(target_command)] == target_command
    # broadcast unadressed
    frame.data = 0xFD00 + opcode
    decoded_command = DALI.Decode(frame, DALI.DeviceType.LED)
    target_command = "BC unadr.".ljust(10) + "---"
    assert decoded_command.cmd()[:len(target_command)] == target_command
    # short address
    for short_address in range (0,0x40):
        frame.data = 0x0100 + (short_address << 9) + opcode
        decoded_command = DALI.Decode(frame, DALI.DeviceType.LED)
        target_command = F"A{short_address:02}".ljust(10) + "---"
        assert decoded_command.cmd()[:len(target_command)] == target_command
    # group address
    for group_address in range (0,0x10):
        frame.data = 0x8100 + (group_address << 9) + opcode
        decoded_command = DALI.Decode(frame, DALI.DeviceType.LED)
        target_command = F"G{group_address:02}".ljust(10) + "---"
        assert decoded_command.cmd()[:len(target_command)] == target_command


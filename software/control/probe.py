#!/usr/bin/env python3
"""TEMP diagnostic. Read-only commands. Nothing moves."""
import serial, time

PORT = "/dev/ttyACM0"

def probe(ser, cmd, wait=2.0):
    ser.reset_input_buffer()
    ser.write((cmd + "\r\n").encode())
    deadline, buf = time.time() + wait, b""
    while time.time() < deadline:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
        else:
            time.sleep(0.05)
    print(f"=== {cmd} ===")
    print(buf.decode("utf-8", "replace") or "(no reply)")
    print()

ser = serial.Serial(PORT, 115200, timeout=1)
time.sleep(2)
ser.reset_input_buffer()

probe(ser, "M114")   # raw position text
probe(ser, "M400")   # does it reply ok, or unknown command?
probe(ser, "M92")    # steps per unit, incl. E (the rail)
probe(ser, "M2101")  # rotary current angle
probe(ser, "M2103")  # rotary firmware version
probe(ser, "M888")   # current end effector module
probe(ser, "M503", wait=4.0)  # full settings dump
ser.close()
#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Early blanker script for Turing Smart Screen 3.5"
# Executes at early system boot via LaunchDaemon to eliminate uninitialized white screen.

import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    import serial
    from serial.tools.list_ports import comports
except ImportError:
    sys.exit(1)


def find_turing_port():
    """Locate the serial port for Turing Smart Screen 3.5 (CH554 Rev A)."""
    for port in comports():
        if port.vid == 0x1A86 and port.pid == 0x5722:
            return port.device
        if port.serial_number and "USB35INCHIPSV2" in port.serial_number:
            return port.device

    # Fallback to direct device node if available
    fallback_nodes = [
        "/dev/cu.usbmodemUSB35INCHIPSV21",
        "/dev/cu.wchusbserial",
    ]
    for node in fallback_nodes:
        if os.path.exists(node):
            return node

    return None


def send_command(ser, cmd, x=0, y=0, ex=0, ey=0):
    """Format and transmit a standard 6-byte Revision A command."""
    buf = bytearray(6)
    buf[0] = (x >> 2) & 0xFF
    buf[1] = (((x & 3) << 6) + (y >> 4)) & 0xFF
    buf[2] = (((y & 15) << 4) + (ex >> 6)) & 0xFF
    buf[3] = (((ex & 63) << 2) + (ey >> 8)) & 0xFF
    buf[4] = ey & 0xFF
    buf[5] = cmd & 0xFF
    ser.write(buf)


def blank_display(port_name):
    """Open serial port, blank panel, extinguish backlight, and close."""
    ser = serial.Serial(
        port=port_name,
        baudrate=115200,
        timeout=1,
        write_timeout=1,
        rtscts=True
    )
    try:
        # Command 103: TO_BLACK (clears GRAM to black)
        send_command(ser, cmd=103, x=0, y=0, ex=0, ey=0)

        # Command 110: SET_BRIGHTNESS(0) -> absolute level 255 (darkest/off)
        send_command(ser, cmd=110, x=255, y=0, ex=0, ey=0)

        # Command 108: SCREEN_OFF (enters display sleep mode)
        send_command(ser, cmd=108, x=0, y=0, ex=0, ey=0)

        ser.flush()
        time.sleep(0.05)
    finally:
        ser.close()


def main():
    # Retry loop waiting for macOS IOKit USB CDC/ACM driver to register device node at boot
    max_wait_seconds = 15
    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        port = find_turing_port()
        if port:
            try:
                blank_display(port)
                print(f"Successfully blanked display on {port}")
                return 0
            except Exception as e:
                # If port exists but is temporarily busy or not ready, retry briefly
                print(f"Waiting for {port} to be available: {e}")
                time.sleep(0.5)
        else:
            time.sleep(0.5)

    print("Turing display not found within timeout window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

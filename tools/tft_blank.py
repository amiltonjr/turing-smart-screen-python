#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
tft_blank.py - Early display blanker for Turing Smart Screen 3.5" (Revision A).

Transmits hardware commands to extinguish the panel and backlight as early as possible
during system boot, eliminating the default uninitialized white screen before the main
monitoring service takes over.
"""

import sys
import time
from typing import Optional
import serial
from serial.tools.list_ports import comports


def find_com_port() -> Optional[str]:
    """Scan connected serial devices for Turing Smart Screen Revision A."""
    for port in comports():
        if port.serial_number == "USB35INCHIPSV2":
            return port.device
        if port.vid == 0x1A86 and port.pid == 0x5722:
            return port.device
    return "COM3"


def blank_display(port: Optional[str] = None) -> bool:
    """Send TO_BLACK, SET_BRIGHTNESS(0), and SCREEN_OFF commands to the display."""
    target_port = port or find_com_port()
    if not target_port:
        return False

    try:
        ser = serial.Serial(target_port, 115200, timeout=1, rtscts=True)

        # 1. TO_BLACK (103): Fills ST7796S GRAM with black pixels (0x0000)
        ser.write(bytes([0, 0, 0, 0, 0, 103]))
        time.sleep(0.01)

        # 2. SET_BRIGHTNESS (110): level_absolute = 255 (0% PWM duty cycle / LED off)
        # (255 >> 2) = 63 (0x3F), ((255 & 3) << 6) = 192 (0xC0)
        ser.write(bytes([0x3F, 0xC0, 0, 0, 0, 110]))
        time.sleep(0.01)

        # 3. SCREEN_OFF (108): Places ST7796S into display sleep / power-saving mode
        ser.write(bytes([0, 0, 0, 0, 0, 108]))
        time.sleep(0.01)

        ser.flush()
        ser.close()
        return True
    except Exception as e:
        sys.stderr.write(f"Error blanking display on {target_port}: {e}\n")
        return False


if __name__ == "__main__":
    com_arg = sys.argv[1] if len(sys.argv) > 1 else None
    success = blank_display(com_arg)
    sys.exit(0 if success else 1)

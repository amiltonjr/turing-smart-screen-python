# TftBlank.efi - OpenCore Early UEFI Driver for Turing Smart Screen 3.5"

## Overview
`TftBlank.efi` is a lightweight standalone UEFI 2.x boot service driver designed for OpenCore. It intercepts the boot process before the OpenCore picker is rendered, locates the Turing Smart Screen 3.5" hardware monitor (WCH CH554, VID: `0x1A86`, PID: `0x5722`), and immediately blanks the panel and turns off the backlight.

This eliminates the uninitialized "white screen of death" during machine power-on, UEFI POST, OpenCore boot picker, and macOS kernel loading.

## Hardware & Protocol Architecture
- **Target Microcontroller**: WCH CH554 / CH552 (8051-based USB bridge)
- **USB Identifiers**: VID `0x1A86`, PID `0x5722`
- **Display Controller**: Sitronix ST7796S (320x480 IPS)
- **Protocol**: 6-byte command sequences transmitted via USB Bulk OUT endpoint:
  1. `TO_BLACK` (`[0, 0, 0, 0, 0, 103]`): Fills ST7796S GRAM with black pixels (`0x0000`).
  2. `SET_BRIGHTNESS(0)` (`[63, 192, 0, 0, 0, 110]`): Sets backlight PWM duty cycle to 0 (darkest absolute level 255).
  3. `SCREEN_OFF` (`[0, 0, 0, 0, 0, 108]`): Places ST7796S into display sleep / power saving mode.

## Building from Source
The driver uses freestanding C with zero external runtime dependencies and compiles directly to standard PE32+ (x86_64) UEFI format using LLVM Clang and `lld-link`:

```bash
cd external/OpenCoreDriver
make clean && make
```

## OpenCore Installation
1. Copy `TftBlank.efi` to your EFI partition:
   ```bash
   cp TftBlank.efi /Volumes/EFI/EFI/OC/Drivers/
   ```

2. Register the driver in your `config.plist` under `UEFI -> Drivers`:
   ```xml
   <dict>
       <key>Arguments</key>
       <string></string>
       <key>Comment</key>
       <string>Turing Smart Screen 3.5 early blanker</string>
       <key>Enabled</key>
       <true/>
       <key>HideVerbose</key>
       <false/>
       <key>LoadEarly</key>
       <true/>
       <key>Path</key>
       <string>TftBlank.efi</string>
   </dict>
   ```

> [!NOTE]
> Setting `LoadEarly` to `true` ensures that OpenCore invokes `TftBlank.efi` at the earliest stage before graphics or picker drivers are initialized.

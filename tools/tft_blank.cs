// SPDX-License-Identifier: GPL-3.0-or-later
// Early display blanker for Turing Smart Screen 3.5" (Revision A) on Windows.
// Zero-dependency native executable compiled via standard .NET csc.exe.

using System;
using System.IO.Ports;
using System.Threading;
using Microsoft.Win32;

namespace TftBlank {
    class Program {
        static string FindComPort() {
            try {
                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Enum\USB\VID_1A86&PID_5722")) {
                    if (key != null) {
                        foreach (string subName in key.GetSubKeyNames()) {
                            using (RegistryKey subKey = key.OpenSubKey(subName + @"\Device Parameters")) {
                                if (subKey != null) {
                                    object val = subKey.GetValue("PortName");
                                    if (val != null) {
                                        return val.ToString();
                                    }
                                }
                            }
                        }
                    }
                }
            } catch {}

            try {
                string[] ports = SerialPort.GetPortNames();
                foreach (string p in ports) {
                    if (p.Equals("COM3", StringComparison.OrdinalIgnoreCase)) {
                        return p;
                    }
                }
                if (ports.Length > 0) return ports[0];
            } catch {}

            return "COM3";
        }

        static int Main(string[] args) {
            string portOverride = args.Length > 0 ? args[0] : null;
            DateTime deadline = DateTime.UtcNow.AddSeconds(15);

            while (DateTime.UtcNow < deadline) {
                string portName = portOverride ?? FindComPort();
                try {
                    using (SerialPort sp = new SerialPort(portName, 115200)) {
                        sp.RtsEnable = true;
                        sp.ReadTimeout = 1000;
                        sp.WriteTimeout = 1000;
                        sp.Open();

                        // 1. TO_BLACK (103): Fills frame memory with 0x0000
                        sp.Write(new byte[] { 0, 0, 0, 0, 0, 103 }, 0, 6);
                        Thread.Sleep(15);

                        // 2. SET_BRIGHTNESS (110) level_absolute = 255 (0% duty cycle / LED off)
                        // (255 >> 2) = 63 (0x3F), ((255 & 3) << 6) = 192 (0xC0)
                        sp.Write(new byte[] { 0x3F, 0xC0, 0, 0, 0, 110 }, 0, 6);
                        Thread.Sleep(15);

                        // 3. SCREEN_OFF (108): Display sleep mode
                        sp.Write(new byte[] { 0, 0, 0, 0, 0, 108 }, 0, 6);
                        Thread.Sleep(15);

                        sp.Close();
                        return 0; // Success!
                    }
                } catch {
                    // Port not ready or being enumerated, retry after 200ms
                    Thread.Sleep(200);
                }
            }
            return 1;
        }
    }
}

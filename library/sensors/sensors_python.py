# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# This file will use Python libraries (psutil, GPUtil, etc.) to get hardware sensors
# For all platforms (Linux, Windows, macOS) but not all HW is supported

import math
import platform
import sys
from collections import namedtuple
from enum import IntEnum, auto
from typing import Tuple

# Nvidia GPU
import GPUtil
# CPU & disk sensors
import psutil

import library.sensors.sensors as sensors
from library.log import logger

# AMD GPU on Linux
try:
    import pyamdgpuinfo
except:
    pyamdgpuinfo = None

# AMD GPU on Windows
try:
    import pyadl
except:
    pyadl = None

PNIC_BEFORE = {}

# AppleSMC and Mach VM integration for macOS
_smc_conn = None


def _init_smc():
    global _smc_conn
    if _smc_conn is not None:
        return _smc_conn
    if platform.system() != "Darwin":
        return None
    try:
        import ctypes
        import ctypes.util

        iokit = ctypes.cdll.LoadLibrary(ctypes.util.find_library('IOKit'))
        mach = ctypes.cdll.LoadLibrary(ctypes.util.find_library('System'))

        class SMCVersion(ctypes.Structure):
            _fields_ = [
                ('major', ctypes.c_uint8),
                ('minor', ctypes.c_uint8),
                ('build', ctypes.c_uint8),
                ('reserved', ctypes.c_uint8),
                ('release', ctypes.c_uint16),
            ]

        class SMCPLimitData(ctypes.Structure):
            _fields_ = [
                ('version', ctypes.c_uint16),
                ('length', ctypes.c_uint16),
                ('cpuPLimit', ctypes.c_uint32),
                ('gpuPLimit', ctypes.c_uint32),
                ('memPLimit', ctypes.c_uint32),
            ]

        class SMCKeyInfoData(ctypes.Structure):
            _fields_ = [
                ('dataSize', ctypes.c_uint32),
                ('dataType', ctypes.c_uint32),
                ('dataAttributes', ctypes.c_uint8),
            ]

        class SMCKeyData(ctypes.Structure):
            _fields_ = [
                ('key', ctypes.c_uint32),
                ('vers', SMCVersion),
                ('pLimitData', SMCPLimitData),
                ('keyInfo', SMCKeyInfoData),
                ('result', ctypes.c_uint8),
                ('status', ctypes.c_uint8),
                ('data8', ctypes.c_uint8),
                ('data32', ctypes.c_uint32),
                ('bytes', ctypes.c_uint8 * 32),
            ]

        iokit.IOServiceMatching.restype = ctypes.c_void_p
        iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
        iokit.IOServiceGetMatchingService.restype = ctypes.c_uint32
        iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        iokit.IOServiceOpen.restype = ctypes.c_int32
        iokit.IOServiceOpen.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        iokit.IOConnectCallStructMethod.restype = ctypes.c_int32
        iokit.IOConnectCallStructMethod.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
        ]

        service = iokit.IOServiceGetMatchingService(0, iokit.IOServiceMatching(b'AppleSMC'))
        if service:
            conn = ctypes.c_uint32()
            res = iokit.IOServiceOpen(service, mach.mach_task_self(), 0, ctypes.byref(conn))
            if res == 0:
                _smc_conn = (iokit, conn, SMCKeyData)
                return _smc_conn
    except Exception:
        pass
    return None


def _read_smc_temp(key_str: str) -> float:
    smc = _init_smc()
    if not smc:
        return None
    iokit, conn, SMCKeyData = smc
    try:
        import ctypes
        k_val = 0
        for c in key_str.encode('ascii'):
            k_val = (k_val << 8) | c

        inp = SMCKeyData()
        inp.key = k_val
        inp.data8 = 9  # SMC_CMD_READ_KEYINFO
        out = SMCKeyData()
        sz = ctypes.c_size_t(ctypes.sizeof(SMCKeyData))
        res = iokit.IOConnectCallStructMethod(conn, 2, ctypes.byref(inp), sz, ctypes.byref(out), ctypes.byref(sz))
        if res != 0 or out.result != 0:
            return None

        dsize = out.keyInfo.dataSize
        dtype = out.keyInfo.dataType.to_bytes(4, 'big').decode('ascii', errors='replace')
        inp.data8 = 5  # SMC_CMD_READ_BYTES
        inp.keyInfo.dataSize = dsize
        res = iokit.IOConnectCallStructMethod(conn, 2, ctypes.byref(inp), sz, ctypes.byref(out), ctypes.byref(sz))
        if res == 0 and out.result == 0:
            raw = bytes(out.bytes[:dsize])
            if dtype == 'sp78' and len(raw) >= 2:
                return int.from_bytes(raw[:2], 'big', signed=True) / 256.0
            elif dtype == 'fpe2' and len(raw) >= 2:
                return int.from_bytes(raw[:2], 'big', signed=False) / 4.0
    except Exception:
        pass
    return None


def _get_mac_cpu_temperature() -> float:
    temps = []
    # Package, die, heatsink sensors
    for k in ['TC0P', 'TC0D', 'TC0H', 'TC0p', 'TC0d']:
        v = _read_smc_temp(k)
        if v is not None and 10 < v < 125:
            temps.append(v)
    # Core sensors
    for i in range(32):
        for pat in (f'TC{i}c', f'TC{i}C', f'TC{i:02d}c'):
            v = _read_smc_temp(pat)
            if v is not None and 10 < v < 125:
                temps.append(v)
                break
    if temps:
        return max(temps)
    return math.nan


def is_loopback(nic_name: str) -> bool:
    name_lower = str(nic_name).lower()
    if name_lower.startswith('lo') or 'loopback' in name_lower:
        return True
    try:
        stats = psutil.net_if_stats()
        if nic_name in stats:
            flags = getattr(stats[nic_name], 'flags', '')
            if 'loopback' in str(flags).lower():
                return True
    except:
        pass
    return False


class GpuType(IntEnum):
    UNSUPPORTED = auto()
    AMD = auto()
    NVIDIA = auto()


DETECTED_GPU = GpuType.UNSUPPORTED


# Function inspired of psutil/psutil/_pslinux.py:sensors_fans()
# Adapted to also get fan speed percentage instead of raw value
def sensors_fans():
    """Return hardware fans info (for CPU and other peripherals) as a
    dict including hardware label and current speed.

    Implementation notes:
    - /sys/class/hwmon looks like the most recent interface to
      retrieve this info, and this implementation relies on it
      only (old distros will probably use something else)
    - lm-sensors on Ubuntu 16.04 relies on /sys/class/hwmon
    """
    from psutil._common import bcat, cat
    import collections, glob, os

    ret = collections.defaultdict(list)
    basenames = glob.glob('/sys/class/hwmon/hwmon*/fan*_*')
    if not basenames:
        # CentOS has an intermediate /device directory:
        # https://github.com/giampaolo/psutil/issues/971
        basenames = glob.glob('/sys/class/hwmon/hwmon*/device/fan*_*')

    basenames = sorted(set([x.split('_')[0] for x in basenames]))
    for base in basenames:
        try:
            current_rpm = int(bcat(base + '_input'))

            try:
                max_rpm = int(bcat(base + '_max'))
            except:
                max_rpm = False  # Real maximum speed not found
            if not max_rpm:
                if current_rpm > 2200:
                    max_rpm = 3000  # AIO Pumps are usualy 3000 RPM
                elif current_rpm > 1500:
                    max_rpm = 2200  # High speed fans are usualy 2200 RPM
                else:
                    max_rpm = 1500  # Approximated: max fan speed is 1500 RPM

            try:
                min_rpm = int(bcat(base + '_min'))
            except:
                min_rpm = 0  # Approximated: min fan speed is 0 RPM
            percent = int((current_rpm - min_rpm) / (max_rpm - min_rpm) * 100)
        except (IOError, OSError) as err:
            continue
        unit_name = cat(os.path.join(os.path.dirname(base), 'name')).strip()
        label = cat(base + '_label', fallback=os.path.basename(base)).strip()

        custom_sfan = namedtuple('sfan', ['label', 'current', 'percent'])
        ret[unit_name].append(custom_sfan(label, current_rpm, percent))

    return dict(ret)


def is_cpu_fan(label: str) -> bool:
    return ("cpu" in label.lower()) or ("proc" in label.lower())


class Cpu(sensors.Cpu):
    @staticmethod
    def percentage(interval: float) -> float:
        try:
            mode = "MAX"
            try:
                import library.config as config
                mode = config.CONFIG_DATA.get("config", {}).get("CPU_PERCENTAGE_MODE", "MAX").upper()
            except:
                pass

            if mode == "AVERAGE":
                return psutil.cpu_percent(interval=interval)

            per_cpu = psutil.cpu_percent(interval=interval, percpu=True)
            if per_cpu:
                return max(per_cpu)
            return psutil.cpu_percent(interval=interval)
        except:
            return math.nan

    @staticmethod
    def frequency() -> float:
        try:
            return psutil.cpu_freq().current
        except:
            return math.nan

    @staticmethod
    def load() -> Tuple[float, float, float]:  # 1 / 5 / 15min avg (%):
        try:
            return psutil.getloadavg()
        except:
            return math.nan, math.nan, math.nan

    @staticmethod
    def temperature() -> float:
        cpu_temp = math.nan
        if platform.system() == "Darwin":
            try:
                cpu_temp = _get_mac_cpu_temperature()
                if not math.isnan(cpu_temp) and cpu_temp > 0:
                    return cpu_temp
            except:
                pass

        try:
            sensors_temps = psutil.sensors_temperatures()
            if 'coretemp' in sensors_temps:
                # Intel CPU - take highest core/package temp
                cpu_temp = max(s.current for s in sensors_temps['coretemp'] if s.current is not None)
            elif 'k10temp' in sensors_temps:
                # AMD CPU
                cpu_temp = max(s.current for s in sensors_temps['k10temp'] if s.current is not None)
            elif 'cpu_thermal' in sensors_temps:
                # ARM CPU
                cpu_temp = max(s.current for s in sensors_temps['cpu_thermal'] if s.current is not None)
            elif 'zenpower' in sensors_temps:
                # AMD CPU with zenpower (k10temp is in blacklist)
                cpu_temp = max(s.current for s in sensors_temps['zenpower'] if s.current is not None)
        except:
            pass
        return cpu_temp

    @staticmethod
    def fan_percent(fan_name: str = None) -> float:
        try:
            fans = sensors_fans()
            if fans:
                for name, entries in fans.items():
                    for entry in entries:
                        if fan_name is not None and fan_name == "%s/%s" % (name, entry.label):
                            # Manually selected fan
                            return entry.percent
                        elif is_cpu_fan(entry.label) or is_cpu_fan(name):
                            # Auto-detected fan
                            return entry.percent
        except:
            pass

        return math.nan


class Gpu(sensors.Gpu):
    @staticmethod
    def stats() -> Tuple[
        float, float, float, float, float]:  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.stats()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.stats()
        else:
            return math.nan, math.nan, math.nan, math.nan, math.nan

    @staticmethod
    def fps() -> int:
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.fps()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.fps()
        else:
            return -1

    @staticmethod
    def fan_percent() -> float:
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.fan_percent()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.fan_percent()
        else:
            return math.nan

    @staticmethod
    def frequency() -> float:
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.frequency()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.frequency()
        else:
            return math.nan

    @staticmethod
    def is_available() -> bool:
        global DETECTED_GPU
        # Always use Nvidia GPU if available
        if GpuNvidia.is_available():
            logger.info("Detected Nvidia GPU(s)")
            DETECTED_GPU = GpuType.NVIDIA
        # Otherwise, use the AMD GPU / APU if available
        elif GpuAmd.is_available():
            logger.info("Detected AMD GPU(s)")
            DETECTED_GPU = GpuType.AMD
        else:
            logger.warning("No supported GPU found")
            DETECTED_GPU = GpuType.UNSUPPORTED
            if sys.version_info >= (3, 11) and (platform.system() == "Linux" or platform.system() == "Darwin"):
                logger.warning("If you have an AMD GPU, you may need to install some  libraries manually: see "
                               "https://github.com/mathoudebine/turing-smart-screen-python/wiki/Troubleshooting#linux--macos-no-supported-gpu-found-with-an-amd-gpu-and-python-311")

        return DETECTED_GPU != GpuType.UNSUPPORTED


class GpuNvidia(sensors.Gpu):
    @staticmethod
    def stats() -> Tuple[
        float, float, float, float, float]:  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        # Unlike other sensors, Nvidia GPU with GPUtil pulls in all the stats at once
        nvidia_gpus = GPUtil.getGPUs()

        try:
            memory_used_all = [item.memoryUsed for item in nvidia_gpus]
            memory_used_mb = sum(memory_used_all) / len(memory_used_all)
        except:
            memory_used_mb = math.nan

        try:
            memory_total_all = [item.memoryTotal for item in nvidia_gpus]
            memory_total_mb = sum(memory_total_all) / len(memory_total_all)
        except:
            memory_total_mb = math.nan

        try:
            memory_percentage = (memory_used_mb / memory_total_mb) * 100
        except:
            memory_percentage = math.nan

        try:
            load_all = [item.load for item in nvidia_gpus]
            load = (sum(load_all) / len(load_all)) * 100
        except:
            load = math.nan

        try:
            temperature_all = [item.temperature for item in nvidia_gpus]
            temperature = sum(temperature_all) / len(temperature_all)
        except:
            temperature = math.nan

        return load, memory_percentage, memory_used_mb, memory_total_mb, temperature

    @staticmethod
    def fps() -> int:
        # Not supported by Python libraries
        return -1

    @staticmethod
    def fan_percent() -> float:
        try:
            fans = sensors_fans()
            if fans:
                for name, entries in fans.items():
                    for entry in entries:
                        if "gpu" in (entry.label.lower() or name.lower()):
                            return entry.percent
        except:
            pass

        return math.nan

    @staticmethod
    def frequency() -> float:
        # Not supported by Python libraries
        return math.nan

    @staticmethod
    def is_available() -> bool:
        try:
            return len(GPUtil.getGPUs()) > 0
        except:
            return False


class GpuAmd(sensors.Gpu):
    _mac_stats_cache = {}
    _mac_stats_time = 0

    @classmethod
    def _get_mac_stats(cls):
        import time
        import subprocess
        import re
        
        # 1-second cache to prevent display loop freezes due to excessive calls to ioreg
        if time.time() - cls._mac_stats_time < 1.0 and cls._mac_stats_cache:
            return cls._mac_stats_cache

        stats = {}
        try:
            # -c IOAccelerator focuses on the GPU, making the search instantaneous
            result = subprocess.run(['ioreg', '-r', '-c', 'IOAccelerator', '-l'], capture_output=True, text=True)
            
            max_temp = -1.0
            max_load = -1.0
            max_mem_used = -1.0
            matched_mem_free = -1.0
            max_clock = -1.0
            max_fan = -1.0

            for line in result.stdout.split('\n'):
                if '"PerformanceStatistics"' in line:
                    temp = re.search(r'"Temperature\(C\)"=(\d+)', line)
                    load_act = re.search(r'"GPU Activity\(%\)"=(\d+)', line)
                    load_dev = re.search(r'"Device Utilization %"=(\d+)', line)
                    mem_used = re.search(r'"inUseVidMemoryBytes"=(\d+)', line)
                    mem_free = re.search(r'"vramFreeBytes"=(\d+)', line)
                    clock = re.search(r'"Core Clock\(MHz\)"=(\d+)', line)
                    fan = re.search(r'"Fan Speed\(%\)"=(\d+)', line)

                    if temp:
                        max_temp = max(max_temp, float(temp.group(1)))

                    cur_load = -1.0
                    if load_act:
                        cur_load = max(cur_load, float(load_act.group(1)))
                    if load_dev:
                        cur_load = max(cur_load, float(load_dev.group(1)))
                    if cur_load >= 0:
                        max_load = max(max_load, cur_load)

                    if mem_used:
                        cur_mem_used = float(mem_used.group(1)) / 1024 / 1024
                        if cur_mem_used > max_mem_used:
                            max_mem_used = cur_mem_used
                            if mem_free:
                                matched_mem_free = float(mem_free.group(1)) / 1024 / 1024

                    if clock:
                        max_clock = max(max_clock, float(clock.group(1)))
                    if fan:
                        max_fan = max(max_fan, float(fan.group(1)))

            # Also check SMC GPU temperature keys if available
            try:
                for k in ['TG0D', 'TG0P', 'TG0d', 'TG0p', 'TGDD']:
                    smc_t = _read_smc_temp(k)
                    if smc_t is not None and 0 < smc_t < 125:
                        max_temp = max(max_temp, smc_t)
            except Exception:
                pass

            if max_temp >= 0: stats['temp'] = max_temp
            if max_load >= 0: stats['load'] = max_load
            if max_mem_used >= 0: stats['mem_used'] = max_mem_used
            if matched_mem_free >= 0: stats['mem_free'] = matched_mem_free
            if max_clock >= 0: stats['clock'] = max_clock
            if max_fan >= 0: stats['fan'] = max_fan

            cls._mac_stats_cache = stats
            cls._mac_stats_time = time.time()
        except Exception:
            pass
        return stats

    @staticmethod
    def stats() -> Tuple[float, float, float, float, float]:  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        if platform.system() == "Darwin":
            mac_stats = GpuAmd._get_mac_stats()
            if mac_stats:
                load = mac_stats.get('load', math.nan)
                mem_used = mac_stats.get('mem_used', math.nan)
                mem_free = mac_stats.get('mem_free', math.nan)
                temp = mac_stats.get('temp', math.nan)
                
                mem_total = math.nan
                mem_percentage = math.nan
                if not math.isnan(mem_used) and not math.isnan(mem_free):
                    mem_total = mem_used + mem_free
                    if mem_total > 0:
                        mem_percentage = (mem_used / mem_total) * 100
                        
                return load, mem_percentage, mem_used, mem_total, temp

        if pyamdgpuinfo:
            # Unlike other sensors, AMD GPU with pyamdgpuinfo pulls in all the stats at once
            pyamdgpuinfo.detect_gpus()
            amd_gpu = pyamdgpuinfo.get_gpu(0)

            try:
                memory_used_bytes = amd_gpu.query_vram_usage()
                memory_used = memory_used_bytes / 1024 / 1024
            except:
                memory_used_bytes = math.nan
                memory_used = math.nan

            try:
                memory_total_bytes = amd_gpu.memory_info["vram_size"]
                memory_total = memory_total_bytes / 1024 / 1024
            except:
                memory_total_bytes = math.nan
                memory_total = math.nan

            try:
                memory_percentage = (memory_used_bytes / memory_total_bytes) * 100
            except:
                memory_percentage = math.nan

            try:
                load = amd_gpu.query_load() * 100
            except:
                load = math.nan

            try:
                temperature = amd_gpu.query_temperature()
            except:
                temperature = math.nan

            return load, memory_percentage, memory_used, memory_total, temperature
        elif pyadl:
            amd_gpu = pyadl.ADLManager.getInstance().getDevices()[0]

            try:
                load = amd_gpu.getCurrentUsage()
            except:
                load = math.nan

            try:
                temperature = amd_gpu.getCurrentTemperature()
            except:
                temperature = math.nan

            # GPU memory data not supported by pyadl
            return load, math.nan, math.nan, math.nan, temperature
        
        return math.nan, math.nan, math.nan, math.nan, math.nan

    @staticmethod
    def fps() -> int:
        # Not supported by Python libraries
        return -1

    @staticmethod
    def fan_percent() -> float:
        if platform.system() == "Darwin":
            mac_stats = GpuAmd._get_mac_stats()
            return mac_stats.get('fan', math.nan)

        try:
            # Try with psutil fans
            fans = sensors_fans()
            if fans:
                for name, entries in fans.items():
                    for entry in entries:
                        if "gpu" in (entry.label.lower() or name.lower()):
                            return entry.percent

            # Try with pyadl if psutil did not find GPU fan
            if pyadl:
                return pyadl.ADLManager.getInstance().getDevices()[0].getCurrentFanSpeed(pyadl.ADL_DEVICE_FAN_SPEED_TYPE_PERCENTAGE)
        except:
            pass

        return math.nan

    @staticmethod
    def frequency() -> float:
        if platform.system() == "Darwin":
            mac_stats = GpuAmd._get_mac_stats()
            return mac_stats.get('clock', math.nan)

        try:
            if pyamdgpuinfo:
                pyamdgpuinfo.detect_gpus()
                return pyamdgpuinfo.get_gpu(0).query_sclk() / 1000000
            elif pyadl:
                return pyadl.ADLManager.getInstance().getDevices()[0].getCurrentEngineClock()
            else:
                return math.nan
        except:
            return math.nan

    @staticmethod
    def is_available() -> bool:
        if platform.system() == "Darwin":
            if GpuAmd._get_mac_stats():
                return True
        try:
            if pyamdgpuinfo and pyamdgpuinfo.detect_gpus() > 0:
                return True
            elif pyadl and len(pyadl.ADLManager.getInstance().getDevices()) > 0:
                return True
            else:
                return False
        except:
            return False


class Memory(sensors.Memory):
    @staticmethod
    def _get_darwin_memory():
        try:
            import ctypes
            import ctypes.util

            libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('c'))
            HOST_VM_INFO64 = 4
            HOST_VM_INFO64_COUNT = 38

            class vm_statistics64(ctypes.Structure):
                _fields_ = [
                    ('free_count', ctypes.c_uint32),
                    ('active_count', ctypes.c_uint32),
                    ('inactive_count', ctypes.c_uint32),
                    ('wire_count', ctypes.c_uint32),
                    ('zero_fill_count', ctypes.c_uint64),
                    ('reactivations', ctypes.c_uint64),
                    ('pageins', ctypes.c_uint64),
                    ('pageouts', ctypes.c_uint64),
                    ('faults', ctypes.c_uint64),
                    ('cow_faults', ctypes.c_uint64),
                    ('lookups', ctypes.c_uint64),
                    ('hits', ctypes.c_uint64),
                    ('purges', ctypes.c_uint64),
                    ('purgeable_count', ctypes.c_uint32),
                    ('speculative_count', ctypes.c_uint32),
                    ('decompressions', ctypes.c_uint64),
                    ('compressions', ctypes.c_uint64),
                    ('swapins', ctypes.c_uint64),
                    ('swapouts', ctypes.c_uint64),
                    ('compressor_page_count', ctypes.c_uint32),
                    ('throttled_count', ctypes.c_uint32),
                    ('external_page_count', ctypes.c_uint32),
                    ('internal_page_count', ctypes.c_uint32),
                    ('total_uncompressed_pages_in_compressor', ctypes.c_uint64),
                ]

            vm_stat = vm_statistics64()
            count = ctypes.c_uint32(HOST_VM_INFO64_COUNT)
            host = libc.mach_host_self()
            if libc.host_statistics64(host, HOST_VM_INFO64, ctypes.byref(vm_stat), ctypes.byref(count)) == 0:
                page_size = 4096
                app_memory = (vm_stat.internal_page_count - vm_stat.purgeable_count) * page_size
                wired = vm_stat.wire_count * page_size
                compressed = vm_stat.compressor_page_count * page_size
                used = app_memory + wired + compressed
                total = psutil.virtual_memory().total
                free = max(0, total - used)
                percent = (used / total) * 100.0 if total > 0 else 0.0
                return used, free, percent
        except Exception:
            pass
        return None

    @staticmethod
    def swap_percent() -> float:
        try:
            return psutil.swap_memory().percent
        except:
            return math.nan

    @staticmethod
    def virtual_percent() -> float:
        try:
            if platform.system() == "Darwin":
                darwin_mem = Memory._get_darwin_memory()
                if darwin_mem:
                    return darwin_mem[2]
            return psutil.virtual_memory().percent
        except:
            return math.nan

    @staticmethod
    def virtual_used() -> int:  # In bytes
        try:
            if platform.system() == "Darwin":
                darwin_mem = Memory._get_darwin_memory()
                if darwin_mem:
                    return int(darwin_mem[0])
            return psutil.virtual_memory().total - psutil.virtual_memory().available
        except:
            return -1

    @staticmethod
    def virtual_free() -> int:  # In bytes
        try:
            if platform.system() == "Darwin":
                darwin_mem = Memory._get_darwin_memory()
                if darwin_mem:
                    return int(darwin_mem[1])
            return psutil.virtual_memory().available
        except:
            return -1


class Disk(sensors.Disk):
    @staticmethod
    def disk_usage_percent() -> float:
        try:
            return psutil.disk_usage("/").percent
        except:
            return math.nan

    @staticmethod
    def disk_used() -> int:  # In bytes
        try:
            return psutil.disk_usage("/").used
        except:
            return -1

    @staticmethod
    def disk_free() -> int:  # In bytes
        try:
            return psutil.disk_usage("/").free
        except:
            return -1


class Net(sensors.Net):
    @staticmethod
    def stats(if_name, interval) -> Tuple[
        int, int, int, int]:  # up rate (B/s), uploaded (B), dl rate (B/s), downloaded (B)
        try:
            pnic_after = psutil.net_io_counters(pernic=True)

            upload_rate = 0.0
            uploaded = 0
            download_rate = 0.0
            downloaded = 0

            target = str(if_name).strip().upper() if if_name else ""
            if target in ["ALL", "AUTO", "TOTAL", "SUM"]:
                for nic, cur in pnic_after.items():
                    if is_loopback(nic):
                        continue
                    uploaded += cur.bytes_sent
                    downloaded += cur.bytes_recv
                    if nic in PNIC_BEFORE:
                        prev = PNIC_BEFORE[nic]
                        if cur.bytes_sent >= prev.bytes_sent:
                            upload_rate += (cur.bytes_sent - prev.bytes_sent) / interval
                        if cur.bytes_recv >= prev.bytes_recv:
                            download_rate += (cur.bytes_recv - prev.bytes_recv) / interval
                    PNIC_BEFORE[nic] = cur
                return upload_rate, uploaded, download_rate, downloaded

            if not if_name:
                return 0, 0, 0, 0

            if if_name in pnic_after:
                try:
                    upload_rate = (pnic_after[if_name].bytes_sent - PNIC_BEFORE[if_name].bytes_sent) / interval
                    uploaded = pnic_after[if_name].bytes_sent
                    download_rate = (pnic_after[if_name].bytes_recv - PNIC_BEFORE[if_name].bytes_recv) / interval
                    downloaded = pnic_after[if_name].bytes_recv
                except:
                    pass

                PNIC_BEFORE.update({if_name: pnic_after[if_name]})
            else:
                logger.warning("Network interface '%s' not found. Check names in config.yaml." % if_name)

            return upload_rate, uploaded, download_rate, downloaded
        except:
            return -1, -1, -1, -1

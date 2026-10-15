"""Execute the actual USB-audio prototype C with in-memory MMIO, offline only.

Run: python tools/test_usb_audio_proto.py
The host compiler is discovered locally (MSVC on Windows, cc elsewhere).
An explicitly named host-only DLL is written under build/usb_audio_proto_host.
No firmware/updater input, device access, external libraries or network needed.
"""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "firmware" / "usb_audio_proto"
OUT = ROOT / "build" / "usb_audio_proto_host"


def build_host_library(source="host_harness.c", prefix="usb_audio_HOST_TEST_ONLY", src_dir=None):
    OUT.mkdir(parents=True, exist_ok=True)
    # A loaded DLL is locked on Windows and two test modules may load it in one
    # process, so every build gets its own name; stale unlocked copies are removed.
    for old in OUT.glob(prefix + "_*"):
        try:
            old.unlink()
        except OSError:
            pass
    stem = "%s_%d_%d" % (prefix, os.getpid(), time.monotonic_ns())
    env = os.environ.copy()
    if os.name == "nt":
        cl = shutil.which("cl")
        if cl is None:
            vswhere = (Path(os.environ.get("ProgramFiles(x86)",
                                          "C:/Program Files (x86)")) /
                       "Microsoft Visual Studio/Installer/vswhere.exe")
            if vswhere.exists():
                found = subprocess.check_output([
                    str(vswhere), "-latest", "-products", "*", "-find",
                    "VC/Tools/MSVC/**/bin/Hostx64/x64/cl.exe"], text=True).splitlines()
                cl = found[-1] if found else None
        if cl is None:
            raise RuntimeError("A local MSVC x64 C compiler is required for host tests")
        env["PATH"] = str(Path(cl).parent) + os.pathsep + env.get("PATH", "")
        library = OUT / (stem + ".dll")
        command = [cl, "/nologo", "/TC", "/LD", "/Od", "/Oi-", "/GS-", "/Zl",
                   "/wd4068", "/Fo" + str(OUT / (stem + ".obj")),
                   "/Fe" + str(library), str((src_dir or SRC) / source),
                   "/link", "/NODEFAULTLIB", "/NOENTRY"]
    else:
        cc = shutil.which("cc")
        if cc is None:
            raise RuntimeError("A local host C compiler is required for host tests")
        library = OUT / (stem + ".so")
        command = [cc, "-std=c99", "-shared", "-fPIC", "-O0",
                   "-Wno-unknown-pragmas", str((src_dir or SRC) / source),
                   "-o", str(library)]
    result = subprocess.run(command, cwd=OUT, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Host harness compilation failed:\n" +
                           result.stdout + result.stderr)
    return ctypes.CDLL(str(library))


def descriptors(data):
    """USB bLength walker: fail on malformed/truncated records."""
    records = []
    position = 0
    while position < len(data):
        size = data[position]
        if size < 2 or position + size > len(data):
            raise ValueError("invalid USB descriptor at byte %d" % position)
        records.append(data[position:position + size])
        position += size
    return records


class UsbAudioPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library()
        cls.lib.usb_audio_copy_descriptors.argtypes = [ctypes.c_void_p,
                                                      ctypes.c_uint, ctypes.c_uint]
        cls.lib.usb_audio_copy_descriptors.restype = ctypes.c_uint
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.usb_audio_set_alt.restype = ctypes.c_int
        cls.lib.host_fragment.argtypes = [ctypes.c_uint]
        cls.lib.host_fragment.restype = ctypes.POINTER(ctypes.c_ubyte)

    def setUp(self):
        self.lib.host_reset()

    def copy(self, requested=65535, capacity=512):
        storage = (ctypes.c_ubyte * 520)(*([0xa5] * 520))
        count = self.lib.usb_audio_copy_descriptors(ctypes.byref(storage, 4),
                                                    requested, capacity)
        return count, bytes(storage)

    def full_configuration(self):
        count, storage = self.copy()
        return storage[4:4 + count]

    def trace(self):
        self.assertEqual(self.lib.host_trace_overflow(), 0)
        return [(self.lib.host_trace_address(i), self.lib.host_trace_width(i))
                for i in range(self.lib.host_trace_count())]

    def test_configuration_header_and_total_length(self):
        data = self.full_configuration()
        self.assertEqual(len(data), 192)
        self.assertEqual(data[:2], b"\x09\x02")
        self.assertEqual(int.from_bytes(data[2:4], "little"), len(data))
        self.assertEqual(data[4], 4)
        self.assertEqual(len(descriptors(data)), 23)

    def test_device_descriptor_is_separate_and_pointer_list_terminated(self):
        device = self.lib.host_fragment(0)
        self.assertEqual(bytes(device[:18])[:2], b"\x12\x01")
        self.assertTrue(all(bool(self.lib.host_fragment(i)) for i in range(24)))
        self.assertFalse(bool(self.lib.host_fragment(24)))

    def test_every_host_length_clips_without_touching_canaries(self):
        expected = self.full_configuration()
        for requested in list(range(256)) + [65535, 0xffffffff]:
            with self.subTest(requested=requested):
                count, storage = self.copy(requested=requested)
                self.assertEqual(count, min(requested, 192))
                self.assertEqual(storage[:4], b"\xa5" * 4)
                self.assertEqual(storage[4:4 + count], expected[:count])
                self.assertEqual(storage[4 + count:], b"\xa5" * (516 - count))

    def test_every_destination_capacity_clips_without_touching_canaries(self):
        expected = self.full_configuration()
        for capacity in range(211):
            with self.subTest(capacity=capacity):
                count, storage = self.copy(capacity=capacity)
                self.assertEqual(count, min(capacity, 192))
                self.assertEqual(storage[4:4 + count], expected[:count])
                self.assertEqual(storage[4 + count:], b"\xa5" * (516 - count))
        self.assertEqual(self.lib.usb_audio_copy_descriptors(None, 512, 512), 0)

    def test_interfaces_endpoint_ownership_and_audio_format(self):
        records = descriptors(self.full_configuration())
        interfaces = [r for r in records if r[1] == 4]
        self.assertEqual([(r[2], r[3], r[4]) for r in interfaces],
                         [(0, 0, 0), (1, 0, 2), (2, 0, 0), (3, 0, 0), (3, 1, 1)])
        endpoints = [r for r in records if r[1] == 5]
        self.assertEqual([(r[2], r[3], int.from_bytes(r[4:6], "little"))
                          for r in endpoints], [(3, 2, 64), (0x84, 2, 64),
                                                (0x81, 5, 180)])
        self.assertEqual(endpoints[-1][6], 1)  # one full-speed USB frame
        audio_format = next(r for r in records if r[:4] == b"\x0b\x24\x02\x01")
        self.assertEqual(audio_format[4:8], bytes([2, 2, 16, 1]))
        self.assertEqual(int.from_bytes(audio_format[8:11], "little"), 44100)
        ac = records.index(next(r for r in records if r[1:4] == b"\x04\x02\x00"))
        header, source, sink = records[ac + 1:ac + 4]
        self.assertEqual(int.from_bytes(header[5:7], "little"),
                         len(header) + len(source) + len(sink))
        self.assertEqual(header[7:], bytes([1, 3]))
        self.assertEqual(sink[7], source[3])  # terminal graph is connected

    def test_inactive_sof_never_accesses_registers(self):
        self.lib.usb_audio_sof_tick()
        self.assertEqual(self.trace(), [])
        self.assertEqual(self.lib.host_get_state(5), 0)

    def test_invalid_full_width_alternate_never_changes_state_or_mmio(self):
        self.assertEqual(self.lib.usb_audio_set_alt(1), 0)
        state = [self.lib.host_get_state(i) for i in range(6)]
        self.lib.host_clear_trace()
        for alt in [2, 3, 255, 256, 257, 65535, 0xffffffff]:
            self.assertEqual(self.lib.usb_audio_set_alt(alt), -1)
            self.assertEqual([self.lib.host_get_state(i) for i in range(6)], state)
        self.assertEqual(self.trace(), [])

    def test_setup_preserves_power_bits_and_uses_byte_index(self):
        self.lib.host_set_register(0x01e00400, 0x4100)
        self.assertEqual(self.lib.usb_audio_set_alt(1), 0)
        self.assertEqual(self.lib.host_get_register(0x01e00400), 0xc100)
        self.assertIn((0x01e0040e, 1), self.trace())
        self.assertEqual(self.lib.host_get_register(0x01e00410), 180)
        self.assertEqual(self.lib.host_get_register(0x01e00464), 0x28)
        self.assertEqual(self.lib.host_get_register(0x01e00462) & 255, 0x15)

    def test_sof_packet_pattern_has_441_frames_per_ten_ms(self):
        self.lib.usb_audio_set_alt(1)
        total = 0
        for i in range(1000):
            self.lib.host_set_register(0x01e00512, 0)  # synthetic host consumes packet
            self.lib.host_clear_trace()
            self.lib.usb_audio_sof_tick()
            trace = self.trace()
            frames = trace.count((0x01e00424, 4))
            self.assertEqual(frames, 45 if i % 10 == 0 else 44)
            self.assertEqual(set(trace), {(0x01e00512, 2), (0x01e00424, 4)})
            self.assertEqual(self.lib.host_get_register(0x01e00512), 0x6001)
            self.assertEqual(self.lib.host_get_register(0x01e00424), 0)
            total += frames
        self.assertEqual(total, 44100)
        self.assertEqual(self.lib.host_get_state(5), 1000)

    def test_busy_endpoint_skips_fifo_and_does_not_spin(self):
        self.lib.usb_audio_set_alt(1)
        self.lib.host_set_register(0x01e00512, 0x6001)
        self.lib.host_clear_trace()
        self.lib.usb_audio_sof_tick()
        self.assertEqual(self.trace(), [(0x01e00512, 2)])
        self.assertEqual(self.lib.host_get_state(4), 1)
        self.assertEqual(self.lib.host_get_state(5), 0)

    def test_alt_zero_flushes_twice_and_stops_sof(self):
        self.lib.usb_audio_set_alt(1)
        self.lib.host_clear_trace()
        self.assertEqual(self.lib.usb_audio_set_alt(0), 0)
        self.assertEqual(self.trace(), [(0x01e00512, 2), (0x01e00512, 2)])
        self.assertEqual(self.lib.host_get_register(0x01e00512), 0x6008)
        self.assertEqual(self.lib.host_get_state(1), 0)
        self.assertEqual(self.lib.host_get_state(2), 0)
        self.lib.host_clear_trace()
        self.lib.usb_audio_sof_tick()
        self.assertEqual(self.trace(), [])

    def test_restart_resets_packet_phase(self):
        self.lib.usb_audio_set_alt(1)
        self.lib.usb_audio_sof_tick()
        self.lib.usb_audio_set_alt(0)
        self.lib.usb_audio_set_alt(1)
        self.assertEqual(self.lib.host_get_state(3), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""ONE-TIME boot-logo installer: replace the ZOOM logo the boot program draws at power-on.

  python tools/make_boot_logo_updater.py <official v2.00 updater.exe> "<name> BOOT LOGO.exe" <logo 92x16.png>

THE ONE RISKY WRITE. The boot program (flash 0x0..0x28000, resource 0x8E) is also update
mode: if this write is interrupted (USB drop, power loss) or wrong, the pedal can only be
recovered with a hardware programmer (recon/25 section 6). Zoom's own v2.00 updater
erases and writes this same region on every run (its stages 4 and 5); this copy runs
ONLY those two stages, with Zoom's boot program changed in nothing but the 184-byte
logo bitmap (recon/09: 92x16, LCD page format, file 0x1be60, load c0229720, inside one
AIS section load; the AIS stream has no CRC commands). The main firmware, effects,
presets and settings sector are not touched.

Checks before writing the .exe (any failure refuses):
  - the updater's stage table is exactly Zoom's v2.00 table;
  - resource 0x8E is the stock v2.00 boot program (SHA-256 pinned, 163840 bytes) and
    holds the ZOOM logo exactly once, at 0x1be60, inside an AIS section load;
  - the new boot program differs from stock only inside those 184 bytes, and its AIS
    command walk is identical (same commands, offsets and jump-and-close);
  - the new stage table is exactly [erase 0x0 size 0x28000, write 0x0 resource 0x8E];
  - the output name contains "BOOT LOGO".
Owner procedure: laptop on mains power, a direct USB port (no hub), nothing else running;
pedal in update mode; run it once and do not touch anything until it reports done.
"""
import argparse
import hashlib
import struct
import sys
from pathlib import Path

import pefile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_controller_fw as ctl  # noqa: E402  (ais_commands)
import make_fs_restore_updater as upd  # noqa: E402  (EXPECTED, TABLE_VA, ZOOM_LOGO, splash_bytes)

BOOT_RES, BOOT_ADDR, BOOT_REGION = 0x8E, 0x0, 0x28000
BOOT_SIZE = 163840
BOOT_SHA256 = "5ee756a5dee51b4e790a6e6f6b6c0a8a1ea531c245a13124e8a5897530b01622"
LOGO_OFF, LOGO_LEN = 0x1be60, 184
LOGO_LOAD = 0xc0229720
STAGES = [(1, BOOT_ADDR, BOOT_REGION, 0), (2, BOOT_ADDR, 0, BOOT_RES)]


def ais_walk(d):
    return [(o, op, a) for o, op, a in ctl.ais_commands(d)]


def new_boot(stock, logo_bytes):
    """Stock boot program with only the logo replaced; raises ValueError on any doubt."""
    if len(stock) != BOOT_SIZE or hashlib.sha256(stock).hexdigest() != BOOT_SHA256:
        raise ValueError("resource 0x8E is not the stock v2.00 boot program")
    if stock.find(upd.ZOOM_LOGO) != LOGO_OFF or stock.count(upd.ZOOM_LOGO) != 1:
        raise ValueError("ZOOM logo not found exactly once at %#x" % LOGO_OFF)
    if len(logo_bytes) != LOGO_LEN:
        raise ValueError("logo must be %d bytes" % LOGO_LEN)
    walk = ais_walk(stock)
    inside = [(o, a) for o, op, a in walk if op == ctl.AIS_SECTION_LOAD
              and o + 12 <= LOGO_OFF and LOGO_OFF + LOGO_LEN <= o + 12 + a[1]]
    if len(inside) != 1 or inside[0][1][0] + (LOGO_OFF - inside[0][0] - 12) != LOGO_LOAD:
        raise ValueError("logo is not inside exactly one AIS section load at %#x" % LOGO_LOAD)
    out = bytearray(stock)
    out[LOGO_OFF:LOGO_OFF + LOGO_LEN] = logo_bytes
    out = bytes(out)
    diff = [i for i in range(BOOT_SIZE) if out[i] != stock[i]]
    if diff and not (LOGO_OFF <= diff[0] and diff[-1] < LOGO_OFF + LOGO_LEN):
        raise ValueError("boot program would change outside the logo")
    if ais_walk(out) != walk:
        raise ValueError("AIS command walk changed")
    return out


def main(src, dst, logo):
    if "BOOT LOGO" not in Path(dst).name.upper():
        sys.exit('the output name must contain "BOOT LOGO"')
    if Path(src).resolve() == Path(dst).resolve():
        sys.exit("output must differ from the official updater")
    pe = pefile.PE(src)
    off = pe.get_offset_from_rva(upd.TABLE_VA - pe.OPTIONAL_HEADER.ImageBase)
    data = bytearray(open(src, "rb").read())
    if [struct.unpack_from("<4I", data, off + 16 * k) for k in range(8)] != upd.EXPECTED:
        sys.exit("unexpected stage table: not the v2.00 G1X FOUR updater")
    res = {e.id: e for t in pe.DIRECTORY_ENTRY_RESOURCE.entries if str(t.name) == "BIN"
           for e in t.directory.entries}
    e = res[BOOT_RES].directory.entries[0].data.struct
    roff = pe.get_offset_from_rva(e.OffsetToData)
    stock = bytes(data[roff:roff + e.Size])
    try:
        boot = new_boot(stock, upd.splash_bytes(logo, 92, 16))
    except ValueError as exc:
        sys.exit(str(exc))
    data[roff:roff + e.Size] = boot
    table = STAGES + [(0, 0, 0, 0)] * (8 - len(STAGES))
    if table[:2] != [upd.EXPECTED[3], upd.EXPECTED[4]]:
        sys.exit("boot stages are not Zoom's own")
    for k, st in enumerate(table):
        struct.pack_into("<4I", data, off + 16 * k, *st)
    check = pefile.PE(data=bytes(data))
    ce = {r.id: r for t in check.DIRECTORY_ENTRY_RESOURCE.entries if str(t.name) == "BIN"
          for r in t.directory.entries}[BOOT_RES].directory.entries[0].data.struct
    if bytes(check.get_data(ce.OffsetToData, ce.Size)) != boot:
        sys.exit("resource 0x8E read-back mismatch")
    open(dst, "wb").write(data)
    print("boot program: stock v2.00 with the logo replaced by %s (%d bytes differ, all in "
          "%#x..%#x); SHA-256 %s" % (logo, sum(a != b for a, b in zip(boot, stock)), LOGO_OFF,
                                     LOGO_OFF + LOGO_LEN, hashlib.sha256(boot).hexdigest()))
    print("wrote %s; stages:" % dst)
    print("   erase 0x000000 size 0x28000   (boot program = update mode: DO NOT INTERRUPT)")
    print("   write 0x000000 resource 0x8e")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("logo")
    a = ap.parse_args()
    main(a.src, a.dst, a.logo)

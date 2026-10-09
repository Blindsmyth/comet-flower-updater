# Recon 25: boot/update program (res5) safety read

Static analysis only. Every claim: instruction address, short excerpt, and
confidence (confirmed / likely / guess). Gaps are stated explicitly, not
filled with plausible claims.

## 1. Boot decision

### Full decision, confirmed exactly as recon/15 stated, with GPIO-pin-level proof (confirmed)
`c020a4d0` is the entire decision. After platform init (`c020a4d4 CALLP c020ce20`),
it reads both footswitches via `c022ba0c`: index 0 -> GPIO5, index 1 -> GPIO3
(`c022ba14 MVK 5,A4; c022ba16 MVK 3,A4; CALLP c022b928`). **If either reads
high (nonzero), it branches straight to normal load `c020a568`** (evidence:
`c020a4e4 [A0] BNOP 0xc020a568,5` and `c020a4ee [A0] BNOP 0xc020a568,5`) — so
both footswitches must be **low** to continue toward update mode.

It then requires ten button GPIOs to read **high**, each checked by
`c022b968`/`c022b9c8`/`c022b9d4`/`c022b9e4` -> `c022b928`, any single low
branching straight to `c020a568`:
```
c020a4f0 CALLP c022b968,B3 ; A4=0  -> GPIO0   (c022b96a..76: idx0=0)
c020a500 CALLP c022b968,B3 ; A4=1  -> GPIO27  (c022b978..82: idx1=27)
c020a508 CALLP c022b968,B3 ; A4=2  -> GPIO24  (idx2=24)
c020a514 CALLP c022b968,B3 ; A4=3  -> GPIO26  (idx3=26)
c020a520 CALLP c022b968,B3 ; A4=4  -> GPIO37  (idx4=37)
c020a52c CALLP c022b968,B3 ; A4=5  -> GPIO38  (idx5=38)
c020a534 CALLP c022b968,B3 ; A4=6  -> GPIO86  (idx6=86)
c020a544 CALLP c022b9e4,B3        -> GPIO2  (direct A4=2 at c022b9e6)
c020a54c CALLP c022b9d4,B3        -> GPIO4  (direct A4=4 at c022b9d8)
c020a554 CALLP c022b9c8,B3        -> GPIO6  (direct A4=6 at c022b9cc)
```
This proves `c022b968`'s index table (0->0, 1->27, 2->24, 3->26, 4->37, 5->38,
6->86, from `c022b96a..c022b9a2`) and shows the last three checks bypass the
index table and pass the GPIO number directly. The pin set is exactly
GPIO{0,27,24,26,37,38,86,2,4,6} from recon/15, now with the index-table
instructions as proof. If every one of the 10+2 conditions holds, it falls
through to `c020a560 CALLP c0201404,B3` (update mode); otherwise `c020a568
CALLP c022ba40,B3` (normal load).

### No other condition exists in the decision (confirmed for this function; one gap noted)
`c020a4d0` contains no flash read, no checksum and no stored "bad firmware"
flag — only the platform-init call and the 12 GPIO reads above. `grep -n
"0xc020a4d0"` over the whole disassembly finds no `CALLP` reference to this
address anywhere in `build/codex7/boot.dis`: it is reached only via an
indirect (table-based) call, consistent with the task-entry-table pattern
recon/15 already found for main firmware (MainApp/MIDI/etc. entries resolved
from a data table, not a direct call). **Gap:** the caller/table that invokes
`c020a4d0` itself was not located, so a hypothetical second trigger path
(e.g. another table entry calling it under a different condition) cannot be
fully ruled out; no evidence of one was found either.

## 2. Normal load and failure

### Signature check before the AIS load, and its failure path (confirmed)
`c022ba40` (the "normal load" target) first reads 16 bytes from flash
0xBFFF0 one byte at a time and compares them against 16 bytes already read
into a stack buffer by `c01fda8c` (the same flash-read helper used later for
the real AIS load):
```
c022ba48 MVK 0xfffffff0,A4 ; c022ba50 MVKH 0xb0000,A4   -> A4 = 0x000bfff0
c022ba54 CALLP c01fda8c,B3  ; reads 16 bytes into stack buf B15+0x12
c022ba68 LDBU *A4[0],A1     ; c022ba6a LDBU *B4[0],B1   ; c022ba6e CMPEQ
c022ba70 [!A0] BNOP 0xc022ba80,5   ; loop 16 times (B0)
c022ba80 CMPEQ B1,A1,B0 ; c022ba84 [!B0] BNOP 0xc022bbe8,5   ; mismatch -> fail
```
On a match it proceeds to parse AIS commands starting at flash 0x33000
(`c022baac MVK 0x33,A10; SHL A10,0xc,A10`) exactly as recon/15/17 already
described (section-load 0x58535901, fill 0x5853590a, jump 0x58535906,
looping while flash pointer < 0xbf000, confirmed in recon/17).

**Failure is a hang, not a fallback to update mode (confirmed).** Both the
signature mismatch (`c022bbe8`) and "AIS stream exhausted without a jump
command" (`c022bb94`, reached when the section loop's pointer reaches
0xbf000 without having seen command 0x58535906) call a display/indicator
routine (`c01f85d4`, `c01f7f44`) and then loop forever:
```
; signature-mismatch path
c022bbe8 CALLP c01f85d4,B3
c022bbf8 CALLP c01f7f44,B3   ; writes an indicator word
c022bc0c CALLP c01fb8e4,B3
c022bc14 BNOP 0xc022bc14,5   ; branch to self: true infinite loop
c022bc18 NOP
c022bc1c NOP
```
```
; AIS-exhausted path
c022bb94 CALLP c01f85d4,B3
c022bba4 CALLP c01f7f44,B3 ; writes 0xffff9cfd
c022bbc4 CALLP c01f7f44,B3 ; writes 0xffff9d0b
c022bbd0 CALLP c01fb8e4,B3
c022bbe0 CALLP c0203800,B3 ; A4=0x3e8 (1000); c022bbe6 BNOP 0xc022bbe0,5
```
The second loop re-calls `c0203800` with a fixed argument every pass
(likely a delay/blink), but it never leaves the loop back toward
`c020a4d0`/`c0201404`. **Neither failure path re-enters the update-mode
decision or the GPIO check.** A corrupt res1 signature or a main-firmware
jump command that never appears leaves the pedal hung with whatever the
indicator routine shows (not yet decoded: LED pattern vs. LCD message) —
recovery would need a manual re-entry to update mode via the footswitch
gesture at the next *power cycle*, which is untouched by this hang (the
hang is inside the current boot attempt, not a corruption of the decision
code itself).

**Gap:** what happens if the loaded res1 entry point (`c020d840`'s jump
target) is reached and that code later crashes, resets, or never returns —
i.e. a failure *after* control leaves the boot program — was not traced.
That would require the exception/reset vector table and is not covered by
this reading of `c020a4d0`/`c022ba40`.

## 3. Update mode (c0201404)

### Can update mode overwrite res5 itself? Yes — confirmed by the stock updater's own stage table (confirmed, host-side)
`tools/make_fs_restore_updater.py` (read as text only, not run) hard-codes
the exact 8-stage table it found in Zoom's official "ZOOM G1X FOUR System
v2.00 Updater.exe" at PE `.rdata` VA `0x43AC88` (16-byte entries
`[op, flash_addr, size, resource]`; op 1 = erase, op 2 = write):
```python
EXPECTED = [(1, 0xBF000, 0x1000, 0), (1, 0x28000, 0xB000, 0), (2, 0x28000, 0, 0x85),
            (1, 0x0, 0x28000, 0), (2, 0x0, 0, 0x8E), (1, 0x33000, 0x8C000, 0),
            (2, 0x33000, 0, 0x81), (2, 0xBF000, 0, 0x8B)]
```
Stages 4 and 5 are `erase 0x0, size 0x28000` then `write resource 0x8E
(142) at 0x0` — **resource 142 is the 163,840-byte boot program**, i.e.
res5 itself, and 0x28000 is exactly its region size. This is not an inferred
capability: it is a stage Zoom's own shipped updater *routinely executes* on
every normal boot-program update. The script's own docstring independently
corroborates this from docs/RECOVERY_G1.md's updater-table reading: "boot
program | 0x000000-0x028000 | 142 (163,840 B)". Since the *host* tool is
the one sending `(op,address,size,resource)` over the wire and the pedal's
update-mode firmware (`c0201404` et al.) must execute exactly this stage
for Zoom's own self-update to work, update mode's flash-write path is
address-driven by the host, with at least this one officially-used address
being inside the boot program region.

**What is confirmed vs. not directly disassembled:** the *host-side* stage
table and its semantics (op/address/size/resource) are confirmed by reading
the updater .exe's own data (via the script's `EXPECTED` check, which
`main()` verifies against the live PE before trusting it — see
`make_fs_restore_updater.py` lines 217-222). The *firmware-side* code in
`c0201404`'s call tree that receives the address and performs the
erase/program over SPI was not traced instruction-by-instruction to find an
explicit bounds check (or its absence) in `build/codex7/boot.dis` — budget
was spent instead on the higher-value, already-conclusive host-table
evidence above, since Zoom's own tool using address 0 settles the yes/no
question regardless of whether a firmware-side guard also exists. **Gap:**
no disassembly-level confirmation of whether `c0201404` validates the
incoming address at all (e.g. rejects a request to write below 0x28000 from
a non-Zoom host); only that it must accept at least the legitimate
Zoom-boot-program write to work as shipped.

### Our own tooling's self-imposed restriction (confirmed, host-side, defence in depth)
Separately from what the pedal *can* accept, `make_fs_restore_updater.py`
itself refuses to ever emit a stage touching the boot or settings regions
when building `--patch-fw`/`--controller-fw` images:
```python
if patch_fw is not None or grown is not None:
    # Boot/update-mode program [0, 0x28000), settings/recovery sector
    # [0xbf000, 0xc0000), and all unused flash regions remain untouched.
    allowed = {(1, FS_ADDR, FS_SIZE, 0), (2, FS_ADDR, 0, FS_RES),
               (1, PRESET_ADDR, PRESET_SIZE, 0), (2, PRESET_ADDR, 0, PRESET_RES),
               (1, FW_ADDR, FW_SIZE, 0), (2, FW_ADDR, 0, FW_RES)}
    if len(new) > 8 or any(stage not in allowed for stage in new):
        sys.exit("unsafe update stages: refused")
```
This is a **host-tool-level allowlist**, not a pedal-firmware guarantee: it
protects us only if we keep using this script unmodified to build test
images. It does not, by itself, prove the pedal would reject an
out-of-allowlist stage if one were sent by some other means.

## 4. Flash layout

### Confirmed from two independent sources: the stock updater table and the firmware's own region table
The updater stage table above gives, for the regions it touches:

| Region | Flash range | Size | Updater resource |
|---|---|---|---|
| boot program (res5) | 0x000000-0x028000 | 0x28000 | 0x8E (142) |
| graphics/presets | 0x028000-0x033000 | 0xB000 | 0x85 (133) |
| main firmware (res1) | 0x033000-0x0BF000 | 0x8C000 | 0x81 (129) |
| settings | 0x0BF000-0x0C0000 | 0x1000 | 0x8B (139) |

This matches docs/RECOVERY_G1.md's table exactly (confirmed, cross-source).

**New, directly-read evidence — the firmware's own internal region table.**
`build/fw/res1_493412.bin` at file offset `0x77C82` (cited by
`make_fs_restore_updater.py`'s docstring as "the firmware's own region
table") contains, read directly as little-endian 32-bit words:
```
0x77C82: 00033000 0008C000   -> main firmware:   base 0x033000, size 0x8C000
0x77C92: 000BF000 00001000   -> settings:        base 0x0BF000, size 0x1000
0x77C9A: 00102000 002FE000   -> file system:     base 0x102000, size 0x2FE000
```
(hex dump: `xxd -s 0x77C82 -l 0x18 build/fw/res1_493412.bin` ->
`00 30 03 00 00 c0 08 00 00 f0 0b 00 00 10 00 00 00 20 10 00 00 e0 2f 00`,
read little-endian 4 bytes at a time.) Immediately after these three
(address,size) pairs the table continues with what read as **code
pointers** (`c0164cc0`, `c0164d20`, `c0164d44`, `c0133f28`, ...), consistent
with a small dispatch table of three regions the main firmware itself knows
how to erase/write (self, settings, file system) plus per-region handler
addresses. **This table does not contain an entry for the boot program
(0x0-0x28000) or the graphics/presets region (0x28000-0x33000).**
Confidence: confirmed for the table's contents (direct file read, no
disassembly needed); likely (not fully proven) that this table is what
gates every main-firmware-side flash write — see section 5's gap note.

The known unaccounted range `0x0C0000-0x102000` (0x42000 bytes, between
settings and the file system) is untouched by both the stock updater table
and this internal region table; its purpose remains unconfirmed (recon/17
flagged it only as "(patches?)").

### Shared low-level SPI engine, boot vs. main firmware (confirmed engine identity; command bytes not isolated)
Main firmware's flash/ADC serial engine is `1180673c=serial_xfer_entry`
(recon/15's already-documented "1180673c"), which calls `11801498`,
`118015f4` (`serial_phase2`), `118017b8` (`serial_phase3`), `118019b8`
(`serial_phase4`) using MMIO bases **0x01c10000** and **0x01e27000**
(`build/fw/map/facts/chunk_00.md`). The *same* two bases appear as operand
targets in `build/codex7/bootrefs.txt` (e.g. `c01f4424 B4 01c14038`,
`c01f4444 A4 01c14184`, `c01f4464 A6 01e27804`, `c01f44b0 A4 01e27a04`),
i.e. **res5 drives the identical peripheral cluster** rather than a
separate boot-only SPI block. This supports (does not by itself prove) that
update-mode flash writes go through genuine SPI transactions to the same
IS25LP032 chip the main firmware uses, not a different mechanism. **Gap:**
the actual SPI command bytes (0x02 page program, 0x20/0xD8 erase, 0x03
read, write-enable 0x06) were not isolated at specific instruction
addresses in either `boot.dis` or `main.dis` — this would need a further
pass reading `serial_xfer_entry`/`serial_phase3` and their boot-side
counterparts byte-by-byte, which was not done here. GPIO90, found earlier
(recon/15) toggling around the serial transfer, is the **expression-pedal
ADC's chip-select**, not flash CS (confirmed: its only caller in main
firmware is `1180abc0=ad_serial_read`, matching recon/15's pedal-read
path) — the flash chip's own CS line was not identified.

## 5. Main-firmware reach

### Main firmware's flash-write call graph, traced from the shared SPI engine (confirmed graph; address bound not fully closed)
Every caller of `1180673c=serial_xfer_entry` that is not the expression-
pedal read (`1180abc0=ad_serial_read`) is a `cfg_locked_write_*` function
(`build/fw/map/facts/chunk_00.md`): `c01451a0=cfg_locked_write_5byte_core`,
`c0145220=cfg_locked_write_6byte_core`, `c0145270=cfg_write_packet_build_32`,
`c01452ac=cfg_locked_write_chunked_step`, `c0145320=cfg_locked_write_small_step`,
`c0145378=cfg_write_packet_build_216`, plus two small orchestrators
(`11805420`, `11805484`). These are the leaves; the mid-level entry points
actually called from task code are `c01453b4=cfg_locked_write_chunked`,
`c01454f4=cfg_locked_write_small`, `c0145568=cfg_locked_write_chunked2`
(`build/fw/map/facts/chunk_10.md`), all tagged root `DataStore` (plus
MainApp/MIDI/PreLoad/RhythmService/UpdateUI, i.e. reachable from several
tasks).

Their callers resolve to three families:
- **Boot-time settings init**, `c0136a18=cfg_mainapp_write_sections` and
  `c0137204=cfg_mainapp_write_finalize`, both called only from
  `c015d428=mainapp_startup_init` (recon/15's already-identified MainApp
  startup hook) — writing default/migrated settings once per boot
  (`build/fw/map/facts/chunk_07.md`).
- **Effect/patch file installs**, `c01367f8=cfg_datastore_write_sections`
  called from `11809160=datastore_copy_helper`, root `DataStore,UpdateUI` —
  this is the normal DIY-effect-install path (recon/13/14), consistent with
  `tools/pedal_g1.py`'s MIDI file-upload protocol, not a firmware
  re-flasher.
- **Service menu and MIDI-triggered writes**: `118092a0=midi_param_lock_op`,
  `c012d80c=midi_param_reply_build23`, `c015d7e0=mainapp_model_detect`, and
  notably `c0165db0=sysmenu_checksum_write_locked` — the service menu's
  **"CheckSum"** item (named in docs/RECOVERY_G1.md) reaches
  `cfg_locked_write_small`, i.e. the CheckSum screen can itself write
  through this same path (likely a calibration/checksum value store, not
  yet disassembled further).

**None of these call chains were found to pass a flash address inside
0x0-0x28000 (boot) or 0x28000-0x33000 (graphics).** The firmware's own
region table (section 4) only enumerates main-firmware-self, settings and
file-system regions as targets, and no function on this call graph is named
or shaped like a boot-region writer. **This is "likely", not "confirmed":**
I did not trace `cfg_locked_dispatch` (`c0161200`, the common dispatcher
all three write-size variants pass through) down to the actual absolute
address computation to verify it is bounded to the three region-table
entries. That would be the remaining step to fully close this question.

**Gap:** the file-system calls docs/RECOVERY_G1.md names
(`f_findfirst`, `f_unlink`, `ffs_format`) were not located by name in
`build/fw/map/facts/` (likely stripped/inlined library symbols) and so were
not re-verified here; only the `cfg_locked_write_*`/`DataStore` graph above
was traced. A full answer to "can *any* normal-firmware code path reach the
boot region" would need `cfg_locked_dispatch`'s address arithmetic and the
`ffs_format`-equivalent code, neither of which was reached.

## 6. Verdict for pedal tests

### What can brick the pedal beyond update-mode recovery
1. **A corrupted/incompatible res1 (main firmware) hangs, it does not
   recover (confirmed, section 2).** If flash 0xBFFF0's 16-byte signature
   does not match what was just read via `c01fda8c`, or if the AIS stream
   from 0x33000 reaches 0xbf000 without a jump command, res5 shows an
   indicator and loops forever (`c022bc14`/`c022bbe0`). It does **not**
   fall back into the GPIO-decision/update-mode path on its own. Recovery
   still works because **this failure is confined to flash 0x33000-0xbf000
   (res1)**: update mode is reached again by power-cycling with both
   footswitches held, which re-enters `c020a4d0` fresh and does not depend
   on anything res1 touched. So a bad *main-firmware* image is recoverable
   via update mode (as already proven in practice, docs/RECOVERY_G1.md),
   but it will hang rather than silently reboot into update mode if you
   forget the footswitch gesture.
2. **A bad image that targets the boot region (0x0-0x28000) is the one
   thing that is not update-mode-recoverable (confirmed capability exists,
   section 3)**: update mode accepts host-specified erase/write stages,
   and Zoom's own stage 4/5 (erase+write 0x0, size 0x28000) proves the
   pedal firmware executes writes there when told to. If such a write were
   interrupted (power loss, USB drop) or sent a corrupt boot image,
   there would be no software fallback — update mode itself is what would
   be destroyed. This is the one region where our tooling's own allowlist
   (section 3) is the only thing standing between "a bug in a patch
   script" and "no recovery path at all," since it is host-tool discipline,
   not a pedal-side guarantee (gap noted in section 3).
3. **A bad effect file-system image is recoverable (confirmed in
   practice):** this is exactly the 2026-10-06 incident (docs/RECOVERY_G1.md)
   — hang at the ZOOM logo, fixed by writing a fresh FS image at 0x102000
   via update mode. res5 and res1 were untouched throughout.
4. **A bad settings-sector write is likely recoverable** (erase+rewrite of
   0xBF000-0xC0000 is a normal updater/boot-init stage; it is 4 KB and not
   on the path res5 or res1 depend on to load), but this was not stress-
   tested here.

### Checks to run before each test image (confirmed from the evidence above; follow for every image we flash)
- **Never include an erase/write stage at flash address 0x0 or inside
  0x0-0x28000.** Verify with the same check `make_fs_restore_updater.py`
  already enforces for `--patch-fw`/`--controller-fw` (section 3's
  `allowed` set) — re-run that script unmodified, and additionally inspect
  the final stage table it prints (`main()`'s "wrote ...; stages:" output)
  before running the image, rather than trusting the allowlist silently.
- **Never include a stage at 0x28000-0x33000 (graphics/presets)** unless
  that is explicitly the intent (`--splash`/`--presets`), for the same
  reason: it is adjacent to the boot region and only known-safe because the
  stock updater also touches it routinely (section 4's table).
- **Confirm the main-firmware (res1) image passes the 0xBFFF0 signature
  check** the stock boot program expects (section 2) before relying on
  update mode alone as the safety net — a signature mismatch hangs rather
  than re-offering update mode, so the *only* recovery if that happens is
  the user remembering to power-cycle with both footswitches held, not a
  self-healing fallback.
- **Keep file-system (0x102000+) and settings (0xBF000+) changes inside
  their known sizes** (0x2FE000 and 0x1000 respectively, per both the
  updater table and the firmware's own region table in section 4) — an
  oversized write would spill into the unexplained 0x0C0000-0x102000 gap
  or past the 4 MB flash end, neither of which has been characterized.
- **Treat "can update mode overwrite res5" as yes-by-design** (section 3):
  the safety property we actually rely on is that *our* tooling never asks
  it to, not that the pedal would refuse if asked. Any new or edited tool
  that emits update-mode stages should be checked against the same
  allowlist before it is ever pointed at the real pedal.

## Review (Claude, 2026-10-09)
Checked against the code and the tools:
- **Order confirmed:** c020a4d0 reads the footswitches (c020a4d8/e8 CALLP
  c022ba0c) and the button pattern (c022b968, c022b9c8) and calls update mode
  c0201404 at c020a560 **before** the normal load c022ba40 at c020a568. So a
  bad main firmware (res1) cannot stop update mode from starting. Recovery
  from a res1, preset, file-system or settings fault depends only on res5
  being intact.
- **Our tool never writes res5.** make_fs_restore_updater.py builds its stage
  list from scratch out of file-system, preset and firmware stages only. Its
  allowlist check, previously only on --patch-fw / --controller-fw, now runs
  for every image.
- **Pre-flight tool:** `tools/check_updater_stages.py <updater.exe>` prints
  the stage table and refuses any stage touching [0, 0x28000) or
  [0xbf000, 0xc0000). All nine updaters in build/fw pass. Zoom's own v2.00
  updater does not: it rewrites the boot program (stages 4-5) and the
  settings sector. **An interrupted official Zoom update is the one easy way
  to brick the pedal beyond update-mode recovery.** Run it only when needed,
  on a stable USB connection.
- The 0xBFFF0 signature lives in the settings sector, which our images never
  write, so main-firmware changes cannot fail that check.
- Still open: the res5 code path inside c0201404 (whether it bounds host
  addresses), and where c020a4d0 is called from.

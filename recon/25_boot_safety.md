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

## 4. Flash layout

## 5. Main-firmware reach

## 6. Verdict for pedal tests

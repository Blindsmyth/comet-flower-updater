# S4 - Fault containment: why a bad effect kills USB audio

## Status
running

## Findings

### F1. RA200X's audio callback is a single ~1064 B leaf frame, with the entire kernel inlined into it
**Confirmed.** Extracted the ELF from `build/RA200X.ZD2`'s `DATA` chunk (offset
1220, length 30145, `\x7fELF` magic) to `build/fw_rnd/S4/RA200X_extracted.elf`
and disassembled with `dis6x.exe` to `build/fw_rnd/S4/RA200X_extracted.dis`.
The audio function (`Fx_SFX_CFRA200 @ .text+0`, per `build/RA200X.REPORT.md:5`)
prologue:
```
00000002  STW.D2T1  A11,*B15--[2]   ; 8 B
00000004  STW.D2T1  A10,*B15--[2]   ; 8 B
00000006  STDW.D2T2 B13:B12,*B15--[1] ; 8 B
00000008  STDW.D2T2 B11:B10,*B15--[1] ; 8 B
00000012  STDW.D2T1 A15:A14,*B15--[1] ; 8 B
00000018  STDW.D2T1 A13:A12,*B15--[1] ; 8 B
0000001a  STW.D2T2  B3,*B15--[2]    ; 8 B (return address)
00000024  ADDK.S2   -1008,B15       ; 1008 B locals
```
Total frame = 56 B register-save + 1008 B locals = **1064 B**. This is the
ONLY `ADDK ...,B15` in the whole 30 KB ELF (`grep -n "B15$" ... | grep ADDK`
returns exactly this one line), and the only `CALLP` instructions in the
file are at 0x5558-0x5934 (inside `Dll_CFRA200`, the loader-facing init/entry
code starting at 0x5560 per the report) — none inside the audio function's
body. So `ra_rotor_coeffs`, `ra_block`, `ra_derive` and the whole MNA solver
(`mna_ss.h`) are fully compiler-inlined into one leaf function; the 1064 B is
the entire kernel's stack footprint, not a partial figure. This directly
answers the brief's "no measured frame size" gap.

### F2. RA200X's frame (1064 B) is SMALLER than the proven-safe DR103 frame (1428 B) — the raw-size theory is not supported
**Confirmed, refutes the obvious hypothesis.** Did the same extract+disassemble
on `build/DR103.ZD2` and `build/CE2X.ZD2`:
- DR103 (`build/fw_rnd/S4/DR103_extracted.dis:30`): `ADDK.S2 -1280,B15`.
  1280 B locals; `docs/DSP_RULES.md:56` and `HANDOFF_2026-10-05.md:120` and
  `recon/04_hardware_log.md:43` all independently state DR103's total
  measured stack frame is **1428 B** (1280 + ~148 B register saves), and
  that DR103 was installed, read back byte-identical and play-tested
  **PASSED** on real hardware (`recon/04_hardware_log.md:43`).
- CE2X (`build/fw_rnd/S4/CE2X_extracted.dis:20`): `ADDK.S2 -472,B15`, a much
  smaller frame.
Since DR103's larger (1428 B) frame is proven to work on the pedal with
audio flowing, RA200X's smaller (1064 B) frame cannot by itself be the
reason RA200X gives no audio or crashes USB audio when effects follow it.
This is evidence **against** "stack frame too big" as the direct cause.

### F3. Channel-B write + instance[3] work-buffer state are NOT unique to RA200X — CE2x and Delayx use the identical pattern and are proven safe together with it
**Confirmed.** `effects/ce2x/ce2x.c` and `effects/delayx/delayx.c` both define
their own `work_state()` with the exact same validation
(`(wb[0]&7u)||wb[0]==0u||wb[1]-wb[0]!=wb[2]||wb[2]<sizeof(...)`) against
`instance[3]`, and both write `eff[i+SH_CH_B_OFFSET]` in their output loop —
byte-for-byte the same idiom RA200X uses (RA200X's own header comment at
`effects/ra200x/ra200x.c:4` says so: "as CF CE-2 / CF Delay"). All four
effects I checked (`ce2x`, `delayx`, `hiwatt`/DR103, `ra200x`) have
`"allow_stack": true` in their manifests — the handoff's claim that RA200X
is "the only effect built with allow_stack" (`HANDOFF_2026-10-22_FW_RND.md:20`)
does **not** match the current manifests; noting this as a correction.
Crucially, `HANDOFF_2026-10-22_FW_RND.md:19` reports the bench
`CFMPRE, Delay, Watt, RA200` (Delay in slot 2, with Watt AND RA200 running
**after** it) measured **0 lost frames**. So Delay already proves
ch-B-write + instance[3] + allow_stack + "effects after it" is safe in
combination. This rules out the ch-B/instance[3] pattern itself as the
differentiator; whatever is wrong is specific to RA200X's own kernel body.

### F4. RA200X is the only one of 5 compared kernels with data-dependent (unbounded) loop trip counts — confirmed and not shared by any proven effect
**Confirmed, strongest lead found.** `build/RA200X.LOOPS.md` lists 20 loops
(all in `mna_ss.h`, inlined into the audio function) whose trip count is
reported as `1..?` — i.e. the pipelining tool could not determine a static
bound; trip count depends on runtime data (consistent with an iterative
MNA/linear-system solve that runs until some data-dependent condition).
Counted the same marker across every other built effect's loop report:
```
grep -c "1\.\.?" build/CE2X.LOOPS.md    -> 0
grep -c "1\.\.?" build/DLYX.LOOPS.md    -> 0
grep -c "1\.\.?" build/DR103.LOOPS.md   -> 0
grep -c "1\.\.?" build/MISTRX.LOOPS.md  -> 0
grep -c "1\.\.?" build/RA200X.LOOPS.md  -> 20
```
Every loop in CE2X, Delay(DLYX), DR103 and Mistress(MISTRX) has a
statically-known fixed trip count; RA200X alone has 20 loops whose
iteration count is runtime/data-dependent. `HANDOFF_2026-10-22_FW_RND.md:19`
independently measured RA200X at **14.1k cycles** against an **expected 4k**
(3.5x over) in the one bench where it ran — consistent with a solver that,
for at least some parameter/state combination, iterates far more than the
"typical" case. A sufficiently pathological trip count (certain knob/state
combinations, or the very first "fresh" frame which forces a fuller
derive per `ra200x.c:97` `fresh ? 3 : 1`) could make a single call's cycle
cost balloon much further than the 14.1k already measured, with no static
upper bound provable from the source.

### F5. Memory layout: RA200X's channel-B write sits directly against the next framework ctx buffer, but the USB tap reads a buffer two stages downstream
**Confirmed (addresses), likely (significance).** From `recon/14_effect_memory.md`
section 4 and the generated `sh_params.h` geometry (`SH_FRAMES=16`,
`SH_CH_B_OFFSET=16`, both confirmed in
`build/dr103r/cc/sh_params.h:16-18`, the same generator RA200X used):
the shared audio bus `ctx[1]` = `0x11f037b0` (confirmed, L1D RAM). Channel A
is `eff[0..15]` = bytes `0x11f037b0..0x11f037f0` (64 B); channel B is
`eff[16..31]` = bytes `0x11f037f0..0x11f03830` (64 B) — and
`recon/14_effect_memory.md:167` independently confirms `ctx[2]` (the
"pedal-output accumulator", `SH_CTX_OUT`) = `0x11f03830`, exactly where
channel B ends. So RA200X's channel-B write loop (`ra200x.c:105-116`,
bound to `i<SH_FRAMES`, i.e. strictly `eff[16..31]`) stays inside its own
64 B slice and does not itself overrun into `ctx[2]` — the bound in the C
source is correct and matches the measured layout (no off-by-one found).
However, `docs/USB_AUDIO_TAP_CANDIDATE_2026-10-15.md:22,30` confirms the
USB audio tap reads `0x11f038b0`/`0x11f038f0` — the **final stereo mixdown**
output written by the audio Swi (`11818ba0`) after all 5 slots and the
master-gain stage run — not `ctx[1]`/`ctx[2]` directly. So a bad value in
RA200X's channel B cannot reach USB audio by direct address aliasing; it
can only get there by surviving normal in-place processing through
whichever slots/stages run after it, which is consistent with the
handoff's observation that the failure needs "more effects after it", not
RA200X alone.

### F6. SYS/BIOS Exception module is linked into the firmware; audio Swi and USB Swi are different priorities on the one shared core
**Confirmed.** `build/fw/map/strings.txt` contains, among the resident
strings: `610: c01723d7 To see more exception detail, use ROV or set
'ti.sysbios.family.c64p.Exception.enablePrint = true;'` and `611: c017243b
E_exceptionMax: pc = 0x%08x, sp = 0x%08x.` and `680: c0172b09 Exception`.
These are TI-RTOS/SYS-BIOS boilerplate for the C64x+ `Exception` module,
proving this firmware build links a C674x CPU-exception handler (covers
illegal/misaligned memory access, among others). `recon/18_round3.md:107`
confirms (separately, for USB SOF handling) "USB Swi priority13 and audio
Swi priority15 are different scheduling levels" — i.e. both Swis run under
the same single-core SYS/BIOS scheduler, not isolated cores/processes.
**Not checked (gap, honestly flagged):** I did not locate or trace the
actual exception vector table or the live `Exception_handler` policy
(halt vs. reset vs. resume) in this image — `recon/25_boot_safety.md:107`
independently flags this exact gap ("would require the exception/reset
vector table and is not covered by this reading"). So I can confirm the
*infrastructure* exists but not *what it does* when triggered, nor whether
RA200X's failure mode actually reaches it. If SYS/BIOS's default (with
`enablePrint=false`, as production builds normally ship) is to spin/halt
the CPU on an unrecovered exception, that would explain "crashes the USB
audio driver" as a side effect of a whole-core halt rather than anything
USB-specific — but this is **likely**, not confirmed on this pass.

### F7. L2 audio/task stack region: ~12 KB reserved, RA200X's frame is a small fraction of it
**Confirmed (addresses), uncertain (real headroom at call time).**
`recon/16_audio_hw.md:183` (cited via brief) records: stack region
`0x118134a8..0x11816468` (~0x3000 = 12288 B), startup `B15` set to
`0x118164a4` then aligned down to `0x118164a0` (top of region, stack grows
down from there). `recon/14_effect_memory.md` separately confirmed (via
hardware probe) the stack was observed at `0x11816140` while inside the
audio Swi's effect-call chain — i.e. by the time an effect kernel runs,
~0x2360 (9056 B) of the ~12 KB region is already consumed by Swi/task
scaffolding above it, leaving roughly 0x2CD8 (~11.5 KB) of headroom below
`0x11816140` down to the region's low boundary. RA200X's 1064 B frame is a
small fraction of that remaining headroom under this (single, static)
measurement. **What I did NOT check:** whether this ~12 KB L2 region is
shared concurrently with any OTHER task/ISR stack at the same time RA200X
runs (recon/16 only resolves the startup/task stack, not an exhaustive
tenant list), and whether the single `0x11816140` sample represents the
Swi's typical call depth or its minimum. So "plenty of headroom" is likely
but not proven for every call site.

## Answers
(none yet)

## Not checked / open leads
(none yet)

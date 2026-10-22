# S9 - Bypass path and delay tails (2026-10-22)

Helper: Sonnet 5, job S9 of `docs/helpers/FW_RND_BRIEF3_2026-10-22.md`. Purpose:
can a CF delay keep its tail ringing after it is switched off, as the CN chain
needs? Static analysis only of `build/fw/map/main.dis` and existing repo
studies. No pedal access, no MIDI/USB/updater tools run. Scratch:
`build/fw_rnd/S9/`.

## Status
done (stopped inside the ~2h budget; see "Not checked" for follow-up)

## Findings

### S9.F1 - The 5-slot audio dispatch loop calls every slot's function pointer
### unconditionally every block; the only gate is a single all-5-slots flag,
### not a per-slot bypass/skip (confirmed)
Re-read `11818ba0` (`audio_swi_main`) byte-for-byte, focusing on the loop body
at `11818c00..c38` (the part recon/map/chunk_19.md calls the "5-slot effect
loop"):
```
11818bd8   LDW.D2T2 *+B14[101],B0        ; global "run audio?" flag
11818bec [ B0] BNOP.S1 0x11818c44,5      ; taken -> SKIPS straight to the
                                         ; post-loop stage, i.e. skips ALL 5
                                         ; slots at once if B0=0
...
11818c00   ADDKPC.S2 0x11818c04,B3,0     ; loop top
11818c04   CALLP.S2  0x11818eb0,B3       ; veneer -> c01502cc (F2 below)
11818c08   MV.L1     A4,A10              ; save ctx ptr
11818c0c   LDW.D2T2  *+B11[B10],B5       ; B11=0x118133e0 (slot-callback
                                         ; table), B10=slot index 0..4
11818c12   MV.L1     A10,A4              ; restore ctx ptr as the call arg
11818c16   BNOP.S2   B5,0                ; CALL the slot's function pointer
11818c20   LDW.D2T2  *+B14[102],B4
11818c24   ADD.L2    1,B4,B10            ; slot index += 1
11818c28   CMPGT.L2  5,B10,B0            ; slot < 5 ?
11818c2c [ B0] B.S1   0x11818c00         ; loop while slot<5
```
There is **no comparison or predicate anywhere in this loop that reads a
per-slot enable/bypass state and skips an individual slot's call** - the only
branch out of the 5-iteration loop is the `CMPGT 5,B10` bound, and the only
branch that skips calls at all is the single `[B0]` at `11818bec`, which
(per recon/map/chunk_19.md and recon/16_audio_hw.md:253, both independently
confirmed and now re-checked) is a single flag at `B14[101]` that skips the
**whole** 5-slot loop (e.g. likely a global audio-off/init-not-done guard),
not a per-slot one. So: every slot's process function is called every block
it runs, regardless of whether that slot's effect is "on" or "off" in the UI.
Confidence: confirmed (direct re-disassembly of the cited addresses; the
loop-bound and single-flag-gate claims match the pre-existing, independently
confirmed recon/map/chunk_19.md and recon/16_audio_hw.md:253, which this
session's byte-level read corroborates rather than merely cites).
Commit: this finding.

### S9.F2 - The veneer at 11818eb0 (called just before each slot's call) is
### NOT a bypass decision; it fetches the shared audio service-context
### pointer, passed as the call argument (confirmed, re-verified)
`11818eb0` is a 4-instruction tail-call trampoline:
`MVK.S2 0x02cc,B31; MVKH.S2 0xc0150000,B31; B.S2 B31; NOP 5` -> `c01502cc`.
`c01502cc` = `cfg_get_ptr_11f03b48` (named and confirmed by pre-existing
recon/map/chunk_12.md:40 and chunk_19.md:32; re-verified this session
byte-for-byte). It returns the shared service/audio context pointer
`0x11f03b48` whose word[1] = `0x11f037b0` (the L1D stereo bus). Back in the
loop (S9.F1's listing), the returned pointer (A4) is saved to A10, then
restored to A4 immediately before the indirect call at `11818c16`, i.e. **it
becomes the slot function's own argument** - not a gate on whether the call
happens. Confidence: confirmed (own re-read of 11818eb0..ec0 and
11818c04..16; matches chunk_12/chunk_19's pre-existing attribution).
Commit: this finding.

### S9.F3 - coef[SH_COEFF_BYPASS] (coef[0]) is the project's own ZD2/SH
### kernel-ABI contract: firmware supplies a 0..1 crossfade value, every
### kernel blends dry/wet with it itself (confirmed as documentation/
### toolchain convention; NOT independently re-derived from G1X Four
### disassembly this session - see F5/F6 for what WAS checked in main.dis)
`effects/g1gain/gain.c:19-20` (comment, part of the project's own
stomphacks-derived kernel template, explicitly called out as
"hardware-proven on an MS-70CDR+" - a sibling Zoom pedal on the same
ZD2/SH firmware family, not the G1X Four itself):
```
 *   coeff[SH_COEFF_BYPASS] -> the firmware bypass crossfade, ramps 0..1
```
and the kernel body (`gain.c:78-80`):
```
    sL += 0.002f * (tL - sL);
    float mix = 1.0f + fade * (sL - 1.0f);
    float a = eff[i] * mix;   /* fade=0 -> mix=1 -> unchanged passthrough */
```
`grep -rn "coef\[SH_COEFF_BYPASS\]" effects/*/*.c` shows **every** effect in
this repo (ce2x, cfmaster, cfm_amp, cfm_pre, cftone, clkt, delayx, drv808,
drv808x, dynacx, memprobe, mistrx, muffx, probe10/30, ra200x, ratx, rotx) -
including `effects/delayx/delayx.c:50` - follows this same contract: read
`coef[0]`, do your own dry/wet mix, keep running every block. `SH_COEFF_BYPASS`
is `#define`d to `0` in every generated `sh_params.h`
(e.g. `build/agy4/cc/sh_params.h:21`). `coef` is `instance[1]`, i.e. the
per-slot 0x348-byte buffer at `0x11f00000 + slot*0x348` (recon/14, the
Answers doc's address table, chunk_12.md:37/169 - all pre-existing,
confirmed).
Confidence: confirmed that this is the project's documented/assumed contract
and that every kernel in this repo follows it; **not** independently
re-confirmed against G1X Four firmware disassembly this session (that is
exactly the open question F5/F6 below address and leave open).
Commit: this finding.

### S9.F4 - The per-slot callback-table entry (118133e0+4*slot) is normally
### set only at module load/switch time, to the loaded module's own function;
### a literal "default callback" constant (0x11818de0) exists and is
### installed by a separate function, but its trigger condition was not
### traced this session (likely but incomplete - central open lead)
Three distinct writers of the live 5-slot callback table `118133e0..f0` were
found (one pre-existing + confirmed, two pre-existing + re-verified
byte-exact this session):
1. `c0165f20` (`effect_callback_publish`, pre-existing chunk_16.md:122,
   re-read `c0165f20..48` this session): on an effect module switch, fetches
   the newly-loaded module's own process-function pointer (word+8 of the
   effect-info record via `c012afe0`) and writes it into
   `118133e0 + 4*slot`. Caller `effect_slot_switch_finalize` (`c0133050`).
   This is "load a different effect into this slot", not bypass.
2. `c013f9f0` (`effect_slot_switch_reload`, pre-existing chunk_09.md:42):
   during a slot-switch, temporarily substitutes a **silence** callback into
   **all 5** slots at once (via `c016f660`) while the switch is in progress,
   then proceeds to the real unload/load. A transient "mute everything while
   reloading", not a per-effect on/off toggle.
3. `c0165e80` (`effect_slot_callback_reset`) - re-disassembled byte-exact
   this session:
   ```
   c0165e80   LDW.D1T1  *+A4[0],A4        ; A4 = slot index (deref'd)
   c0165e84   MVK.S1    0x33e0,A5
   c0165e88   MVK.S2    0xffff8de0,B0  )
   c0165e8c   MVKH.S1   0x11810000,A5  ) A5 = 0x118133e0 (table)
   c0165e90   MVKH.S2   0x11810000,B0  ) B0 = 0x11818de0 ("default" ptr)
   c0165e94   STW.D1T2  B0,*A5[A4]        ; table[slot] = 0x11818de0
   ```
   This confirms chunk_16.md:120's claim exactly (the earlier "likely" is now
   confirmed at the instruction level). Its one known caller, per the
   pre-existing fact sheet, is `c0143470` = `effect_param_apply_full`, the
   top-level "apply one edited effect parameter" routine (also named in the
   2026-10-22 Answers doc Q3/Q7 discussion). **I did not trace, in this
   session's time budget, the predicate inside c0143470 that decides whether
   to call c0165e80** (e.g. is it reached only when a parameter edit clears a
   slot to "no effect", or on every parameter edit of some specific field, or
   something else). This is the single most important open thread for
   Q2 of this job ("does the firmware ever call a different bypass
   function") - it is the one concrete mechanism found that redirects a
   slot's callback away from the loaded effect's own code, and whether it is
   reachable by ordinary on/off toggling (as opposed to only by clearing/
   emptying a slot) was not established.
Confidence: confirmed for all three functions' own bodies and table-write
targets (byte-exact reads, all three independently in my own working set and
matching the pre-existing fact sheet's attribution); likely-but-incomplete
for "is #3 the on/off toggle path" - not confirmed either way.
Commit: this finding.

### S9.F5 - What 0x11818de0 (the "default callback") actually does was only
### partially traced; it is a real, reachable instruction sequence (not
### padding), operating on the SAME fixed shared-bus addresses every real
### kernel uses, but whether it is "silence" or "pass dry through unchanged"
### was not conclusively determined (guess-level on the semantics, confirmed
### on the raw bytes)
`0x11818de0` sits inside the same code block as the function at `0x11818d60`
(itself one of `audio_swi_main`'s post-loop-stage helpers, per
chunk_19.md's summary - called directly by `11818ba0` at `11818c48`-area, NOT
via the slot-callback table in that call). Read in full (`11818d60..e5c`):
there appear to be **two** entry points sharing one tail -  `11818d60` (own
prologue, calls `0x11817640` first, then a 16-iteration `BDEC` loop) and
`11818de0` (no stack-frame prologue, starts straight into the same kind of
16-iteration loop body). Both loops touch fixed addresses
`0x11f037ac/0x11f037b0` (the already-confirmed shared stereo bus - same for
every slot, per the 2026-10-22 Answers doc Q8) and `0x11f03de0`/`0x11f03e20`
(not characterized by any prior recon document; my own read suggests these
hold a 16-entry per-sample array and a pointer-to-pointer respectively, i.e.
possibly a per-block ramp-curve table, but I could not fully resolve the
register sequencing (A3 appears reused for both a pointer and a loop count
within a few cycles at `11818de4..df4`) with confidence inside the time
budget, and C6000 delay-slot/parallel-bar misreads are exactly the pitfall
the brief warns about. I am **not** claiming this is "the" bypass-silence
stub; I am reporting that it is reachable, real code, touching the shared
bus, and that its exact effect (mute vs. unity passthrough vs. something
else) is unresolved.
Confidence: confirmed (bytes, reachability, operand addresses); guess (what
it semantically does to the audio).
Commit: this finding.

### S9.F6 - Two concrete candidate "coef[0] producer" mechanisms were
### checked and ruled out (confirmed, by direct disassembly)
- `gain_ramp_up`/`gain_ramp_to_zero`/`gain_ramp_variant1`/`gain_ramp_variant2`
  (`1180a4a0`/`1180a4c4`/`1180a4e8`/`1180a50c`, via `audio_gain_ramp_div`
  `1180a2a8`) were disassembled directly. `gain_ramp_up` targets a fixed
  address built from `MVK 0xfffface8,A4; MVKH 0xc0110000,A4` = **0xc011ace8**,
  ramping it to `1.0f` (`MVK 127,B4; SHL B4,0x17,B4` = `0x3f800000`).
  `gain_ramp_to_zero` targets the **same** `0xc011ace8`, ramping to `0.0f`.
  `gain_ramp_variant1`/`_variant2` target the adjacent fixed word
  `0xc011ace4` the same way. These are **fixed global words**, not inside the
  per-slot `0x11f00000 + n*0x348` table, and sit in the same `c011ac..`
  cluster as `c011acd4`/`c011acd8`, which pre-existing recon/map/chunk_01.md
  already ties to the **expression-pedal level** ramp
  (`explevel_save_and_max`, "Level = word B14[118]", `audio_cfg_gain_ramp_
  apply` ramping `c011acd4` from a curve table). Ruled out as the per-effect
  bypass fade.
- The brief's "ZD2 BYPASS/BPS blocks (strings near c0129b40)" lead: grepped
  `build/fw/map/strings.txt` for every `BYPASS`/`BPS` occurrence
  (`c0176a88/94/98`, `c017de68`, `c017ded8`, `c017f5a7/ae/d4/db`,
  `c0181668/6f`) - none are near `c0129b40` (they sit in `c0176xxx..c0182xxx`,
  a ~0x4D000-byte-distant region; the brief's parenthetical does not hold).
  Traced the reference at `c012a9b0/c012a9cc` (the `"Bypass"`/`"BYPASS.ZD2"`
  pair) via `build/fw/map/refs.txt`: it is inside `patchlist_screen_build`
  (`c012a8bc`), already identified and confirmed by pre-existing
  recon/map/chunk_04.md:106 as the **MainApp patch-file browser screen**.
  `"Bypass"`/`"BYPASS.ZD2"` is a **factory patch FILENAME** shown in that
  file list (alongside `"FLST_SEQ.ZT2"`, `"*.*"`, `"GUARDZDL.ZT2"`) - a
  preset literally named "Bypass" (presumably an all-through default patch),
  not any part of the per-sample audio bypass mechanism. Ruled out.
Confidence: confirmed (both ruled out by direct address/target tracing, not
by assumption).
Commit: this finding.

### S9.F7 - Stock DELAY_3S.ZD2's own "on/off"-named callback is an internal
### per-tap mute parameter, not firmware bypass; its main process function's
### dry/wet mix instruction was not reached in the time budget (partial)
Extracted the ELF from `build/bench/stock/DELAY_3S.ZD2`'s `DATA` chunk
(offset 476, length 15333, `\x7fELF` magic, same method S4 used for RA200X)
to `build/fw_rnd/S9/delay3s_extracted.elf` and disassembled with
`C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS/bin/dis6x.exe` (per
`tools/make_controller_fw.py:34`'s `ZOOM_TI_CGT` default) to
`build/fw_rnd/S9/delay3s_extracted.dis` (symbol names intact). Function list
includes `Fx_DLY_Delay_TapOpen`, `Fx_DLY_Delay_tapmuteMute/Open`,
`Fx_DLY_Delay_time_edit`, `_onf`, `_mix_edit`, `_fb_edit`, `_init`, and the
main body `Fx_DLY_Delay` (0x620..0xa60, 0x440 bytes). Read `Fx_DLY_Delay_onf`
(0x354..0x46c) in full: it is a parameter-edit callback that reads an
edited value and calls `Fx_DLY_Delay_tapmuteMute` or `_tapmuteOpen`
depending on it - this is the delay's **own internal tap-mute knob**
edit handler (stock effects use their own original Zoom edit-callback
ABI per parameter, distinct from our ZD2/SH toolchain's synthetic
`coef[]` convention used by `effects/*/*.c` in this repo), not a firmware-
level bypass hook. I did not reach the main `Fx_DLY_Delay` process body's
output/mix stage in the time remaining, so I cannot say whether/where it
reads a coefficient at the same byte offset our `coef[SH_COEFF_BYPASS]`
convention uses. Marking this "not checked" rather than guessing.
Confidence: confirmed (onf/tapmute identification); not checked (the
process body's coef[0]-equivalent, if any).
Commit: this finding.

## Answers

### Is an OFF effect's audio function still called each block?
**Likely yes**, with the caveat in F4 left open. S9.F1 (confirmed) shows no
per-slot skip exists in the dispatch loop itself - every slot's current
function pointer is called every block, gated only by one all-5-slots flag.
S9.F4 (likely but incomplete) shows the callback-table entry is normally set
once at module-load time and otherwise undisturbed; the one mechanism found
that *can* redirect a single slot's callback away from the loaded module
(`effect_slot_callback_reset`, `c0165e80` -> installs `0x11818de0`) has an
unconfirmed trigger (`effect_param_apply_full`, `c0143470` - predicate not
traced). If that path is NOT the ordinary on/off toggle (my working
hypothesis, given the project's own ZD2/SH ABI is explicitly built around a
coef[0] crossfade that implies the kernel keeps running), then "yes, always
called" is the practical answer for every slot whose effect is simply
switched off via the normal UI/MIDI path. Patch-wise: nothing to patch if
this hypothesis holds - the call already happens.

### How is coef[SH_COEFF_BYPASS] (coef[0]) produced - a ramp over how many
### blocks, written where, by which function?
**Not found** in the G1X Four firmware this session. S9.F3 establishes what
coef[0] is *for* (confirmed as this project's/toolchain's own documented
contract, hardware-proven on a sibling pedal) but I did not locate, in
`build/fw/map/main.dis`, the specific function that writes a ramped float
into `0x11f00000 + slot*0x348 + 0` at runtime. Two plausible candidate
families were checked and ruled out (S9.F6): the `gain_ramp_*` family (wrong
target - fixed globals `0xc011ace4/e8`, tied to the expression-pedal level,
not per-slot) and the `BYPASS.ZD2`/"Bypass" strings (wrong subsystem - the
patch-file browser, not audio). The `0x11818de0` default-callback body
(S9.F5) touches `0x11f03de0`/`0x11f03e20`, addresses in the same `0x11f03xxx`
region as the confirmed shared service-context struct
(`cfg_get_ptr_11f03b48` returns base `0x11f03b48`; word[1]=`0x11f037b0`) -
this is a plausible lead for a per-block ramp-curve table, but NOT the
per-slot `0x11f00000+n*0x348` coefficient table S9.F3 is about, and I could
not resolve its exact semantics (F5). Patch-wise: with the producer
unlocated, no patch site can be given; this is the clearest "needs a follow-
up pass" item.

### Does the firmware ever skip the call, or call a different (bypass)
### function?
**Skip: likely not** for an ordinary on/off toggle (S9.F1 - no per-slot skip
predicate found in the dispatch loop). **Call a different function: a real
mechanism exists** (`effect_slot_callback_reset` installing `0x11818de0`,
S9.F4) **but whether ordinary UI/MIDI on/off toggling reaches it is not
confirmed** - its only known caller is `effect_param_apply_full` (`c0143470`),
and the exact condition under which *that* function calls the reset was not
traced in the time budget. The brief's suggested "ZD2 BYPASS/BPS blocks" lead
(S9.F6) is ruled out - those strings belong to the patch-file browser, not
the audio-dispatch bypass path.

### Can a kernel implement a tail (process with input muted while coef[0]=0)?
**Likely yes, with the current firmware, given the project's own kernel
contract** - no patch needed under the most-supported reading of the
evidence. Reasoning: (1) S9.F1 confirms the dispatcher calls every slot's
function every block with no per-slot skip; (2) S9.F3 confirms the project's
own kernel ABI gives every kernel direct access to `coef[0]` and leaves the
dry/wet mix entirely up to the kernel's own code (firmware does not impose
the mix, it only - per the toolchain's documented contract - supplies the
ramped value). Combining these: a delay kernel is called every block
regardless of its own bypass state, with the live input still on the shared
bus (nothing found that mutes/zeroes the bus for a "bypassed" slot - the bus
is literally the same memory for every slot, fixed, per the Answers doc Q8).
So a delay kernel can simply choose, in its own code, NOT to follow the
instant "dry when fade=0" convention: keep writing/reading its own delay
line every block exactly as the gain-ramp family of stock helper functions
do with other global ramps, and instead of blending straight to dry the
instant fade hits 0, hold the wet output (or cross-fade it out slowly on the
kernel's own schedule, independent of coef[0]) for as many blocks as desired
after the user switches the effect off. **This is a kernel-authoring choice,
not a firmware patch**, under the evidence found. The one caveat (not fully
closed, see F4) is whether the firmware ever redirects the slot's callback
pointer away from the kernel entirely on an ordinary on/off toggle (which
would defeat this regardless of kernel code) - not confirmed either way this
session, but the balance of evidence (the project's own effects, including
`effects/delayx/delayx.c`, already assume and are built against the coef[0]
contract, consistent with "the kernel keeps running") argues against it.
If a future finding does confirm c0143470 redirects the callback on ordinary
bypass, the smallest patch would be at the `CALLP 0xc0165e80` call site
inside `c0143470` (not yet located precisely - would need that trace first):
either NOP the call (2-4 instructions, keeps the loaded kernel's pointer in
place for that slot always) or invert whatever predicate guards it so it is
only reached when the slot is truly emptied, not merely toggled off. Risk:
low if the predicate is cleanly isolated; unknown without having traced it.

## Not checked / open leads
- The exact predicate inside `effect_param_apply_full` (`c0143470`) that
  decides whether to call `effect_slot_callback_reset` (`c0165e80`) - the
  central open question for this job. Next step: read `c0143470` in full
  (it is "~100 lines" per chunk_09.md:157, already partially read by a prior
  helper) looking specifically for the `CALLP 0xc0165e80` site and the flag
  test guarding it.
- The exact semantics of `0x11818de0` (silence vs. unity passthrough vs.
  something else) - S9.F5, register-sequencing concerns noted, not resolved.
- What `0x11f03de0`/`0x11f03e20` actually hold (per-block ramp-curve table?
  part of the shared service-context struct past `11f03b48`?) - not
  characterized by any prior recon document either; worth a dedicated look
  given it may be adjacent to, or even be, the real coef[0] producer.
- The G1X Four's own stock `Fx_DLY_Delay` (DELAY_3S) main process body
  (0x620..0xa60 in `build/fw_rnd/S9/delay3s_extracted.dis`) was not read for
  its output/mix stage - would show whether the ORIGINAL Zoom delay code
  also honors a coef[0]-equivalent, independent of our own toolchain's
  documentation claims. TPEC3_3S not touched at all (time budget).
- Whether `B14[101]` (the single all-5-slots gate at `11818bec`) is ever
  cleared per-slot by some other mechanism not visible from inside
  `11818ba0` itself (e.g. a per-slot variant of the same global, which would
  contradict S9.F1) - not checked; S9.F1's "not per-slot" conclusion rests
  on this one flag's read site only being a single scalar word, not an
  array, which was confirmed (`LDW *+B14[101],B0`, a single scalar load) but
  the global's own writers were not enumerated this session.


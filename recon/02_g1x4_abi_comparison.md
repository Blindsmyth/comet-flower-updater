# 02 — G1X Four vs MS Plus: is the stomphacks DIY ABI the same?

Date: 2026-10-04. Specimens: `NYC_MUFF.ZD2` (v1.40) and `THEVIBE.ZD2` (v1.50)
from a G1X Four, compared with `DIYGAIN.ZD2` built by
[thammer/stomphacks](https://github.com/thammer/stomphacks) (commit ebd5ced),
which is hardware-proven on MS-70CDR+ / MS-50G+. Disassembly with TI CGT 8.5.0
`dis6x` / `ofd6x`.

**Verdict: the code ABI matches on every point checked. The container and the
display images differ. Nothing yet proves the G1X Four will load a DIY effect.
That needs a hardware test.**

## Same (code-level ABI)

| Check | G1X Four stock | stomphacks DIY (MS+) |
|---|---|---|
| ELF | ET_DYN, EM 140 (C6000), ISA C6740, EABI | same |
| Compiler | CGT 7.3.4 (Tag_Producer 8.4.5) | CGT 8.5.0 |
| Relocations | ABS32, ABS_L16, ABS_H16 only | same (the only types the MS+ loader accepts) |
| Entry stub `Dll_<Name>` | writes count byte → `A4[0]`, param table → `A4[1]`, image info → `A4[3]` | identical |
| Param table | 56-byte records: OnOff, effect-name record (init + audio fn), then knobs | identical layout |
| Init | memcpy defaults via ctx+172, memset state via ctx+176, then calls every edit handler | identical |
| Edit handler | `get_param` via ctx+160 with (instance[0], index) | identical |
| Audio fn | A4 = instance: [1] coeff table, [2] state; B4 = ctx; reads bus from ctx[1] | identical |
| VOL knob | flags 0x16 (stock VOL curve) | 0x16 for `"curve": "stock_vol"` |

Stock audio code also reads ctx[7] and ctx[8] (unknown). DIY kernels must keep
to ctx[1] (stomphacks: other slots can freeze the pedal).

Not yet confirmed on the G1X Four: block size of 16 frames × 2 channels and a
44.1 kHz rate. The stock audio code is hand-scheduled SPLOOP asm, so these are
plausible but unproven.

## Different

| Item | G1X Four stock | DIY (MS+) | Risk |
|---|---|---|---|
| `target` @0x0C | `0x07` | `0x90` | The pedal may refuse to list a non-G1 effect. Retarget needed. |
| Header 0x10..0x58 | 5–7 non-zero bytes (`01`, `80` words at 0x10/0x14/0x18/0x28/0x38) | all zero | Unknown semantics. |
| `ICON` block | 182-byte 1-bpp BMP, 23×30 | 936-byte colour frame (+ separate `.ZIC`) | The G1X Four needs a 1-bpp BMP icon. |
| INFO text | `DRVDRIVE`, `MODMOD.` | empty | Probably cosmetic. |
| Image list in ELF | 23×32 (or 23×30) screen pic, **20×10 category icon**, optional 24×22 add/del icon | one blank 24×30 pic | **The firmware may dereference a missing category icon → crash.** Generate a G1-shaped list. |
| 16-byte trailer | non-zero, not an MD5 of any block | zeros | MS+ ignores it (zeroed builds load). Unknown on G1. **A signature here would block everything.** |
| DSP budget | stock loads 34.86 (NYC Muff), 24.40 (TheVibe) | budget 270 on MS-70CDR+ | G1X Four budget unknown; find it from a patch with several stock effects. |

## Implications for "wipe effects to free DSP"

The DSP budget is enforced **per patch**. The pedal sums the declared
`dspload` of the effects in the chain. Uninstalling effects frees flash and
list slots, not DSP. A single heavy custom effect has to fit in one patch's
budget.

## Next steps

1. Read-only backup of the pedal (all ZD2 + `FLST_SEQ.ZT2`) → run
   `zd2 audit` on ~100 G1 effects to settle the invariants above (header
   words, image list shape, trailer, target bits, loads).
2. G1 profile for the stomphacks generator: target bits, G1 header words,
   1-bpp 23×30 BMP icon, G1-shaped image list with a category icon.
3. First hardware test = the gain effect only, retargeted, following
   stomphacks SAFETY.md (autosave OFF, never save, never power-cycle
   mid-transfer). The stomphacks installer is MS+-only (target bit and stock
   catalogue checks), so it needs a G1 variant first.

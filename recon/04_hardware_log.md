# 04 — Hardware test log (G1X Four)

Every write to the pedal, in order. Wire logs: `build/pedal-logs/wire.log`.

| Date | Stage | File | Result |
|---|---|---|---|
| 2026-10-04 | backup (read-only) | all 114 files | OK, 0 transfer errors, session closed cleanly |
| 2026-10-04 | 1: write test | G1GAIN.ZD2 (4535 B, id 07000f81) | **PASSED**: uploaded, read back byte-identical, deleted, verified absent; FLST_SEQ.ZT2 byte-identical before and after. Free flash 8180 B before. |

Stage 1 shows that the stomphacks file-transfer engine (`tools-pedal/file_session.py`,
device ID 0x6E) works unchanged on the G1X Four for upload, readback and delete.
It says nothing yet about whether the pedal *loads* or *runs* the effect. That
is stages 2 (install into the effect list) and 3 (play test).
| 2026-10-04 | free flash | ORG1201U.ZD2 (stock ORG120 amp, 59237 B) | **PASSED**: verified identical to backup, deleted, FLST entry set installed=0 (1-byte change), list read back identical, 0 retries. Free flash 8180 B → 69530 B. First FLST rewrite on G1X Four. |
| 2026-10-04 | 2: install | G1GAIN.ZD2 | **PASSED**: uploaded, read back identical; FLST gains one installed entry in group 7 (SFX); list read back identical, 0 retries. Copy: `build/pedal-logs/FLST_after_install.ZT2`. |

To restore ORG120: upload `backup/2026-10-04/files/ORG1201U.ZD2` and set its
installed byte back to 1 (`pedal_g1.py` can be extended to do this). Its patches
referencing it will work again.
| 2026-10-04 | 3: play test | G1 Gain in an unsaved patch, AUTO SAVE off | **PASSED** (owner, by ear): pedal booted with the new effect list, G1 Gain listed and selectable, audio passes, Level lowers and raises as expected (80→20 is a much larger change than 80→100, matching the stock VOL curve: −12 dB vs +3.5 dB), no faults. |

**Result: first self-compiled DSP effect confirmed running on a G1X Four.** The
stomphacks ABI holds on the G1 Four family once the container is retargeted
(recon/02, recon/03).
| 2026-10-04 | patch backup (read-only) | all 50 patches (760 B each, 0x46 read) | OK. Patch 40 uses UK30A_1U (shipped uninstalled); the owner selected it: loads, missing effect simply skipped, no fault. No patch used ORG120. |
| 2026-10-04 | wipe | 86 stock effects (all but G1GAIN) | **PASSED**: one FLST rewrite (86 installed bytes → 0, verified, 0 retries), then 86 files deleted and verified absent; FLST re-verified after. Free flash 2,433,550 of 3,087,950 B. Copy: `build/pedal-logs/FLST_after_wipe.ZT2`. |

Restore: every effect file is in `backup/2026-10-04/files/`, the original list is
`FLST_SEQ.ZT2` there, and the patches are in `backup/2026-10-04/patches/`.
| 2026-10-04 | blank patches | patch 50 (test), then 1–49 | **PASSED**: blank patch built from factory patch 30 (5 slots id 0x0, enabled; 13 bytes changed). The pedal stored it normalised: 38 bytes in the per-slot parameter area (offsets 300–436) zeroed. The owner confirmed patch 50 empty, no alerts. The pedal's stored copy (`build/BLANK_CANON.ZPTC`) was then written to 1–49, each read back byte-identical. All 50 patches blank. |

Empty-slot encoding: id `0x0` with the EDTB entry `01 00…` (enabled bit only).
Id `0x1` is not empty: it is the second half of a double-width ("1U") effect.
| 2026-10-04 | install | DRV808.ZD2 "Green 808" (14401 B, id 03000f81, DRIVE) | **PASSED**: write test (upload, readback, delete) then install; FLST rewritten and verified, 0 retries. Port of Comet Flower DriveMobileCore; host comparison vs original −117.8 dB worst case. Play test pending. |
| 2026-10-04 | replace | DRV808.ZD2, G1GAIN.ZD2 | **PASSED**: rebuilt with a drawn 23x30 slot picture (LCD page format) in place of the blank stomphacks one; overwritten, read back identical, FLST unchanged. The owner reported the slot showing as bypassed/blank until selected (patch 41). |
| 2026-10-05 | play/display test | patch with G1 Gain + Green 808, after a full power cycle | **PASSED** (owner, photos): both slots show the drawn pictures ("G1 GAIN", "GREEN 808") straight from boot. The earlier "1 BYPASS" / blank slot came from the blank image-list picture the stomphacks scaffold ships. **The G1 needs a real slot picture (image 0, LCD page format).** |
| 2026-10-05 | install | PROBE30.ZD2 (07000f82, dspload 30), PROBE10.ZD2 (07000f83, dspload 10) | **PASSED**. Diagnostics: Load = knob × 1600 cycles/block (8-cycle dependent MPYSP+ADDSP loop), Tone = 440 Hz at 44.1 kHz. Measurements pending. |
| 2026-10-05 | install | DRV808X.ZD2 "Green 808X" (10253 B, id 03000f82, DRIVE, dspload 80, state 316 B) | **PASSED** write test + install. First DIY effect with state > 192 B (G1 stock drives use 392 B undeclared). Estimated ~74k cycles/block. Play test pending, after the probe CPU measurement. |
| 2026-10-05 | probe test | Probe 10, then Probe 30, Tone on, Load raised | **Tone 439.98 Hz (44.1 kHz confirmed).** Pedal **froze at Load 60 / 64** (~96-102k cycles/block): the tone kept playing clean, but the pedal took no input until power-cycled. Recovered both times by power cycle, nothing saved. See recon/06. |
| 2026-10-05 | play test | DRV808X "Green 808X" in an unsaved patch, AUTO SAVE off | **PASSED** (owner, by ear, through the interface): plays with no freeze. Sound very close to Green 808 ("almost exact"); level sounds lower through the interface (not yet compared at equal gain). |
| 2026-10-05 | cost test | Green 808X + Probe 10 in one unsaved patch, Load raised | Froze at **Load 14** (22.4k cycles). 808X real cost ≈ 96k − 22.4k = **≈74k cycles/block**, matching the static cl6x estimate. Recovered by power cycle. |
| 2026-10-05 | replace | DRV808X.ZD2 "Green 808X" table-solver build (38518 B, same id 03000f82 / 1.00, dspload 80, 27 KB const_blob) | **PASSED**: written, read back identical, effect list unchanged. Static estimate ≈17k cycles/block. Play test and Probe 10 cost test pending (expect freeze ≈ Load 49). |
| 2026-10-05 | writetest + install | DR103.ZD2 "DR103" Hiwatt DR103 (28835 B, id 04000f81, amp group, dspload 80, state 320 B, stack frame 1428 B, 4 KB const_blob) | **PASSED** both: read back byte-identical, effect list rewritten and verified. Play test and Probe 10 cost test pending. |
| 2026-10-05 | play test | DR103 in an unsaved patch | **FAILED by ear**: "digital glitch" sound. With DR103 + Probe 10 the Probe Load went to 100 without a freeze (alone it froze at 60), Tone toggled fine. Suspected CPU overrun; DR103D built to measure. |
| 2026-10-05 | writetest + install | DR103D.ZD2 "DR103D" diagnostic (29201 B, id 04000f82): DR103 processing timed with TSCL (read only), output = triangle at cycles/100 Hz, 0.5 s whole / 0.5 s derivation | **PASSED** both. Recording pending. |

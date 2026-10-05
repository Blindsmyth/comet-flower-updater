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

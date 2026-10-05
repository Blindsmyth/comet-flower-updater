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

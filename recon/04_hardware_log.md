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

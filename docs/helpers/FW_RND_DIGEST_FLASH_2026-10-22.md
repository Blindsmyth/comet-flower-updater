# F1 - Prior-knowledge digest

## Status
running

## Findings

### Q1: Slot limit and effect list
- "Header 0x58: `01`, or `02` for double-width effects (1U amps, 47/50-px icons) | **slot count**; `01`" (`recon/03_g1x4_corpus_audit.md:23`, no addresses named, confidence: confirmed invariant across 87 stock effects).
- "Empty-slot encoding: id `0x0` with the EDTB entry `01 00…` (enabled bit only). Id `0x1` is not empty: it is the second half of a double-width ('1U') effect." (`recon/04_hardware_log.md:33`, no addresses named, confidence: confirmed).
- "Patch slot count: the effect header already carries a slot count (byte 0x58) and patches already mark the second half of a double-width effect (id 0x1), and the declared dspload drives 'Process Overflow'." (`recon/10_firmware_capabilities.md:40`, no addresses named, confidence: deduced / likely).
- "Variant 1: Monolithic 5-Slot Kernel (`CFM5`) - Condition: If the pedal loads header `0x58 = 5` and provides unified patch control. Slot Usage: Claims all 5 slots (header 0x58 = 5, `g1_slots: 5`)." (`docs/CF_MASTER_DESIGN.md:90-91`, no addresses named, confidence: hypothetical design).
- "Variant 2: Split Multi-Slot Rig (`CFM_PRE` 2-Slot + `CFM_AMP` 3-Slot) - Condition: If the pedal enforces a 2-slot maximum, or if 12 knobs are the maximum." (`docs/CF_MASTER_DESIGN.md:103`, no addresses named, confidence: hypothetical design).
- "CF M5: CFM5P.ZD2, Header 0x58 = 5 (no stock effect does this); CF M2: CFM2P.ZD2, Header 0x58 = 2 (as the stock 1U amps)" (`docs/CF_MASTER_PROBE_2026-10-19.md:17-18`, no addresses named, confidence: confirmed test configurations).
- "CF M2 (2 slots): loads and is listed. With Mode 1 set the report decodes cleanly... 1.00 calls per block... single instance... work buffer 529,200 B at `0xc0226000`, slot 0... code `0xc01f41e0`, slot region 0; knobs 1-12 read back... all 12 knobs reach the DSP." (`docs/CF_MASTER_PROBE_2026-10-19.md:63-69`, addresses `0xc0226000`, `0xc01f41e0`, confidence: confirmed on hardware).
- "CF M5 (5 slots): NOT offered by the pedal. Absent from the effect list on Updater 24 and 25 (CF M2 and CFM Pre are listed)." (`docs/CF_MASTER_PROBE_2026-10-19.md:70`, no addresses named, confidence: confirmed on hardware).
- "Still open: code/const heap size for a multi-slot effect, the maximum slot count the pedal lists (3? 4?), and how many slots CF M2 visibly occupies. Consequence: a single 5-slot CF Master cannot be selected as built." (`docs/CF_MASTER_PROBE_2026-10-19.md:71-73`, no addresses named, confidence: open).
- "A patch has 5 slots (`tools/patch_g1.py`, `g1presets.py`), and the pedal refuses a patch whose declared dspload sum reaches 230. Header byte 0x58 (slots used) from the built ZD2s: `DYNACX`, `MUFFX`, `MISTRX`, `CE2X`, `DLYX`, `DR103`, `RA200X`, `RATX`, `DRV808X` = 1." (`docs/CN_CHAIN_SPEC_2026-10-21.md:49`, no addresses named, confidence: confirmed).
- "`0x0C` (4 bytes): Slot count: 5 in every factory record." (`recon/08_factory_presets.md:32`, no addresses named, confidence: confirmed).
- "All 50 backup ZPTC files are 760 bytes, but their slot counts differ... Do not infer slot count from file length." (`recon/08_factory_presets.md:70-73`, no addresses named, confidence: confirmed).
- "`c0147fc0` (`effect_slot_count_after`): counts how many per-slot records (stride 84, table `0x1181159c`) from index A3+1 to B1 have field offset+84 equal to 1" (`recon/map/chunk_10.md:79`, address `c0147fc0`, table `0x1181159c`, confidence: confirmed).
- "`c0148008` (`effect_slot_count_before`): sibling of effect_slot_count_after: counts matching slot records walking BACKWARD from A4-1 down to 2" (`recon/map/chunk_10.md:80`, address `c0148008`, confidence: confirmed).
- "`c014811c` (`effect_slot_reorder_apply`): refreshes all 5 slot indicators (loop bound CMPGT 5,A12; calls cfg_table_ptr_11f03ad0 + c016f660), then copies two 84-byte per-slot parameter records" (`recon/map/chunk_10.md:82`, addresses `c014811c`, `c016f660`, `0x11f03ad0`, `0x11811598`, `0x11811ca8`, confidence: likely).
- "`c01483ac` (`effect_slot_reorder_dispatch`): drives effect_slot_reorder_apply (`c014811c`) in two bounded loops bracketed by effect_slot_count_before (`c0148008`) and effect_slot_scan_1548 (`c0148354`)" (`recon/map/chunk_10.md:84`, addresses `c01483ac`, `c014811c`, `c0148008`, `c0148354`, confidence: likely).
- "`c0148408` (`effect_slot_reorder_ramp_apply`): top-level 'move/insert an effect in the 5-slot chain with gain ramping' handler... under a bios_sem_pend/post (B14[155]) lock" (`recon/map/chunk_10.md:85`, address `c0148408`, confidence: likely).
- "Effect-category dispatch table at `0xc0183eac..0xc0183f08` (24 x 4-byte slots, indices 0-23), read by fx_cat_edit_dispatch (`c0148f34`)" (`recon/map/chunk_10.md:189`, addresses `0xc0183eac`, `c0148f34`, confidence: confirmed).
- "`c0141ac8` (`effect_slot_list_update`): calls patchlist_helper3 (`c012b2c4`) and midi_apply_value_cascade_b (`c012edcc`) -- likely updates a patch/effect list entry and cascades a MIDI value change" (`recon/map/chunk_09.md:120`, addresses `c0141ac8`, `c012b2c4`, `c012edcc`, confidence: confirmed).
- "`c0141b74` (`effect_slot_scaled_update`): validates an index via bound_check_lt4 (`11805d84`), scales it via fixed_scale_mul_84_div (`c0130d28`), then calls effect_slot_list_update (`c0141ac8`)" (`recon/map/chunk_09.md:121`, addresses `c0141b74`, `11805d84`, `c0130d28`, `c0141ac8`, confidence: likely).
- "`c0130ab4`: Blank 'empty' PTCF constructor... empty slot marker id 0x0 / 0x1" (`docs/helpers/PATCH_STORE_ARGON_2026-10-17.md:124`, address `c0130ab4`, confidence: confirmed).
- "`118074b0`: Calls `11806450(0x11811598)` to sanitize slot count / order" (`docs/helpers/PATCH_STORE_ARGON_2026-10-17.md:157`, addresses `118074b0`, `11806450`, `0x11811598`, confidence: confirmed).
- "`FLST_SEQ.ZT2`: 8502 bytes (same size as MS Plus), 148 entries, 87 installed... Groups 1–9 and 11." (`recon/03_g1x4_corpus_audit.md:11`, no addresses named, confidence: confirmed).
Coverage: partly covered (header 0x58 slot count semantics, 1U double-width slot reservation with ID 0x1, and hardware behavior where header-2 loads but header-5 is omitted from the list are documented; specific firmware routine filtering/hiding header-5 in the UI list is not yet located).

## Answers

## Not checked / open leads

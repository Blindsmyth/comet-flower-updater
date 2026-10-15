# Notes for Flash 3.8 (running log; newest entries at bottom of "Log")

Read first: `HANDOFF_2026-10-14_LEAD.md` (real project state), then this file.
**DO_NOT_FLASH remains in effect.** Never write to the pedal. Never commit `.agents/` or `bridge/`.

## Rules of engagement (learned the hard way)
- Python: `.venv\Scripts\python.exe`. Tests:
  `.venv\Scripts\python.exe -m pytest tests tools/test_usb_audio_proto.py -q`
  Baseline: **160 passed, 471 subtests passed.** Never leave it red.
- Controller candidate build (offline, safe):
  `.venv\Scripts\python.exe tools/make_controller_fw.py --out build/controller/<name>.bin`
  Expect 7 `hook ...` lines then `wrote ...`. Delete scratch outputs afterwards.
- A new asm/C section needs BOTH a `--retain` line and a placement line in
  `firmware/controller/controller.cmd` (omission caused `KeyError: 'controller_worker_wait'`).
- Doc claims must be evidence-tagged (address + bytes/disassembly). No "proved" without it.
- Hand off to Argon (`.agents/rules/argon-bridge.md`) only for heavy RE or DSP transpile.
- Do NOT redo broad stock call-graph audits; the next work is bounded (below).
- Commit small, with a message saying what was verified.

## Log
### 2026-10-14 (Claude session)
- Resumed from HEAD `feec933`. Previous agent's uncommitted work reviewed: controller worker-wait tail-call
  thunk, usb_audio `set_alt`/`copy_descriptors` bounds, host_harness, test_usb_audio_proto.py,
  USB_TEARDOWN_DECISION doc. Fixed controller.cmd (missing worker_wait section). Build + 160 tests pass.
- Thunk review (done): stock site `c0149d4c` = CALLP `c014a0cc` with parallel B6=B15+4, A6=1; A4=event
  (`*B14[90]`), B4=3 mask, A8=B4-4=-1 timeout; returns to `c0149d56`, which reloads bits from `B15[1]`.
  Thunk clobbers only A0, A8, B31 (+B3 in controller mode); stock mode branches with args and B3 intact.
  Pump args (A4 event, B4 bits ptr, A6 wait result) match `controller_worker_pump(u32, volatile u32*, int)`.
  Looks correct. Not yet verified on hardware (not allowed).

## Next steps (in order)
1. Commit the reviewed work (check `git log` — may already be done).
2. Implement the *diagnostic ownership candidate* described at the end of
   `docs/helpers/USB_TEARDOWN_DECISION_2026-10-14.md`: fixed-size memory trace (no printing in Hwi) recording
   teardown word 0 type-19 receipts, queue snapshots, poll expiry, sticky fault code. Keep it a separately named
   candidate; do not claim it fixes ownership.
3. Update `HANDOFF_2026-10-14_LEAD.md` "Continue from this point" and add a line here.
4. Owner-run MIDI test prep only after offline gates close. Flashing is the owner's decision.

### 2026-10-14 later (Claude)
- Committed as 9a76baa (HEAD). Step 1 done. Step 2 is NOT started: the teardown doc itself says patch feasibility review must come first. Do that review before writing code: pick hook sites in the stock abort routine (c0120744..0750 recycles the entry; poll at c011faa0; Hwi consumer c011fcb8..fcc2) and confirm each patch site has room for a CALLP (4 bytes, parallel bits preserved, see HOOKS in tools/make_controller_fw.py). Write findings to docs/helpers/ before coding. Trace buffer must live in the controller image (16 KiB at c01a0000, currently 2880 bytes used) or .ctl_state.


- Step 2 prerequisite review was handed to Argon via bridge/to_argon.md (clipboard). When bridge/from_argon/ has a response, ingest per .agents/rules/argon-bridge.md: execute its FLASH_3.8_ACTION_PLAN, spot-check its Evidence addresses against build/fw/map/main.dis, then run tests.


- Browser automation of Gemini was REMOVED on purpose (ToS/account risk). Do NOT recreate it. Argon round trips are manual: clipboard out (bridge/to_argon.md), user saves reply to bridge/from_argon/response.md.

- Argon NOT used. Claude did the patch-site feasibility pass: docs/helpers/USB_TEARDOWN_PATCH_SITES_2026-10-14.md. Best hook site c0120744 (32-bit CALLP to c011fa54). Next: resolve its 'Unproved' list items 1,2,4 (decode c0120658..0674 and c011faa0), then add a HOOKS row + ring trace in controller.c as a SEPARATE named candidate, add test, rebuild, run pytest. Never claim it fixes ownership.

### Later 2026-10-14 (Claude): diagnostic candidate implemented
- See sections 6-7 of docs/helpers/USB_TEARDOWN_PATCH_SITES_2026-10-14.md. Build: tools/make_controller_fw.py --diag-teardown. Offline only, observer only, NOT packageable.
- Tests: tests/test_diag_teardown_hook.py. Baseline now 160 + 3.
- Remaining ideas in order: (a) second observer at the Hwi consumer move-to-queue-32 (c011fb74/c011fb7a, both 16-bit-compact CALLP? check width first) or queue-32 consumer c0121a18..24; (b) host-side model test of ring semantics; (c) update HANDOFF_2026-10-14_LEAD.md Continue list; (d) owner-run test prep (flash decision is the owner's).

### Later 2026-10-14 (Claude): second observer done (idea (a))
- Hwi push sites c011fb74/fb7a are 16-bit compact CALLPs: not hookable. Used queue 32..35 consumer site c0121a18 (32-bit CALLP c011fa54, file offset 0x15994) instead. See section 8 of docs/helpers/USB_TEARDOWN_PATCH_SITES_2026-10-14.md. Ring updates now run with interrupts disabled (consumer context unproved). Lifecycle build unchanged (3e7f5236...28b9). Baseline now 167 passed, 471 subtests.
- Added tools/decode_ctl_diag.py host decoder (text table + JSON) and tests/test_diag_teardown_hook.py test. Baseline: 168 passed, 471 subtests.
- Updated HANDOFF_2026-10-14_LEAD.md "Work completed" and "Continue from this point".
- (d) owner-run test prep completed: created docs/helpers/OWNER_DIAG_TEST_PREP_2026-10-15.md (test scenarios, memory structure layout at 0xc01a0b00, decoding procedures, fault bit interpretation). DO_NOT_FLASH remains in effect.


### 2026-10-15 (Claude): abort obligation 1 narrowed
- docs/helpers/USB_TX_TEMPLATE_WRITERS_2026-10-15.md. The TX template table (c01805c4) has no instruction-level writer; bulk/external writes to its writable section remain unexcluded. Corrected the abort doc: the tail drain at c0120778 is the slot's submit queue (word [0]), not runtime state. Baseline: 171 passed, 471 subtests. Next: obligation 2 (Hwi c011fc8c->c011faa0 coexistence with the c0120650 poll; entry interrupt state).
- Obligation 2 (ownership part) done: docs/helpers/USB_HWI_COEXISTENCE_2026-10-15.md, tests/test_usb_hwi_coexistence.py. Baseline: 173 passed, 504 subtests. Next: obligation 3, endpoint association on shared queue 25 (teardown descriptor channel field, word 0 bits; does stock ever check it?), then the entry interrupt state of c0120650.
- Obligation 3 narrowed: docs/helpers/USB_Q25_ASSOCIATION_2026-10-15.md, tests/test_usb_q25_association.py. Baseline: 175 passed, 544 subtests. Next: obligation 4 (recovery/reuse after expiry), op-8 (c0144d0c) producer, c0120650 entry interrupt state. Consider an expiry-branch observer for the diag (c0120732 area; check hook width first).
- Entry IRQ state: docs/helpers/USB_ABORT_ENTRY_IRQ_2026-10-15.md (likely GIE=1; c015ee80 save/restores CSR; c012154c ends GIE=1). Helpers launched: Sol on docs/helpers/SOL_EXPIRY_RECOVERY.md (obligation 4), Gemini 3.8 Flash (agy) on docs/helpers/GEMINI_OP8_PRODUCER.md. Review their reports before relying on them.
- Sol obligation-4 report reviewed. It inverted c0120fa0 and c011fb38 and missed c011fd80 (field [9] = -1); corrections are at the top of the report. Next: triggers of the direct submitters c0120c00/c01219d0; consider a diag observer for TX field [5] stuck non-zero (liveness).
- The diag ring had no way off the device. Added a MIDI readback that exists only in the diag build (CTL_DIAG): event 4 (both footswitches) snapshots ctl_diag plus TX fields [2],[3],[5],[9] and streams them as CC102..106 framed by CC119. Host tools: tools/capture_ctl_diag.py (receive-only) and decode_ctl_diag.py --cc-log. Lifecycle build still 3e7f5236...28b9 (tested). ctl_diag now at 0xc01a0da0 in the diag build. Baseline: 183 passed, 579 subtests.
- Sol direct-submitter report reviewed (predicates check out). Key reframe: TX field [2] selects the mode, 0 = counted (enqueue/c0120550) and !=0 = ring (kick c0120c44, case D c01219d0). Ring-mode risk: an expired abort followed by a kick gives two chains. Open: the writer of field [2] and the caller of c0120c44. Both matter for USB audio (ISO is probably ring mode).
- Gemini op-8 report verified: op 8 = host CLEAR_FEATURE(HALT) on EP 0x84 (c0151f30), dispatched from the event task, so it runs the MIDI IN abort. A host pyusb clear-halt could trigger aborts on purpose during a diag run (owner-run).

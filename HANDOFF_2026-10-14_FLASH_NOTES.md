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

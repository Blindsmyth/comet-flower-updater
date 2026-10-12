# Controller firmware: preflight evidence and open assumptions

This is an offline audit of the existing **Controller TEST** updater. It is not a record of a pedal test. The firmware map's naming coverage is a navigation aid; it does not establish every function's behavior or every indirect call target.

## Artifact identity and flash scope (checked 2026-10-11)

| Claim | Evidence | Status |
|---|---|---|
| The updater contains the reviewed controller image | PE resource `BIN/0x81` is 494,928 bytes, SHA-256 `c6317cacfc28b0f49bed679b73fe1da6632b2cda4dd77523beb5a24b6d812f59`, byte-identical to `build/fw/res1_cf_controller.bin`. This explains the `c6317cac` handoff reference; `res1_controller.bin` is the different stock-based image. | Confirmed for current disk files |
| Current source produces that image | Offline rebuild with `make_controller_fw.py --base build/fw/res1_cfupd.bin` produced the same SHA-256 and 1,504-byte payload at `c01a0000..c01a05df`. | Confirmed, reproducible here |
| Existing stock bytes and hook targets | The builder and updater validator accept the stock SHA-256, the 176 CF constant-data changes, four stock CALLP sites/words, one added AIS load, and the unchanged final jump. Hook targets are `controller_start` c01a0000, `controller_dispatch` c01a0540, `controller_analog` c01a046c, `controller_housekeeping` c01a028c. | Confirmed structurally; linked ELF was disassembled, but the builder does not independently disassemble the patched main-image hook words |
| Updater flash stages avoid recovery code | `check_updater_stages.py` reports erase/write at 0x28000 (presets), 0x102000 (effects FS), and 0x33000 (main firmware), all `ok`; no stage touches boot/update code [0, 0x28000) or settings/signature [0xbf000, 0xc0000). | Confirmed for this updater's stage table |

## Runtime chain and confidence

| Link | Cross reference | What remains unknown |
|---|---|---|
| Boot mode selection | `controller_start` calls stock c015d428 before c0156f00 samples the 10-button bitmap twice through valid output pointers; bit 9/GPIO0 low latches mode. The earlier output-pointer ABI defect is fixed (recon/18 §1.2). Res5 checks update mode before loading main firmware (recon/25). | GPIO0's **physical button legend** is still an inference. Two immediate reads are not timed debounce. The user must hold through main-firmware startup. |
| MainApp events | c0134df0 dispatch hook preserves the event pointer/stack, forwards stock mode to c0127fe0, and in controller mode resumes at c0134dc4 after `controller_event` (recon/18 §1.4). Switch event pairs, knob IDs 25..28 and delta at event word 2 have instruction traces (recon/15). | Physical control names, encoder direction, combined footswitch/remap/repeat behavior, and every other path that may change a patch remain unverified. Incoming editor MIDI is not gated. |
| Expression | c015ffd0 interposes on calibrated 0..127 values before stock c014aef4 changes effect parameters (recon/15,18). The AD task publishes a latest value and posts idle event 42 with timeout 0 to wake MainApp (recon/19). | The expression pedal's physical identity is still inferred from the AD chain. A failed idle post while a value remains dirty can defer output until another MainApp event. The producer/consumer byte snapshot can discard a newer sample during the read/clear window. |
| USB MIDI transmit | Stock c01274cc accepts raw bytes; its worker packetizes `B0 cc value` as USB MIDI CC (recon/15). Housekeeping c0134dc4 drains up to four queued messages per MainApp pass, checking the 1,025-position ring before each send (recon/17,19). | The send takes stock semaphores B14[161] and B14[89] with unbounded waits, despite the ring-space peek. Drain latency has no fixed period. The wrapper hides transport success, so disconnects and competing producers can still lose messages. The 16-slot button queue drops the newest edge when full, including a release. These are known limits, not proven-safe behavior. |
| SDRAM placement | The payload is inside the reserved 16 KiB region at c01a0000, between inventoried AIS data ending c0187024 and the first known slot heap c01f4000 (recon/17,18 §2). The AIS load is accepted by the image walk. | Runtime indirect allocations, generic DMA destinations, and arbitrary effect writes have not been exhaustively excluded (recon/18 §2). Static gap evidence supports a controlled experiment, not an unconditional ownership proof. |

## Moving each assumption toward knowledge

1. **Close offline checks first.** Independently disassemble all four patched CALLP words in a main-image view, confirm execute-packet behavior and ABI at each call, trace all direct and credible indirect writers into c01a0000..c01a05df, and run an event/queue harness covering event IDs, ring wrap, disconnect and queue overflow. Verify the complete updater resource hashes and stage table for the *exact* candidate file immediately before use.
2. **Decide the required reliability contract.** If CC edges must never be lost or the MainApp must never wait on MIDI, the current implementation fails that contract already; redesign the transport and queue, then repeat the static audit. Do not label the current drain nonblocking.
3. **Use a controlled pedal observation only for facts static code cannot supply.** One physical control at a time establishes GPIO0's label, knob ordering/direction, expression identity and host enumeration. Timing, long-run coexistence and failure recovery require their own measured tests. Record the exact updater hash, pedal behavior and MIDI capture; promote only observed claims to “confirmed on hardware.”

**Current gate:** the image is reproducible and flash scope is checked. Runtime safety and complete control semantics are not proved. USB audio is a separate prototype and is not in this controller updater.

## Transport liveness trace (2026-10-11)

`controller_housekeeping` runs once per **MainApp mailbox event**, then MainApp returns to an indefinite mailbox wait (`c0134dd0` → `c015350c`, timeout `-1`; recon/19 §1). It sends at most four pending CCs. The stock MIDI worker drains its ring independently, but freeing ring space does not by itself post a MainApp event. Thus pending CCs can remain queued indefinitely after a full-ring observation or a four-message pass. An expression wake post with timeout zero can also fail while `expr_dirty` remains set. These are concrete liveness gaps, not just unmeasured latency.

`MIDI_SEND` at `c01274cc` waits on B14[161]; its lower send path `c0149de4` waits on B14[89]. The read-only `ring_free()` snapshot is outside those locks and does not reserve three bytes. The wrapper used by this controller discards the accepted-byte count returned by the lower path. Sending can therefore block and partial acceptance cannot be detected or retried as an intact CC. The 16-entry button array has 15 usable positions and drops the incoming edge when full, including a release. A queue test alone cannot repair the stock send contract.

The map name `midi_tx_worker_notify` for `c014a240` is not a validated public wake API. It branches to `c0155ac0` with an event-like argument, but that routine's existing `big_subsystem_init` map name is stale and the descriptor/return semantics need a direct call-site trace before reuse. Raw append at `c0149d74` bypasses the stock locks and is not a safe shortcut.

**Required design proof before a new candidate:** establish an accepted-message contract (or explicitly allow and recover from lost CCs), a wake path that retries pending state when ring space returns, and button state reconciliation so an overflow cannot leave a host control pressed. Prove task context, lock order, disconnect behavior and reset behavior against exact instructions, then test a host-side state machine for overflow, concurrent writes, wrap and failed wakes. Only after that should a rebuilt image be considered for a controlled pedal test. The existing updater is retained as an identified experimental artifact, not a reliability-qualified controller.

The proposed worker-side contract and its offline state-machine checks are in
`docs/CONTROLLER_TRANSPORT_DESIGN_2026-10-11.md`. They do not yet close the
worker-hook ABI, USB reconnect signal or hardware delivery gates.

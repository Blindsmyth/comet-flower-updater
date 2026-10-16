# USB mode — Codex Astra — 2026-10-16

## Summary
- U1: current controller_start latch precedes USB open on traced normal boot paths (Finding 3).
- Initial open/connect runs in MainApp, priority 3; later GPIO78 transitions run in SwitchNrmlSpdRead, priority 9.
- The priority-30 USB worker is created before SOFTCONN; the initiating task sets SOFTCONN.
- c015af18 is a worker restart wrapper, not just a POWER write (Findings 1–2).
- POWER bit 6 is set at c0120e1a/c0120e20 and cleared at c011ff4a/c011ff4c.
- Worker-only reconnect does not rerun usbmidi_open or rebuild IF2/IF3 (Finding 4).
- Full layer init clears registry/maps; full controller close must remove the old Hwi first (Findings 5–6).
- Config/alt state and custom stream state need reset separately; the apparent USB lock is a stub.
- U3: use checked, serialized task-context lifecycle steps; function inventory is in Finding 7.
- A safe live switch remains unproved because DMA ownership/reclamation is not established (Finding 6).
- Evidence and confidence tags follow; analysis was offline and no firmware/updater files were changed.

## U1. Ordering at boot

### Finding 3 — normal boot ordering and task priorities (U1)
**Confidence: confirmed** for the traced normal-boot control flow and task
records; **likely** that no untraced indirect task-priority mutation bypasses it.
The important boundary is NOT entry versus return of stock c015d428:
`c0134e14 CALLP c015d428` returns BEFORE `c0134e18 CALLP c0134db8`;
`c0134dc0 CALLP c01341e4` then performs the later application initialization.
That later initialization calls switch setup (`c0134200 CALLP c01570a4`)
and initial USB detection (`c0134354 CALLP c016c120`). Initial detection
uses `c016c140 CALLP c016ec60` (veneer to GPIO78 reader 1180950c), and
on its zero branch `c016c150 CALLP c016ab8c` starts USB in **MainApp**.
Thus controller_start's current source order, STOCK_STARTUP then two
READ_SWITCHES calls then mode assignment, is still before this USB open.
This corrects the tempting but incorrect inference that all application
initialization occurs inside c015d428.

Decoded static task objects in build/codex3/init_c0181b28.bin:
MainApp object c0181b28 has priority +8 = 3, entry +40 = c0134e10;
SwitchNrmlSpdRead object c0181c90 has priority +8 = -1 (inactive), entry
+40 = 118076c0. B14 base c0184e00 is established by `c0169a38 MVK
0x4e00,B14; c0169a3c MVKH 0xc0180000,B14`; c0185070 (B14[156])
contains c0181c90. Switch setup enables priority **9**:
`c0157138 CALLP c01529c0; c0157140 LDW *+B14[156],A4;
c0157144 MVK 9,B4` (parallel call argument packet).
Later GPIO78 changes are handled in that switch task by 1180a7ec:
`1180a874 CALLP 1180b150`, veneer `1180b150 MVK 0xab8c,B31;
1180b154 MVKH 0xc0160000,B31; 1180b158 B B31` -> c016ab8c.
Its initialization gate is `1180a800 LDBU *A5[0],A0; 1180a804 [!A0]
BNOP 1180a890`, A5=118134a0, set by `c016c172 STB A0,*A4[0]`.

Both paths converge: `c016ab94 CALLP c015b114` (endpoint-layer init),
`c016ab98 CALLP c016ab70`; `c016ab78 CALLP c0159758`;
`c01597b0 CALLP c0145124`; `c0145158 CALLP c0152410`;
then `c016ab80 CALLP c015af18`. Open and SOFTCONN run synchronously
in the initiating task: MainApp priority 3 initially, switch task priority 9
on its transition path, NOT in the new USB worker. The created worker is
c0138310, priority **30**, descriptor c01800bc: `.word c0138310` at
c01800c4, `.word 0x1e` at c01800c8, name pointer c01817d0 at c01800d4.
`c01387ac CALLP c014a400` creates it; `c014a438 LDW *A4[3],A0`
loads priority into Task params before `c014a46c CALLP c0165920`;
`c01387d0 CALLP c014a170` starts it, then `c01387e8 CALLP c0120dd0`
sets SOFTCONN in the caller. Worker receives at `c0138318 CALLP
c014a214` using B14[95]. Static MainApp/switch objects are C-initialized,
not created by this USB task factory.

Answer: c0134e14 (including the current latch before its return) precedes
c0145158 on the traced normal paths. No move is required for these paths.
A defensive common pre-open latch could run once at entry to c016ab8c,
before c016ab94, with already initialized GPIO; or immediately before
c0145158 if only registration needs guarding. These are **likely design
options**, not claims of a verified new patch. Do not re-sample on every
cable reconnection: latch once per power-up, initialize FX by default, and
preserve later explicit settings-page choices. Earlier raw GPIO reads
before platform initialization are not certified here.

## U2. Software disconnect / reconnect

### Finding 2 — actual POWER writes and shutdown work (U2)
**Confidence: confirmed.** POWER is 0x01e00401. Connect: `c0120e18 LDBU
*A4[0],A0; c0120e1a SET A0,6,6,A0; c0120e20 STB A0,*A4[0]`.
Disconnect: `c011ff34 LDBU *A4[0],A1; c011ff4a CLR A1,6,6,A1;
c011ff4c STB A1,*A4[0]`. Stop also writes zero / 0x4000 through
0x01e01800 / 0x01e01808 with 32-byte strides (`c011ff68 STW
A0,*B4++[8]`; `c011ff6c STW B0,*A4++[8]`), masks wrapper interrupts
(`c011ff8a STW A0,*A4[0]`, address 0x01e00034), and calls interrupt
control `c011ff8c CALLP c014a2a0` with A4=7. Connect enables interrupts
(`c0120de8 CALLP c014a278`, A4=7), iterates endpoint setup
`c0120df0 CALLP c0120888; c0120e00 CALLP c01201e0`, then sets SOFTCONN.
Thus stock disconnect does more than remove the pull-up. DMA descriptor
ownership reclamation is not proved by these register writes alone.
### Finding 4 — registration replay is separate from SOFTCONN (U2)
**Confidence: confirmed.** `c015afa4 CALLP c0138a6c` -> `c0138a70 CALLP
c015c6b4` edits the persistent three-slot selector/record registry at
c011aa28. Null B4 takes removal/compaction (`c015c6c0 [B2] BNOP
c015c70c`; `c015c6ec CMPEQ A0,A2,A0`; `c015c6f2 STW A0,*A4[0]`;
`c015c6f4 STW A0,*A4[1]`). It removes matching selector entries, not a
chosen record pointer: c015afa0(6,0) removes MIDI and both audio records.
Non-null B4 allocates a free slot (`c015c738 STW B2,*B4[1]`;
`c015c73a STW A2,*B4[0]`), or returns ffff8a5c at c015c744.
After successful mutation `c015c74a CALLP c015c620` clears derived maps,
and `c015c760 CALLP c015c66c` replays each surviving record with ordinal
A6 (`c015c764 ADD B1,1,A6`). No locking is present in these small wrappers.

Reset targets: endpoint owners c011aa40 (32 words to -1:
`c015c622 MVK 32,B0; c015c628 ADD B0,-4,B0; c015c632 STW A0,*A4++[1]`),
interface owners c011aac0 (five words, sufficient for IF0..3:
`c015c640 MVK 1,B0; c015c64a STW A0,*A4++[1]`), and record vector
c011aa18 (zero: `c015c660 MVK 0,A0; c015c664 STW A0,*A4++[1]`).
SPLOOPD ILC counts require pipeline-fill iterations; do not interpret ILC
as the whole store count. Stock interface-owner index 5 is not cleared.
Stock replay always assigns MIDI endpoints and IF0/1 to its slot:
`c015c684 STW A4,*A5[0]` (c011aa4c), `c015c68a STW A4,*B4[0]`
(c011aa90), and c015c696's doubleword store at c011aac0. Keep the audio
candidate's slot-aware replay modification: slot0 -> IF0/1 + MIDI EP3/EP4;
slot1 -> IF2; slot2 -> IF3. Merely flipping descriptor mode leaves stale
records/maps. Rebuild MIDI first, then audio IF2 then IF3 only for USB mode,
check all return values, and leave disconnected on partial registration.

`c0145158 CALLP c0152410` is re-executed by the full c016ab8c cable/start
path (Finding 3), but NOT by c015af18/c0138720 alone. Its stock open clears
40 bytes at c011ac80 (`c0152428 CALLP c0167b00`, A6=40), stores callback,
and dispatches operation 0 (`c0152438 CALLP c01520f4`, A4=0, B4=-1).
Registration then uses `c01521b0 CALLP c015afa0`, A4=6,
B4=c018137c. Therefore a worker reconnect does not automatically rebuild
the audio registry, and a full MIDI reopen must not append duplicate slots.
### Finding 5 — full layer init clears registry; alternatives do not (U2/U3)
**Confidence: confirmed.** Full c016ab8c invokes c015b114 -> c0138a78;
`c0138b20 CALLP c015c814`; that routine calls `c015c816 CALLP c015c620`
and clears persistent selector/record pairs at c011aa28 (`c015c836 STW
B0,*B4++[2]; c015c838 STW A0,*A4++[2]`). Hence a successful full
layer-init followed by MIDI open starts with empty slots: it does not need
an extra selector-6 removal. A worker-only reopen bypasses this clear.
Layer init also resets endpoint software records based at c011a4e8
(`c0138a88 MVK 0xa4e8,B4; c0138a8c MVKH 0xc0110000,B4`) and calls
`c0138b0c CALLP c0122260`. The latter refuses if the Hwi handle B14[131]
already exists (`c0122264 LDW *+B14[131],B0; c0122268 [!B0] BNOP
c0122274`; otherwise ffff8acd). It is NOT an idempotent live reset.

Alt-setting/configuration reset is a separate routine c01359b8:
`c01359c0 STW B0,*+B14[10]; c01359c4 STW B0,*+B14[11]`, B0=0;
`c01359cc MVK 0xa1b0,A4; c01359d0 MVKH 0xc0110000,A4;
c01359d8 STB A0,*A4++[1]` clears the four alt bytes IF0..3.
SET_CONFIGURATION also clears them (`c0135678 STB A0,*A4++[1]`).
A bare POWER toggle itself does neither. Reset audio stream/EP1 producer
state and pending EP0 state too; host re-enumeration is not proof that a
concurrent producer has stopped. These additional custom-state resets are
a **likely requirement**, not a verified stock audio capability.

Synchronization correction: B14[96] looks like a lock at the call sites,
but its implementation is a stub here: `c014a4d0 MVK 1,A4; c014a4d2 BNOP
B3,5`, and `c014a1d8 MVK 0,A4; c014a1da BNOP B3,5`.
Do not rely on it to serialize a mode switch. The worker mailbox does
block: `c014a216 MVK -1,A6; c014a218 CALLP c0166680` from c0138318.

## U3. Full re-open functions, contexts, and synchronization

### Finding 1 — connect wrapper includes teardown (U2/U3)
**Confidence: confirmed** for call graph; lifecycle safety is not yet established.
`c015af18 STW B3,*B15--[2]`; `c015af20 CALLP c0138720` is the public
connect wrapper, not the POWER write itself. `c0138722 CALLP c013826c`
first shuts down the previous instance. Shutdown starts `c0138274 CALLP
c011ff28`, then handles task/synchronization objects in B14[94..96]:
`c0138298 CALLP c014a160`, `c01382a4 CALLP c014a2b0`,
`c01382d0 CALLP c014a344`, `c01382e0 CALLP c014a340`.
Creation uses `c0138730 CALLP c014a4d0`, `c013876c CALLP c014a4d4`,
`c01387ac CALLP c014a400`, storing handles in B14[96], [95], [94].
The explicit stop wrapper is `c015af10 CALLP c013826c` (entry c015af0c).
These wrappers need task-context lifecycle serialization; they cannot be
assumed to be a harmless SOFTCONN toggle from Hwi.
### Finding 6 — complete close path and CPPI limits (U2/U3)
**Confidence: confirmed** for the following call chain; **unproved** for
complete in-flight DMA ownership recovery.
Cable detach uses `1180a824 CALLP 1180b180` -> c016ab58.
`c016ab5a CALLP c016ab40` with B14[24] as A4 first stops the worker
(`c016ab48 CALLP c015af0c`) then, if enabled, closes MIDI
(`c016ab50 CALLP c0159620`). `c016ab64 CALLP c015af00` ->
`c015af04 CALLP c0138300` -> `c0138302 CALLP c013826c` and
`c0138304 CALLP c01200c0` performs the additional controller close.
That last step matters: `c01200d0 CALLP c014a36c` deletes the Hwi,
`c01200e0 STW B0,*+B14[131]` clears its handle on success, then
`c01200e4 CALLP c011ffc0; c01200e6 CALLP c0120004` perform hardware
shutdown. Do not substitute just c015af0c before full layer init, which
would leave the live-Hwi guard from Finding 5.

MIDI close `c0159624 CALLP c0144ed0` calls c0144e58 (stop/drain) and
`c0144ed4 CALLP c0152318`; the latter only clears callback word c011ac80
(`c0152326 STW A0,*A4[0]`), not interface registry. MIDI task/event teardown
uses `c0159644 CALLP c01529c0` with -1, `c015964c CALLP c016cba0`,
`c0159658 CALLP c016c960`. Stop/drain can sleep:
`c0144ea4 CALLP c014a28c` with A4=10 -> `c014a290 CALLP c0158980`,
inside a retry loop (`c0144eb4 [A0] BNOP c0144e80`), counter initialized
to 0x3e9 at c0144e74. Run this from an external task, never Hwi/Swi or
the USB worker being deleted. Do not hold producer locks while waiting:
MIDI send pends indefinitely on B14[161] (`c01274d4 CALLP c0150b20`,
B4=-1 at c01274e0); another lock wrapper is `c014a096 MVK -1,B4;
c014a098 CALLP c0150b20`. A new lifecycle lock must exclude cable
transitions and mode requests without deadlocking these existing waits.

CPPI state is layered. c011ff28 clears global I/O state via
`c011ffb2 CALLP c011fe70` with A4=0; controller init calls it with A4=1
(`c0122280 CALLP c011fe70; c0122284 MVK 1,A4`), enabling its additional
per-endpoint clearing (`c011fe98 [!B0] BNOP c011ff20`). Connect iterates
c0120888/c01201e0 to program channel queue/control fields from templates
c0180598/c01805c8/c01805cc (`c01208b2 LDW *A4[0],A2`;
`c012020a LDW *A4[0],A4`; `c012024c STW A0,*B4[0]`). Those writes
reconfigure channels; they do NOT demonstrate that old submitted packets
or completion queues are empty.

Existing offline teardown decision (docs/helpers/USB_TEARDOWN_DECISION_2026-10-14.md)
identifies the still-open ownership issue. Cross-checked instructions:
`c0120744 CALLP c011fa54; c0120748 CALLP c0120550` classify/recycle a
completion; `c0120778 LDW *-A4[3],A11; c0120780 CALLP c011fa20`
drains the endpoint's submit queue. For stored MIDI template {22,24,25},
this late drain is queue 22, not proof of a matching TX teardown or recovery
of an already in-flight descriptor. **Likely safety requirement:** account
for matching teardown completion and all retained descriptors before reuse;
on timeout/ambiguous ownership stay disconnected and do not recycle buffers.
Neither a full stock reopen nor a bare pull-up toggle closes this proof gap.
### Finding 7 — proposed mode-switch transaction (U2/U3)
**Confidence: likely design; not a proved safe implementation.** The smallest
change in software is not necessarily the smallest safe hardware transition.
The evidence supports two possible transactions:

1. **Minimal registry-only variant, conditional on proven quiescence:** stop
   producers and finish/cancel transfers; disconnect and stop the worker via
   c015af0c (Finding 1); reset configuration/alt state with c01359b8 (Finding 5)
   and custom audio/EP0 pending state; change the mode flag while detached;
   c015afa0(6,0), then re-register stock c018137c and, for USB, IF2 and IF3
   in order (Finding 4); recreate the worker/connect through c015af18.
   This avoids reopening MIDI, but the MIDI transport state left behind by
   c011ff28 has not been shown reusable. It is a candidate optimization,
   NOT the recommended currently justified minimum.
2. **Conservative stock-lifecycle variant:** serialize requests in a dedicated
   lifecycle task (MainApp posts a request); stop new MIDI/audio submissions,
   complete the ownership/quiescence handshake, then invoke c016ab58 for
   full worker + MIDI + controller close (Finding 6). Verify close completion
   and Hwi removal; wait a host-visible detached interval without holding
   locks (exact interval not established offline). Clear configuration/alt
   and custom pending state, publish the new mode flag, then invoke the
   c016ab8c initialization/open sequence (Findings 3/5). Full init clears the
   registry; successful c0145158 open then installs MIDI and the mode-aware
   hook installs IF2/IF3 only for USB. All records/maps must be ready before
   c016ab80 connects. Do not resume producers until the host configures the
   new device; audio remains inactive until its alternate setting is selected.

The transaction must cover both the descriptor builder and registration
reader with one stable flag. FX and MIDI may share descriptors/registry;
only crossing the USB boundary inherently requires this topology rebuild.
This is a **likely design inference**, not a finding about an implemented
MODE menu. On registration/init failure keep SOFTCONN clear; stock wrappers
such as c016ab8c do not test intermediate A4 results (`c016ab94 CALLP
c015b114` immediately followed by `c016ab98 CALLP c016ab70`), so a safe
implementation needs checked substeps, not blind calls to the whole wrapper.

For review, the full-lifecycle call inventory is:

| Stock entry | Observed caller/context | Relevant operation / evidence |
|---|---|---|
| c016ab58 | GPIO78 transition in SwitchNrmlSpdRead, priority 9 | Full stop; c016ab5a CALLP c016ab40, c016ab64 CALLP c015af00 |
| c015af0c / c013826c | Initiating task; also error cleanup | Disconnect, stop worker/mailbox; c0138274 CALLP c011ff28 |
| c0159620 / c0144ed0 | Initiating task after worker stop | MIDI close and task deletion; c0159624 CALLP c0144ed0; may sleep |
| c015af00 / c0138300 / c01200c0 | Initiating task / error cleanup | Controller/Hwi close; c0138304 CALLP c01200c0 |
| c01359b8 | Reset path, callable only with lifecycle exclusion for this proposal | Config + alt clear; c015ea00 CALLP c01359b8 |
| c015b114 / c0138a78 | MainApp initially, switch task on transition | Endpoint/core init and registry clear; c0138b0c CALLP c0122260; c0138b20 CALLP c015c814 |
| c0159758 / c0145124 / c0152410 | Same initiating task, before USB worker start | MIDI init/open; c01597b0 CALLP c0145124; c0145158 CALLP c0152410 |
| c015afa0 / c015c6b4 | Synchronous caller; no lock in these wrappers | Registry mutation/replay; c0138a70 CALLP c015c6b4 |
| c015af18 / c0138720 / c0120dd0 | Same initiating task | Start priority-30 worker, then SOFTCONN; c01387e8 CALLP c0120dd0 |
| c0138310 | USB worker, priority 30 | Mailbox dispatch; c0138318 CALLP c014a214; do not ask it to delete itself |

Table confidence: **confirmed** call sites and observed contexts; any new
lifecycle-task integration is **likely design**. c015e9d0 is a larger reset
orchestrator, not interchangeable with c01359b8: it calls abort/endpoint
operations before that state clear (`c015e9d8 CALLP c01229e8;
c015e9e4 CALLP c0122ad0; c015e9ec CALLP c015b128;
c015e9f4 CALLP c0138660`). Do not invoke it while deleting its worker
without resolving its callback/transport dependencies.

## Remaining unproved points
- Complete CPPI teardown receipt, queue drainage, buffer ownership, and safe
  reuse across live mode changes (Finding 6); no safe hot-switch certification.
- Host-required disconnect timing and enumeration behavior; no device or host
  experiments were performed.
- Complete indirect-writer exclusion for startup task priorities and GPIO78
  physical meaning; normal boot ordering above is the traced stock graph.
- Exact custom audio/EP0 cancellation handshake and rollback after partial
  IF2/IF3 registration; only stock disassembly and existing reports assessed.
- New lifecycle serialization against switch-task cable changes, USB Hwi/Swi,
  MIDI producers, and settings-page requests; the stock lock stub is insufficient.
- Worker stop/delete failure propagation and whether MIDI close's bounded
  retry really establishes quiescence; its elapsed sleep is not DMA proof.

Offline scope: no pedal, MIDI transport, network, updater execution, or firmware
edits. Only this report and build/scratch/astra_usb were written. Existing
unrelated working-tree modifications were left untouched.

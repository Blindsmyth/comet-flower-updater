# Instruction-backed kernel extents — 2026-10-14

The companion `stack_extents.json` initially recorded **53 explicit physical scan extents**
with exact-start/exclusive-end addresses and verbatim disassembly anchors.
They resolve the physical-range question for 28 of the 29 distinct entries
marked `UNCATALOGUED_ENTRY`/`UNKNOWN_EXTENT` in the previous four-root inventory.
The remaining entry, `c0152154`, is an internal control-flow fragment; its
owning switch routine requires a control-flow analysis before an analyzer can
call the fragment an independent function.

This is extent evidence, **not a stack proof**. The worker stack bound remains
unknown; DO_NOT_FLASH remains applicable. An extent can be correct while its
control flow, callback set, live frames, context transfer or recursion remains
unmodeled. The old catalog is useful for navigation but was not used alone to
justify an end address.

## Image identity and conventions

- Disassembly `build/fw/map/main.dis`: SHA-256
  `e824b1e0effdaaca35cf87bd3a0bcc9b6242291e4def5e471120b28a762c82d1`.
- ELF `build/fw/map/main.elf`: SHA-256
  `b0625c7a055020ddcbc61bb6966311891ead03bb6dae865b6f3f72ed45fb3946`.
- Catalog `build/fw/map/subsystems.tsv`: SHA-256
  `abc2e8a8c407b306088ef5e39853ca5529acf65faa1735e024c0cef3de622d0c`.

The JSON maps hexadecimal entry addresses to `end`, classification, rationale,
and exact parsed instruction anchors. A boundary anchor at the exclusive end
shows the next independent instruction sequence or data boundary; it is not
part of the preceding extent. Extents include zero padding and compact fetch
headers where needed to reach the following independent routine. They do not
claim every instruction inside an interval executes on every path. Actual
branch-delay packets were checked before selecting each end. BNOP instructions
with five encoded delay cycles do not execute the next routine's prologue.

Every JSON entry has instruction evidence at its start, terminal sequence and
end. All anchors were rechecked against the parser expression used by
`stack_depth.py`; all start/end addresses occur in the decoded image. The
three veneer target addresses were computed from MVK/MVKH pairs, rather than
assumed from catalog names.

## Material corrections

| Entry | Exclusive end | Instruction evidence / effect |
|---|---|---|
| `c016de00` | `c016de40` | Lookup returns at `de20`, followed by zero padding; the next 176 bytes are tables and a separate veneer, not this routine. |
| `c0167be0` | `c0167cc0` | Return at `7cb8` precedes an independent five-save prologue at `7cc0`; the former `7da0` scan included a second routine. |
| `c0168340` | `c0168400` | Saved B11 is restored to B3 at `83e2`; return at `83ea` has delay packets through `83f2`; `8400` begins its own B3 save. |
| `c0169240` | `c0169300` | Two register-restoring epilogues return at `92e2` and `92f6`; `9300` begins another save prologue. |
| `c016ba40` | `c016bac0` | Five saved-register slots are restored at `bab0..bab8`, followed by B3 return; `bac0` begins the independent predicate routine. |
| `c016dd00` | `c016dd40` | Linked-list search returns at `dd38`; `dd40` begins a saved-register wrapper. |
| `c016dd40` | `c016dd80` | Wrapper returns at `dd64`; `dd80` begins a separate SP-snapshot wrapper. |
| `c016a9c0` | `c016a9f0` | Lock/root wrapper returns at `a9ec`; `a9f0` begins another independently saved 16-byte wrapper. |
| `c016e9a0` | `c016e9c0` | Wrapper returns at `e9ba`; `e9c0` and `e9e0` are separate vtable field-[2]/field-[3] computed tail wrappers. |

The ELF section `sc011adc0` confirms that `c016de40..c016de78` contains seven
little-endian binary64 values:
`1.0, 1.189207115, 1.414213562, 1.681792831, 1.044273782, 1.090507733,
1.138788635`. The repeated constants/table words continue through `c016deec`;
`c016def0` begins a four-instruction B31 veneer. Misdecoded conditional memory
operations in this region must not be counted as stack instructions.

Cross-review with the stack/context investigation additionally confirms
`c0168c40..c0168d00`, `c016cc00..c016cc60`, `c016cc60..c016ccc0`,
`c016bb40..c016bbc0`, and the independent accessors at
`c016b840..c016b8c0` and `c016b8c0..c016b940`. In particular the idle routine
at `cc00` does not contain the conditional scheduler call at `cc74`; that
call belongs to the separate wrapper at `cc60`.

## Save/restore helpers and startup

`c016e020..c016e040` is a **save helper**, not a normal balanced callee. It
pushes an 8-byte B14 slot plus six 8-byte register pairs: **56 bytes**. Its
branch through A3 at `e024` returns to the wrapper's continuation while
the remaining stores at `e028..e032` execute in delay packets. Those 56 bytes
remain live during later wrapper calls. `c016e000..c016e020` restores the same
slots; its branch through restored B3 at `e00a` completes after the B14 load
and NOP sequence. The JSON isolates these helpers from neighboring stubs.

The two cross-image veneers `1180bd10..1180bd20` and
`1180bcc0..1180bcd0` load B31 with `c016e020` and `c016e000`, respectively.
They preserve the A3 continuation used by CALLP.S1 callers. Thus the
`1180add8..1180ae18` function has the same live helper-frame issue, although
its helper calls initially target veneers. A B31 transfer at one of these
sites is neither an arbitrary callback nor a return alias; it is a constant
tail transfer into the helper.

The callback wrapper `c015f08c..c015f0d8` is also helper-backed. Its two
callback sites are `c015f0a8` and `c015f0c0`; the final restore-helper call is
at `c015f0d4`. The no-frame state setter beginning at `f0d8` is excluded.
An analyzer that scans the old broad `c015ee80` catalog body must still fix
that owner's extent instead of attributing these callbacks to the owner.

Registration `c016e0c0..c016e0e0` returns B3 and stores its incoming A4 to
`c0183aec` in delay packets. The neighboring task startup routine
`c016e0e0..c016e100` instead loads B2, A4, B4 and B3 from the startup stack,
advances SP 16 bytes, and transfers through B2 at `e0f4`. It is a context
transfer with task-entry arguments, requiring separate context analysis.

## Previously unknown tail veneers

| Entry | Exclusive end | Constant target |
|---|---|---|
| `c016f5c0` | `c016f5d0` | `11805eb4` |
| `c016f6c0` | `c016f6d0` | `1180af50` |
| `c016f6e0` | `c016f6f0` | `1180add8` |

Each veneer consists of MVK, MVKH, B B31 and NOP 5 in a 16-byte slot.
`observed_tail_target` is metadata; a consumer must explicitly resolve the
constant target instead of silently suppressing B31 branches. The map also
contains narrow target bodies `11805eb4..11805ec4`,
`1180af50..1180af60`, `1180af34..1180af50`, and
`1180add8..1180ae18`. Following those bodies will expose additional physical
entries or helper/context issues; this chunk does not assert exhaustive graph
coverage.

## Remaining cases and integration requirements

`c0152154` is reached by a local switch-default branch at `c015210c`; it sets
A1 and branches to merge block `c01521b8`. Its owner starts at `c01520f4`
with the save helper, reserves another eight bytes at `20f8`, dispatches via
the table at `c018447c`, and finally calls the restore helper at `222c`.
Catalog starts at `2126`, `215a`, `216a`, `2176`, `2198`, and `21a8` are case
or merge fragments. Making only `2154..215a` an independent function would
lose the shared epilogue and inherited stack state. The JSON keeps this entry
under `unresolved`, with exact owner/branch/merge evidence, instead of giving
it a spurious normal-function extent.

Integration must use explicit ends rather than merely adding each start to
the existing catalog. Otherwise internal catalog fragments still split owners,
padding may become synthetic functions, or data stays merged into adjacent
code. Validate the disassembly hash and exact anchors before applying a map.
The observed ELF hash is provenance and should be revalidated when the ELF is
available. Keep unknown bodies unscanned, keep callbacks and return aliases
unresolved unless independently justified, and preserve live-helper findings.
No finite stack bound follows from completing the physical extent inventory.

No firmware edits, flashing, updater actions, staging or commits were performed
by this investigation chunk. Only this note and `stack_extents.json` were
created; the lead performs serial review and commits.

## Lead integration follow-up

The map now contains **60 extents**. The lead verified all quoted anchors
against the pinned disassembly and added the independent no-frame return stub
`c016e940..c016e960` and physical switch-owner range
`c01520f4..c0152240`. The latter includes the local eight-byte reservation,
default and case fragments, result merges, eight-byte restore and terminal
save-frame epilogue. Its register dispatch at `c0152124` remains a blocker.
This is a conservative physical scan, not a resolved switch CFG or proof
that every scanned case is reachable for a particular caller.

The historical `unresolved.c0152154` record is retained as control-flow
evidence. That address remains an internal fragment, and is now scanned
inside its physical owner rather than traversed as an independent callee.
This exposes the downstream command handlers previously omitted from the
USB-send root. See the refreshed inventory in the continuation note.

The next pass separates `c0164380..c01644c0` from the following independent
prologue. Its alleged call to `c0161200` was actually at `c01644f0`, in the
next routine. This removes the remaining catalog-induced DFS cycle. The
separate `c0161200..c01613a0` extent has 24 bytes of decrements, rather than
the 48 bytes charged by the merged catalog.

`c015dc20..c015de40` is now physically known, but its record-field and
diagnostic callbacks remain unresolved. Separating
`c0166780..c0166880` from `c0166880..c0166980` shows that the callback-wrapper
call at `c0166904` belongs to the latter. It is no longer attributed to the
former or pulled into the four reviewed roots through that false edge.
Both findings are retained rather than treating an unreachable callback in
these roots as a globally resolved callback.

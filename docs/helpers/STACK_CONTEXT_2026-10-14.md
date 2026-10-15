# Stack continuations and execution contexts — 2026-10-14

Offline review of the stock disassembly and ELF. **This is not a stack proof.**
No device or updater was accessed, and no firmware was changed. The worker
stack gate remains open; DO_NOT_FLASH remains in effect. This note supplements
[the continuation inventory](STACK_CONTINUATION_2026-10-14.md).

## Input identity

| Input | SHA-256 |
|---|---|
| `build/fw/map/main.dis` | `e824b1e0effdaaca35cf87bd3a0bcc9b6242291e4def5e471120b28a762c82d1` |
| `build/fw/map/main.elf` | `b0625c7a055020ddcbc61bb6966311891ead03bb6dae865b6f3f72ed45fb3946` |
| `build/fw/map/subsystems.tsv` | `abc2e8a8c407b306088ef5e39853ca5529acf65faa1735e024c0cef3de622d0c` |

Addresses and instructions below refer to these inputs. The stock instruction
findings do not independently prove the identity of a packaged candidate or
the completeness of runtime callback writers. Adjacent `.fphead` words are
fetch-packet metadata; `||` instructions and branch delay instructions must
remain in the semantic review.

## Persistent register-save helper

`c016e020` is a register-save continuation helper. It returns control to the
incoming A3 continuation while leaving **56 bytes of SP decrement live**:

```text
c016e020 STW.D2T2 B14,*B15--[2]
c016e024 B.S2X A3
c016e028 || STDW.D2T1 A15:A14,*B15--[1]
c016e02a STDW.D2T2 B13:B12,*B15--[1]
c016e02c STDW.D2T1 A13:A12,*B15--[1]
c016e02e STDW.D2T2 B11:B10,*B15--[1]
c016e030 STDW.D2T1 A11:A10,*B15--[1]
c016e032 STDW.D2T2 B3:B2,*B15--[1]
```

The STW decrements B15 by 8 despite storing one 4-byte word; six STDW
decrements add 48. The branch at `c016e024` does not finish the helper's stack
effect: the parallel store and subsequent delay instructions execute before
the continuation. There is no pop in this helper.

`c014a0cc CALLP.S1 0xc016e020,A3` is a concrete caller that supplies A3 as
the continuation and preserves the incoming caller B3 in the helper frame.
After resuming, `c014a0f8 CALLP.S2 0xc0144580,B3` executes while those 56
bytes remain live. Both result branches (`c014a104` to `c014a10c` and
`c014a106` to `c014a114`) eventually reach the restore helper.

```text
c014a114 CALLP.S1 0xc016e000,A3
c014a118 || MV.L1 A0,A4
c016e000 LDDW.D2T2 *++B15[1],B3:B2
c016e002 LDDW.D2T1 *++B15[1],A11:A10
c016e004 LDDW.D2T2 *++B15[1],B11:B10
c016e006 LDDW.D2T1 *++B15[1],A13:A12
c016e008 LDDW.D2T2 *++B15[1],B13:B12
c016e00a BNOP.S2 B3,0
c016e00c || LDDW.D2T1 *++B15[1],A15:A14
c016e00e LDW.D2T2 *++B15[2],B14
c016e010 NOP 4
```

The restore pops 56 bytes and branches through **restored B3**, not the A3
supplied by the apparent CALLP. A3's restore-helper continuation is unused.
The final two pops execute with/in the return delay sequence. On this path,
the restore helper is a terminal epilogue for the wrapper. Treating both
helpers as normal sibling calls loses the persistent frame, and treating the
restore as returning locally to `c014a118` invents continuation behavior.

Narrow annotation: `c016e024` is a continuation when reached under this save
helper's CALLP/A3 convention; it is not an arbitrary A3 callback. `c016e00a`
is a return through its paired save frame. These classifications do not prove
all callers pair helpers correctly. A context-aware analyzer must keep the
save-helper issue open until it checks live frame pairing, SP changes and
every exit. The companion `stack_context_sites.json` pins exact disassembly
anchors and records these conventions.

## The apparent idle/scheduler cycle is a merged extent

The previous graph cycle `c015de40 -> c016cc00 -> c015de40` does **not**
describe the idle routine's instructions. `c016cc00` and `c016cc60` are
independent entries that the catalog merges into one 192-byte extent.

| Instruction evidence | Consequence |
|---|---|
| `c016cc00 SUB.L2 B15,0x8,B15` | Idle routine's local SP decrement is 8 bytes. |
| `c016cc04..cc0c MVC CSR; OR 1; MVC CSR` | It enables interrupts while waiting. |
| `c016cc24 SPLOOPW 13`, `c016cc40 SPKERNEL 0,0` | Local software-pipelined loop, with no additional SP decrement in the loop. |
| `c016cc44 DINT`, `c016cc48 ADD.L2 8,B15,B15`, `c016cc4c BNOP.S2 B3,5` | Idle restores its SP and returns. It never branches to `c015de40`. |
| `c016cc60 STW A10,*B15--[2]`, `c016cc62 STW B3,*B15[1]` | Separate wrapper establishes an 8-byte save frame. |
| `c016cc6c LDHU *+A10[0],A0` with A10=`c01820e4`; `c016cc74 [A0] B.S1 c015de40` | The scheduler call belongs to the separate wrapper. |
| `c016cc80 ADDKPC c016cc84,B3,0`; `c016cc9c..cca8` restore/return | The branch has an explicit local call continuation and then unwinds. |

At `c015de82`, the scheduler calls the slot at `c01817ac`, whose observed
image target is `c016cc00`, with a continuation set at `c015de84` to
`c015de88`. Its local retry at `c015de96` returns to `c015de82`, after the
callback has returned. Neither retry re-enters the scheduler prologue at
`c015de40`. Thus this local retry reuses the scheduler's existing 48-byte
frame; it does not itself accumulate scheduler frames.

Interrupt-driven scheduling remains a separate question because the idle
routine explicitly enables interrupts. Eliminating this false ordinary-call
cycle establishes neither interrupt nesting nor a worker stack bound.

Other extent contamination found during this review:

| Entry needing separation | Instruction-backed distinction |
|---|---|
| `c016e0e0` after `c016e0c0` | Registration returns at `e0c0`, with slot construction/store at `e0c4..e0cc` in its delay sequence. `e0e0..e0f8` loads a task bootstrap frame and jumps through B2 at `e0f4`; it is not a registration callback. |
| `c016e9c0`, `c016e9e0` after `c016e9a0` | `e9a0` restores/returns at `e9b6..e9ba`. The later entries independently load object/vtable fields and tail-transfer through A3 at `e9d0/e9f0`. |
| `c015f08c` inside catalog extent `c015ee80` | New CALLP to save helper at `f08c`, object callbacks at `f0a8/f0c0`, final restore-helper CALLP at `f0d4`. Those callbacks do not belong to the preceding routine. |
| Following `c0168c40` | This routine restores and returns at `8cd8..8ce8`; its body has no call to `c0169ca0`. Its actual callback at `8cd0` loads slot `c017a0c4`, whose image word is `c0167e80`. |
| `c016bbc0` after `c016bb40` | `bb40` restores/returns at `bba8..bbb8`. `bbc0` has a distinct three-store prologue. |
| `c016b840`, `c016b8c0` after `c016b7c0` | `b7c0` restores/returns at `b81c..b828`; separate field-selection wrappers return at `b8b4/b934`. |

These are review findings for the extent owner, not a blanket assertion that
every byte between these entries is executable or that other boundaries are
correct. Padding and terminal delay instructions must remain accounted for.

## Task stack switching is a context edge

The scheduler's call sequence supplies outgoing and incoming task-SP slots:

```text
c015e004 DINT
c015e008 B.S1 0xc016aec0
c015e00c ADDKPC.S2 0xc015e018,B3,3
c015e010 ADD.D1 A11,0x10,A4
c015e014 || ADD.D2 B10,0x10,B4
```

`c016aec0` reserves 48 bytes on the outgoing task stack, saves its SP through
A4, and loads the selected incoming task SP through B4:

```text
c016aec0 STW.D2T2 B3,*B15--[12]
c016aec4 MV.D2 B15,B0
c016aec6 || MV.S1X B15,A0
c016aec8 || STW.D1T2 B15,*+A4[0]
c016aecc LDW.D2T2 *+B4[0],B15
c016aed0 || STW.D1T1 A11,*+A0[3]
...
c016aefc || STW.D2T2 B3,*+B0[1]
c016af00 LDW.D2T2 *B15[1],B4
c016af02 || MV.D1X B15,A0
...
c016af28 B.S2 B4
c016af2c || LDW.D2T1 *+B15[10],A14
c016af30 LDW.D1T1 *+A0[11],A15
c016af34 || LDW.D2T2 *++B15[12],B3
c016af38 NOP 4
```

Old-SP aliases A0/B0 keep the outgoing register stores on the outgoing stack
after the B15 load. The incoming frame supplies B4 at word 1, which is the
branch continuation. The final incoming restore/pop completes in its delay
sequence. The store at `c016aec0` writes the entry-SP slot before its 48-byte
post-decrement; the saved continuation is also written at outgoing frame
word 1. SP-decrement accounting and actual touched addresses are distinct.

`c016af28` is **not an ordinary B4 return alias or a callback**. It transfers
to the selected task's saved continuation. A fresh task can resume the
bootstrap helper `c016e0e0`; a suspended task can resume an existing scheduler
activation such as `c015e018`. No single ordinary-call target set models
these choices. The companion annotation uses `kind=stack_switch` so the
inventory can retain an explicit blocker.

On resumption at `c015e018`, `c015e030` can branch locally to `c015de74`;
that reuses the resumed task's scheduler frame. The scheduler then pops its
48 bytes at `c015e048..e052` and returns at `c015e054`. This loop alone
does not stack repeated activations on one B15. The outgoing scheduler frame
and 48-byte saved context remain on the suspended task while another task
runs, so an analyzer must retain both states without charging the selected
task's subsequent calls to the outgoing task's stack.

## Preemption placement and guards

The interrupt dispatcher deliberately switches stacks late. The instructions
confirm the placement described in [the stack audit](STACK_AUDIT_2026-10-13.md):

1. `c015ec80 STW B10,*B15--[2]`, `c015ec88 AND -8,B15,B15`, and
   `c015ec8c ADDK -264,B15` reserve 272 bytes plus alignment on the
   interrupted stack. The call through A3 at `c015ed44` targets `c01557c0`
   (constructed at `c015ed10/ed1c`); delay packets finish register saves and
   set the continuation B3 to `c015ed90` at `c015ed68/ed78`.
2. `c01557c0..57ca` reserve six 8-byte save slots, and `c01557cc`
   reserves 32 more: 80 bytes before the stack switch.
3. `c0155800` calls `c016d600`. It reads saved-SP word 5 at `c0181fb8`
   and interrupt-top word 6. `c016d610 BNOP B3,0` still executes the
   conditional delay stores/move: if saved-SP B0 is zero, `c016d618`
   stores B15 in word 5 and `c016d620` changes B15 to B1. With nonzero
   saved-SP it returns without changing B15. A4 records the prior state.
4. `c0155a1c` calls `c016e100` with that prior state loaded from the
   dispatcher's word-4 local at `c0155a20`. When A4 is zero,
   `c016e110` restores B15 from `c0181fcc` and `c016e114` clears the
   saved-SP slot in the branch delay sequence. Nested dispatchers with
   nonzero prior state do not restore another stack.
5. **After** restoration, `c0155a64 [!B0] B.S1 c015de40` can call the
   scheduler with continuation `c0155a7c` established at `c0155a78`.
   Thus this scheduler path can run on the interrupted task's stack while
   the 352-byte pre-switch interrupt/dispatcher reservation is still live.

The scheduler guard at this last call tests the original dispatcher's saved
state at `c0155a22`, the scheduler flag halfword at `c01820e4`
(`c0155a2c/5a38`), and another lock halfword at `c01820b4`
(`c0155a40..5a58`). `c016b7c0` likewise tests its incoming A4, flag
`c01820e4`, and lock `c01820b4` before its scheduler branch at `c016b7f4`.
These are instruction-backed guards, not proven bounds on reentrant
scheduling: their complete writer sets, meanings, initialization, nesting
transitions and interactions with callbacks are still required.

The first-level pre-switch charge is 352 bytes plus alignment; that is an
observed path component, not an interrupt maximum. Nested interrupts can
place their own entry/dispatcher reservations on the interrupt stack. The
dispatcher enables interrupts before its handler call (`c0155934/5938`),
so nesting cannot simply be excluded. Every applicable vector, nesting limit,
error/exception path and post-restoration scheduler path still needs review.

## Minimum model needed next

Track each execution state's entry, packet/delay position, predicate facts,
register provenance, SP delta, live save-helper frames and owning task or
interrupt-stack identity. A CALLP to the save helper is a 56-byte persistent
push plus a continuation; the paired restore is a pop plus terminal caller
return. Ordinary B+ADDKPC sequences are calls when their continuation is
established in the delay instructions. Vtable branches with no new return
address can be tail transfers, but their targets still require resolution.

At `c016aec0`, suspend the outgoing stack state and resume the selected
context; keep the outgoing frame live until that context later resumes and
unwinds. At `c016d600/c016e100`, carry the prior saved-SP state so nested
dispatch does not acquire a fictitious new stack or prematurely restore one.
Evaluate guards against writer-complete facts before pruning reentrant paths.
Local loops must revisit a program state with its SP effect, rather than be
mistaken for new function activations.

Reviewed unresolved A3 sites `c015d364`, `c01616b0`, `c0163788`,
`c0163900`, `c0168bcc`, `c0168bf8`, and `c0168cd0` are actual
loaded-target transfers, with explicit B3 continuations. None is safely
removed merely because its branch register is A3. `c0152124` is a jump-table
dispatch loaded from `c018447c`, and `c015f0a8/f0c0` are object callbacks.
The `c016e0f4` bootstrap transfer and `c016e9d0/e9f0` vtable transfers
belong to independent entries. Exhaustive callback coverage, genuine recursive
cycles and maximum live stack usage remain unresolved.

No worker-stack ceiling or spare-margin claim follows from these findings.

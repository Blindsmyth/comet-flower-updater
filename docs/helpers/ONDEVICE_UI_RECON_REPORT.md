# On-device UI recon report

## 1. Screen selection, `c01595e8`

**Finding (confirmed call sites and branch logic; likely task attribution for the
MainApp-side callback).**  The callable entry is actually `c01595e4` (the
`c016e020` prologue thunk); `c01595e8` is the first body instruction.  There
are two direct callers:

* `c0135aec` calls it at `c0135af0` with `A4=0, B4=0`.  That routine is passed
  as the callback address by `c0136688..c0136694` to `c01361ac`; the latter
  invokes the callback through `B6` at `c01361f4..c0136200`.  Its known
  registration/call paths (`c013072c`, `c01341d0`) are MainApp-side UI paths,
  so this invocation is likely in MainApp task context rather than in a
  display interrupt.
* `c013c02c` calls it at `c013c034`.  `c013c02c` is one arm of the table
  dispatcher `c013c060` (`c013c0ac`), reached from `c013c0c8`; the UpdateUI
  entry `c013c754` calls `c013c0c8` at `c013c724`.  This call is therefore in
  `g_Task_UpdateUI`.

The selector call is not a dispatcher: `c0127fe0` is simply
`LDW *+B14[27],A4; ... return`.  This word is the PC/editor-session screen
flag: the editor/MIDI connection path changes zero to one at
`c0128b4c..c0128b58`, while its teardown writes zero at
`c0128a28..c0128a30`.  Thus PC MODE is an editor/PC connection presentation,
not USB enumeration in general and not USB-audio stream state.

The exact decision at `c01595ec..c0159612` is:

| `B14[27]` returned by `c0127fe0` | input `B4` | action |
|---:|---:|---|
| 0 | either | call `c0148af4`; result 1 selects `c01594f0`, otherwise `c015942c` |
| nonzero | 0 | call `c01594c8` (PC MODE path) |
| nonzero | nonzero | call `c0148af4`; result 1 selects `c01594f0`, otherwise `c015942c` |

Predicate audit: `c01595f2 [!A0]` branches to the normal chooser when the
selector is zero; only the nonzero fall-through copies input `B4` to `A0`,
and `c01595f6 [!A0]` branches to PC MODE when that input is zero.
`c0159600 CMPEQ 1,A4,A0` followed by `c0159602 [A0]` selects `c01594f0`
exactly for return value 1.

`c01594c8` deliberately tests its own `A4` because it is a conditional draw
helper.  `c01594ca MV A4,A0; c01594cc [A0] BNOP c01594ec` skips the bitmap
when `A4 != 0`; when `A4 == 0` it falls through and calls
`c011c508(ctx,0,0,128,32,c0178ee0)` at `c01594e0`.  Both identified callers
provide `A4=0`, so the selected PC MODE branch really does draw the full
screen.  Confidence: **confirmed** for instructions, callers, bitmap and
truth table; **likely** for the indirect callback's precise MainApp task
attribution.

## 2. LCD ownership and flush

## 3. Text drawing

## 4. Controller-mode screen behavior

## 5. LEDs

## 6. Hook proposal

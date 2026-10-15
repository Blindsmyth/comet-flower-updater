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

**Finding (confirmed pipeline and lock; likely policy conclusion).**  The
application renderer and the panel transport are separate.  UpdateUI entry
`c013c754` repeatedly selects/dispatches screen work (`c013c720 CALLP
c0156e80`, `c013c724 CALLP c013c0c8`, `c013c74e CALLP c013c4e4`).  These
screen handlers call the glyph/bitmap primitives and modify the RAM image.
There is also the MainApp-side `c0135aec` callback from section 1, so UpdateUI
is the normal owner, not the only code capable of drawing.

`ctx = *(B14+122*4)` is the word at `c0184fe8`, but it is **not a framebuffer
pointer**.  It is a small framebuffer/context index.  `c011c508` proves the
translation:

```text
c011c520 MV A21,A0
c011c522 SHL A0,9,A0
c011c528 ADD A0,11800000,A4
c011c524 CALLP c011adc0
```

Thus context `n` selects the 512-byte LCD-page buffer
`11800000 + n*0x200` (128 columns x four 8-pixel pages).  Drawing also marks
dirty-page bits in `11813250+n`; for example `c011f054..c011f064` writes that
byte, and `c011e080..c011e096` ORs a page bit after text drawing.  The stock
global context is explicitly reset to zero at `c014df56..c014df58`.

The actual panel push is `c016f420 -> 11805878`.  It reads the dirty byte at
`11813250+ctx` (`118059f8..11805a0e`), tests each of four page bits at
`11805a18..11805a24`, sends the page command/data through `11805420` and
`11805484` (`11805a34..11805ac8`), then clears the bit at
`11805ace..11805ae0`.  This is a synchronous dirty-page flush in the calling
task; no independent periodic framebuffer-copy task was found.

The shared serialization object is `B14[149]`.  The clear wrapper
`c014db8c` takes it (`c014db94 CALLP c0161200`), calls `c016f420` at
`c014dba4`, then releases it at `c014dba8`.  UpdateUI also brackets screen
work with this same object at `c013c72c..c013c74e` and releases it at
`c013c748`.  This is the same shared hardware/SPI lock used by the AD serial
path; it is not a lock internal to `c011c508`, whose body contains no lock.

Consequences: a MainApp task may safely *request* a redraw through an
existing UI event/dirty-state path that UpdateUI consumes.  New drawing
should run in UpdateUI while holding the established `B14[149]` discipline,
then use the normal flush path.  Calling glyph/bitmap or flush routines
directly from the MIDI worker is unsafe policy: the primitives are not
self-locking and `c014db8c` may block on the shared lock.  The MIDI worker
should only publish compact status and signal a UI request; it must not draw,
flush, or wait indefinitely on the display/SPI lock.  Confidence:
**confirmed** for buffer layout, dirty flags, transport and lock; **likely**
that routing every new draw through UpdateUI is the smallest race-free
policy (the complete set of indirect stock drawing callbacks is not proven).

## 3. Text drawing

## 4. Controller-mode screen behavior

## 5. LEDs

## 6. Hook proposal

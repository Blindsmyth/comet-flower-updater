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

**Finding (confirmed graphics ABIs; likely formatter identification).**  The
glyph ABI is consistent across the family:

```c
void glyph(unsigned ctx /* A4 */, int ch /* B4 */,
           int x /* A6 */, int y /* B6 */);
void string(unsigned ctx /* A4 */, const char *s /* B4 */,
            int x /* A6 */, int y /* B6 */);
```

The relevant routines are:

| routine | role / font | instruction evidence |
|---|---|---|
| `c011d2d4` | one 5x7 glyph in a 6x8 cell | `MPY 6,A2,A0`; font base `c01787e0` (ASCII 0x20 lands at `c01788a0`) |
| `c011e000` | 5x7 string, 6-pixel advance; handles tab/form-feed controls | `c011e028 CALLP c011d2d4`; `c011e038 ADD 6,A8,A0` |
| `c011d590` / `c011e0a4` | one/string bold 7x7, 7-pixel advance | font base `c01782d0`; `MPY 7,A2,A0` |
| `c011e898` / `c011e930` | one/string 14x18 glyph | `c011e904 MPYLI 42`; bitmap `c01757f8`; draw width 14, height 18; string advances 14 |
| `c011e96c` and following string wrapper | 16x21 glyph/string | computed 48-byte glyphs from `c0174170` |
| `c011ea30` and `c011ea84` | 11x13 glyph and centered string | table `c0176250`, width 11, height 13 |
| `c011eb08` | one 8x13 glyph | `c011eb2c..c011eb40` selects `c0177180`, width 8, height 13 |
| `c011ebc8` | centered 8x13 string | obtains length, computes approximately half of `9*len`, then calls `c011eb08` |
| `c011ec48` | left-aligned 8x13 string | calls `c011eb08` and advances x by 9 at `c011ec68` |

All sanitize unsupported characters to space before indexing their tables;
for example `c011eb10..c011eb28` accepts ASCII 0x20..0x7e and substitutes
0x20 otherwise.  For compact controller status, the stock small-status font
is the 5x7/6x8 family (`c011d2d4` + `c011e000`), not the 8x13 title family.

`c016c360` is a `sprintf`-style variadic formatter, most plausibly
`int sprintf(char *dst /* A4 */, const char *fmt /* B4 */, ...)`.  It saves
the destination (`c016c370 MV A4,B4`), delegates to the common printf engine
`c014fa40` at `c016c38c`, and explicitly writes the terminating zero at the
returned/end pointer at `c016c3b8`.  Stock UI code uses it to construct local
strings before drawing, e.g. `c0159528..c0159540` builds a stack string and
passes it to `c011ec48`.  Confidence on the formatter's purpose and argument
order is **likely** because the TI variadic stack-home convention obscures the
source-level prototype; the null-terminated formatted-output behavior is
confirmed.

A minimal safe short-line sequence in UpdateUI task context is:

```text
take B14[149]
optional: c016c360(local, "CC %u %u", cc, value)
A4 = *(B14 + 122*4)       ; context index
B4 = literal-or-local     ; NUL-terminated ASCII
A6 = x; B6 = y
CALLP c011e000            ; 5x7 status line
CALLP c016f420            ; dirty-page panel flush for that context
release B14[149]
```

For a literal banner the formatter is unnecessary.  If an existing UpdateUI
iteration already owns the lock and performs the normal flush, do not take
the lock recursively or add a second flush; just issue the text call inside
that owned draw phase.  Confidence: **confirmed** for glyph/string signatures,
font tables and advances; **likely** for the exact C return type of
`c016c360`.

## 4. Controller-mode screen behavior

**Finding (likely visible result; confirmed surviving paths).**  Controller
entry does not install a screen.  `controller_start` first calls stock
`c015d428`, then samples/latches controller mode; MainApp subsequently enters
the ordinary loop at `c0134db8`.  Independently, UpdateUI entry `c013c754`
continues to dispatch and draw the selected stock screen.  Consequently the
post-boot display is normally the stock current-patch/effect screen produced
by startup/UpdateUI.  Once controller mode consumes local control events,
their normal handlers no longer change the selected screen or perform their
screen actions, so that stock patch presentation becomes visually stale.
The exact first visible frame is **likely**, not deterministic from the static
trace alone, because MainApp and UpdateUI scheduling plus an already attached
editor can affect which stock frame wins.

The framebuffer is not simply frozen.  The controller dispatch trampoline
returns to `c0134dc4`, so each MainApp cycle still executes
`c0134dc4 CALLP c01537f4`; UpdateUI itself continues its
`c013c764..c013c8fc` loop and can redraw from unchanged stock state.  The
housekeeping routine can also call `c01537a8` at `c0153810`, retaining its
system-event path.  Predicate audit for that call:

```text
c0153800 LDW *+B14[162],A4
c0153804 LDW *+B14[105],B0
c015380a CMPLTU A4,B0,A0
c015380c [A0] BNOP c0153814
c0153810 CALLP c01537a8
```

Truth table: when unsigned `B14[162] < B14[105]`, `[A0]` is true and the call
is skipped; when it is false, `c01537a8` runs.  Therefore controller mode does
not guarantee total UI isolation: UpdateUI redraws still occur and qualifying
system housekeeping may change the screen.  What is suppressed is the normal
screen transition/action attached to each consumed local MainApp event.
Confidence: **confirmed** for preserved housekeeping, live UpdateUI loop and
suppressed handlers; **likely** for “normal patch screen, then stale” as the
user-visible boot result.

## 5. LEDs

## 6. Hook proposal

# Brief: a way into extra settings pages (2026-10-16, part 2)

Owner decisions (2026-10-16): **no stock menu item is given up.** MODE (FX / MIDI / USB) goes on a page of
our own (start from the dormant OUTPUT page, screen ID 5), and the design must let us **add and remove our
own pages and settings later**. The pedal always boots in FX mode (no persisted mode).

Read first: docs/helpers/MENU_RE_ARGON_2026-10-16.md and docs/helpers/MENU_RE_ASTRA_2026-10-16.md
(both reviewed by Claude: tables are .cinit-decompressed RAM; descriptors 9 words; 4-item records 0x2c).
Rules as before: docs/helpers/SAVE_PROTOCOL.md, offline only, never touch the pedal/MIDI/updaters,
edit only your report and your scratch folder, tag claims with address + instruction + confidence.

Report: `docs/helpers/MENU_PAGES_ARGON_2026-10-16.md`, scratch `build/scratch/argon_pages/`.

## Questions
P1. **Entry to the alternate chooser.** Screen ID 1 (List B c0181368 = {5 OUTPUT, 9 TUNER, 3, 8, 12}) shares
    draw c0157c0c / event c0157bac with ID 0. Find every code path that selects ID 0 or ID 1 (all callers of
    c0149664 / c01496d0 with constant or computed IDs). Is ID 1 ever reachable in stock? How does c0157c0c pick
    List A vs List B (by descriptor w0?), and could a third list be added the same way?
P2. **Unused input in the SETTING chooser.** List every event ID that c0157bac (and the generic c0149840 path)
    handles, and which physical controls produce them where known (knobs 25..28, effect buttons, footswitches,
    Rhythm/Tuner/arrows). Which events arrive in the chooser and are ignored? These are candidates for
    "next/previous settings page" (A -> B -> our pages).
P3. **Page stepping c0149a90** (+1/-1, clamps 2..12, calls c0149664): who calls it (c0164870 and others), on
    which event, in which screen? Could it serve page flipping for us?
P4. **Adding screen IDs >= 15.** c01495c0 returns 0 for ID > 14 (`c01495c4 CMPLTU 0xe,A4,A0`). List every call
    site of c01495c0 and every table or array indexed by screen ID (sizes!), and any code that assumes ID < 15
    (e.g. c01497f4, icon selection c0149ad4, UpdateUI dispatch). Conclude: can one CALLP hook on c01495c0's
    callers (returning our own descriptors for IDs >= 15) give us extra pages safely? Give the exact CALLP
    words (address, word, parallel bit) that would need retargeting.
P5. **Our own 4-item page.** Confirm what a page needs: descriptor w4..w8 (which may be 0?), the c0154564 page
    constructor args (A4 count, B4 records, A6 ?, B6 title, A8, B8), the formatter w7 contract (signature,
    output buffer, max chars at y=24) so a MODE item can print FX / MIDI / USB. Use the OUTPUT page
    (descriptor c0183740, records c0182b00) as the worked example.

Finish with a Summary (<= 15 lines) at the top and a recommended design (entry control + hook list).

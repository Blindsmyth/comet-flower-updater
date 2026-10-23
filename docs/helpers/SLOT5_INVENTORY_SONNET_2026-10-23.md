# Hardcoded-5-slot inventory, main firmware (Sonnet, 2026-10-23)

Static analysis only. Scope: every place OUTSIDE the already-analyzed PTCF
storage format (`docs/helpers/CF_STORAGE_SONNET_2026-10-23.md`, Q3) that
assumes exactly 5 effect slots per patch. Goal: size a 6-(maybe 7-)slot
firmware job.

Method: grep `build/codex6/main-all.dis` for the literal `5` in compare/loop
contexts (`CMPGT`, `CMPLT`, `CMPGTU`, `CMPLTU`, `MVK 5,`), for stride `0x54`
(84, slot struct size) and `0xa000` (40 KiB slot heap size), and for the
specific addresses already named in the brief; read each hit's surrounding
function (<=60 lines) to classify it. Table columns: Address | Function |
What it does with "5" | Category | Change needed | Size | Confidence.

## Summary

Raw grep totals across `build/codex6/main-all.dis` (whole main firmware): 58
`CMPGT(U).L1/.L2 5,...` + 9 `CMPGT(U) 0x5,...` + 11 `CMPLT(U) 0x5,...` = 78
"compare to 5" sites, plus 139 `MVK ...,5,[AB]n` immediate loads. Most are
unrelated (menu item counts, font/retry/table constants); only the ones
tied to the known per-slot structures (0x1181159c+84*slot struct, the
0x118133e0 callback table, the c0183xxx resource tables, c011acf0 page
array) are slot-count sites. Counts by category below (confirmed unless
marked):

- **Audio**: 6 sites/structures (slot dispatch loop, 2 init-table loops,
  1 unrolled 5x memset block, DSP-load admission gate, our own watchdog
  harness in `firmware/usb_audio_proto/usb_audio_tap.c`).
- **Memory**: 3 data tables (heap-base, a second resource table, in-use
  flags) — **none of these is computed by `n*0xa000` arithmetic**; they
  are baked `.const` tables indexed by slot, correcting the brief's framing.
- **Patch load**: re-lists CF_STORAGE_SONNET's clamp + ~9 sites, PLUS 4
  more confirmed sibling loops found this pass in the wider 1180a000-
  1180c000 submodule (not in CF_STORAGE's narrower scan range) — real
  total is "a dozen-plus", not ~9.
- **UI**: 4 confirmed sites (selected slot, page array + reset-all loop,
  24-byte UI struct, slot-window init) + 2 fully-traced effect-placement
  loops + ~14-17 same-idiom untraced siblings in c0132xxx (cited from
  CF_STORAGE, not re-derived). Slot icon chain draw / effect picker still
  **not located** — biggest open UI risk.
- **MIDI/editor**: no new hardcoded-5 beyond what's already covered by
  CF_STORAGE (SysEx = PTCF, already generic); one "likely" lead (a sanitize
  call near the USB/MIDI string-builder address range) not traced to its
  caller.
- **Other**: 1 spot-checked site judged unrelated (audio sample-mixing
  math, not slot count); the remaining ~45 raw hits not individually
  triaged (see Other section for the fingerprint-based shortcut).

**Hardest sites / biggest unknowns** (see Plan): the audio callback table
sits *inside* a larger 0x1181329c..0x118134a4 "peripheral pointer block",
not cleanly before it — growing it shifts other live pointers; the three
c0183xxx resource tables are flash `.const` data with unconfirmed slack;
a 6th 0x81330 work buffer needs new SDRAM after `c04abff0` that was not
confirmed free; the LCD slot-icon-row draw code is still unlocated.

## Audio

| Site | Function | What it does with "5" | Change needed | Size | Confidence |
|---|---|---|---|---|---|
| `11818c28` `CMPGT.L2 5,B10,B0` | audio Swi slot dispatch (loop top `11818c00`, body to `11818c38`) | Loop bound for `for(slot=0;slot<5;slot++)`: `11818c0c LDW *+B11[B10],B5` reads a function pointer from `B11=0x118133e0` scaled by `B10` (slot), then `11818c16 BNOP B5,0` calls it indirectly. `11818be0/be4` form `B4=0x118133e0`; `11818be8 MV.L2 B4,B11`. Matches FW_RND_ANSWERS' "slot callback table 0x118133e0" and S10's watchdog design exactly. | `CMPGT` imm `5`->`6`; table `0x118133e0` needs a 6th 4-byte pointer slot | small instruction edit, but table growth collides with the adjacent peripheral-pointer block (see Plan) | confirmed (full disasm trace `11818bd4..c38`) |
| `c014fea0` region | per-slot descriptor init (boot-time, one-shot) | `c014fed0 MVK.L2 5,B0; c014fed2 ADD B0,-1,B0 (B0=4); c014fed8 MVC B0,ILC; c014fee4 SPLOOPD 4` — a 5-iteration init loop (per FWMAP.md's SPLOOPD-ILC+4 rule) writing 5 entries, stride 20 bytes (`STW *B4++[5]`/`*B6++[5]`), into the work-buffer descriptor table at `c0183470` (base formed at `c014febc MVK 0x3470,B4; c0164ec8 MVKH 0xc0180000,B4` — matches FW_RND_ANSWERS' "c0183470" exactly) | `MVK 5,B0` -> `6`; table needs 20 more bytes appended | small (one immediate + flash `.const` table growth) | confirmed |
| `c0164a98`..`c0164b1c` | work-buffer zero-init (boot-time, one-shot) | **Fully UNROLLED, not a loop**: 5 separate `CALLP 0xc0167b00` (memset) calls, each with its own hardcoded 32-bit base address reconstructed from `MVK`(low16)+`MVKH`(high16) pairs: slot0 `c0226000`, slot1 `c02a7330`, slot2 `c0328660`, slot3 `c03a9990`, slot4 `c042acc0`, each exactly `c0226000+n*0x81330` (arithmetic independently verified for all 5), size `A6=0x81330` each; sentinel reused right after at `c04abff0` (matches FW_RND_ANSWERS' "end c04abff0"). | needs a **new hand-written 6th unrolled `CALLP` block** at `c04abff0` (not an immediate edit — no loop bound exists to bump) | medium (new code + must confirm `c04abff0..c052c320` is free SDRAM — **not confirmed this pass**) | confirmed (address arithmetic for all 5 bases independently recomputed and matched) |
| `c0164a80` / `c0164a8c` | per-slot resource accessors (called from `c0129740`/`c0129734` per FW_RND_ANSWERS) | Each is a single `LDW *A5[A4],A4` (scaled index) with `A5 = 0xc01839c0` / `0xc01839a8` respectively (addresses reconstructed from `MVK 0x39c0`/`0x39a8` + `MVKH 0xc0180000`). **Correction to the brief's framing: there is NO `c01f4000 + n*0xa000` arithmetic anywhere in the firmware — the 5 heap-base addresses (and the second table's 5 values) are a literal precomputed `.const` data table**, not computed from a stride. No bound check in either accessor (confirms "no count" from FW_RND_ANSWERS). | append a 6th `u32` to both tables | small per table, but flash `.const` layout risk (see Memory) | confirmed (both address formations read directly; table-vs-arithmetic distinction confirmed by absence of any `0xc01f0000`/`0xa000` multiply anywhere in the dis file) |
| `c0141ad8`..`c0141b48` | DSP-load ("Process Overflow") admission gate (FW_RND_ANSWERS Q1/Q5, "dspload sum < 230.0f") | `for(A10=0;A10<5;A10++)`: reads slot `A10`'s effect id via `0x1181159c + 84*A10` (`c0141af2 MVK 84,A0; MPYLI A0,A10,...; B0=0x159c\|0x11810000=0x1181159c` — same struct/stride CF_STORAGE already confirmed), looks up its declared dspload via `CALLP 0xc012b2c4`, accumulates with `ADDSP` into a running float sum. Loop bound confirmed `c0141b48 CMPGT.L1 5,A10,A0`; sum compared later (`c0141b5c MVKH 0x4366,B4` = `230.0f`, `c0141b60 CMPLTSP`). | `CMPGT` imm `5`->`6` (trivial); the `230.0f` budget ceiling is a product decision, not forced by this RE pass | trivial for the loop edit; budget re-tuning is a separate (non-RE) decision | confirmed (full disasm trace `c0141ad8..c0141b64`; `230.0f` ceiling cited from already-confirmed FW_RND_S1, not independently re-decoded bit-for-bit here) |
| `firmware/usb_audio_proto/usb_audio_tap.c` (our own watchdog/bench code, not stock firmware) | `ua_slot_enter`, `ua_wd_check`, `#define UA_SLOT_TABLE 0x118133e0` | `if (k < 5u)` in `ua_slot_enter`; `static void *ua_wd_seen[5]; static u32 ua_wd_over[5];` and `for (k = 0; k < 5u; k++)` in `ua_wd_check`; `enum { ...UA_B_POST = UA_B_S0 + 5...}` in the bench harness. All index the SAME `0x118133e0` table confirmed above. | bump all `5`s/`5u`s to `6`, grow both arrays, rebuild via `tools/make_usb_audio_fw.py --watchdog` | trivial (our own C source) | confirmed (direct source read, lines ~332-345 and ~505-535 of `usb_audio_tap.c`) |

## Memory

| Site | Function | What it does with "5" | Change needed | Size | Confidence |
|---|---|---|---|---|---|
| `c01839c0` | heap-base table (5+ `u32`, flash `.const`) | Per-slot code/const heap base, read by `c0164a80` (see Audio). Confirmed to be a **data table, not an arithmetic expression** — corrects the brief's assumption of `c01f4000+n*0xa000` computed inline. | append a 6th `u32` entry | small, but table's exact length/what follows it in `.const` is unconfirmed — risk of `.cinit`-shift, same class of risk CF_STORAGE flagged for the 53-record and region tables | confirmed (table identity + address formation); exact table length inferred (not independently dumped) from all observed callers passing slot 0..4 only |
| `c01839a8` | second per-slot resource table | Same accessor pattern via `c0164a8c`; semantic content (size? const-heap limit? something else) not independently decoded this pass | append a 6th entry alongside `c01839c0` | small, same `.const`-growth risk | confirmed address/table identity; content/meaning not decoded (out of budget) |
| `c01839f0` | per-slot "in use" byte flags (per FW_RND_ANSWERS, address re-confirmed here via `MVK 0x39f0`+`MVKH 0xc0180000` formations at `c0129784`, `c01297c0`, `c012b1f4`) | 3 callers found, none individually traced to full purpose this pass | append a 6th byte | small | address confirmed; role "likely" (unchanged from FW_RND_ANSWERS, not newly confirmed) |
| `c04abff0` boundary | end of the 5 work buffers (see Audio unrolled-init row) | Reused immediately as a base for a **different, smaller** structure right after the 5th work buffer (`c0164b28` region, size argument `~0x1100`, not the `0x81330` work-buffer size) — i.e. **something else already occupies memory starting exactly at `c04abff0`** | a 6th work buffer can't simply start at `c04abff0`; what currently lives there, and where it ends, was **not traced this pass** | unknown — flagged as the key open risk for physical slot-6 resources | confirmed that *something* starts there with a different size; its identity/extent not resolved |

## Patch load

Full detail already in `docs/helpers/CF_STORAGE_SONNET_2026-10-23.md` (Q3)
— re-listing only, not re-derived: clamp `11806450` (`CMPGTU 0x5`/`0x6` x2,
`MVK 5` x2 stores); sibling `CMPGT.L1/.L2 5,A<n>` loops at `118060d4`,
`118061f8`, `11807438`, `11807494`, `118074d4`, `11807504`, `11807570`
(the ZD2 effect-binary loader loop) inside the `c012f878 -> 118075e4 ->
1180738c` chain; CF_STORAGE additionally found ~14 more in `c0132xxx`
(cited there, not re-derived here either).

**New this pass** (confirmed by direct read, same idiom, same callee
fingerprint `{0x1180bcc0, 0x1180bd10}` — the effect-ID sanitize pair
CF_STORAGE already named): `118065d0`, `118066d0`, `11807348` (all in/
adjacent to the `1180738c`-area sanitize function, confirmed), plus a
further cluster `1180a6dc`, `1180a9ec`, `1180aa34` (confirmed, same
callee pair, different outer function spanning roughly `1180a500-
1180ac00` — **a wider submodule than CF_STORAGE's narrower scan range**),
and `11809a00` (confirmed loop `for(slot=0;slot<5;slot++){ CALLP
0x118099a0(slot) }` then the same `1180bcc0`/`1180bd10` pair — sits near
the USB/MIDI string-builder address range per FW_RND_ANSWERS; **not**
conclusively proven to be the SysEx-receive path itself, see MIDI/editor).

**Revised total**: CF_STORAGE's "~9 sibling loops" was a lower bound —
this pass alone adds 4 more confirmed sites in a wider address range,
making the real total for this one subsystem "a dozen-plus", before even
counting the ~14 in `c0132xxx`. Category: Patch load. Change: each site
is its own `CMPGT` immediate edit (`5`->`6`); size small per site, medium
in aggregate (high miss-risk doing this by hand — see Plan for a
fingerprint-based sweep suggestion). Confidence: confirmed for the
addresses and the recurring idiom; "likely" that the untraced `c0132xxx`
sites are the same pattern (not individually re-verified here).

## UI

| Site | Function | What it does with "5" | Change needed | Size | Confidence |
|---|---|---|---|---|---|
| `c011abf4` | selected slot (0-based) | re-cited from `docs/EDIT_SCREEN_TRACE_2026-10-23.md` (live RAM-diff evidence) | n/a (not count-bounded itself) | n/a | confirmed (prior doc) |
| `c011acf0 + 4*n` | per-slot edit-page array, `n=0..4` | re-cited + independently re-derived here: `c015adb4`'s single-slot page-reset accessor forms `A5 = 0xc011acf0` exactly (`MVK 0xffffacf0,A5; MVKH 0xc0110000,A5`), then `STW A0,*A5[A4]` (scaled index by slot `A4`) | append a 5th... 6th word | small | confirmed (address arithmetic re-derived independently) |
| `c015adc8`..`c015add4` | reset-all-pages loop | Fully re-traced: `A4=0; do { CALLP 0xc015adb4(A4) /* page[A4]=0 */ ; A4++ } while (CMPGT.L1 5,A4,A0)`. Called from `c012fc54`, immediately after `c012fc18` zeroes the 24-byte UI struct at `c011abe4` (confirmed caller chain, matches EDIT_SCREEN_TRACE's "cleared by c012fc18" note) | `CMPGT` imm `5`->`6` | trivial | confirmed (full disasm `c015adc8..c015add8`, full caller chain `c012fc18->fc54`) |
| `0x11811900`, 4 entries | slot-window init, boot-time one-shot (`c0140220`-`c0140238`) | `SPLOOPD 1` with `MVK.L2 0,B0; MVC B0,ILC` (`ILC=0`) runs **4 total iterations** (FWMAP.md's documented delayed-SPLOOP `ILC+4` rule, independently cross-checked against this new site) writing `A0=1,2,3,4` (post-increment-then-store) into `*A4++` starting at `0x11811900`. This is the "window of slot indices that follows the selection" the brief/EDIT_SCREEN_TRACE describe (initial boot contents `{1,2,3,4}`, not `{0,1,2,3}` — the live diff in EDIT_SCREEN_TRACE caught it already mid-session). | `SPLOOPD` `ILC` `0`->`1` (+1 more table word) IF the UI should show one more slot in the window at once; otherwise this can stay at 4 (a UI/paging choice, not a forced change) | trivial-to-small | confirmed init site; the **runtime slide-on-arrow-press code was not located** this pass (EDIT_SCREEN_TRACE already flagged `c016f650`/`c012ee80` as open) |
| `c013f9f0`..`c013fe00` region | effect placement ("the routine that places an effect in a slot", per FW_RND_ANSWERS S11) | Confirmed to operate on the **same** `0x1181159c + 84*slot` struct (re-derived stride/base here independently). Does an 84-byte-stride array shift (`SUB A14,0x1,A0` counted loops at `c013f92c`/`c013f960`, generically bounded by a register-held count, not a hardcoded 5 — consistent with CF_STORAGE's "struct is slot_count-generic" finding). Two FULL `CMPGT 5` loops traced in its neighborhood: `c013fa2c-c013fa3c` and `c013fde4-c013fdf4`, each `for(slot=0;slot<5;slot++) { CALLP 0xc016f4d0; CALLP 0xc016f4c0; CALLP 0xc014ff44(slot); CALLP 0xc016f660(slot); }` — almost certainly "refresh every slot's on-screen icon/state" after an insert/replace. | 2 traced sites: `CMPGT` `5`->`6` each; CF_STORAGE's ~14 untraced `c0132xxx` siblings presumed same idiom (not re-verified here) | small for the 2 traced; unknown-but-presumed-small-each for the rest | confirmed for the 2 traced loops and the shift-loop's genericity; "likely" that the `c0132xxx` cluster is the same pattern |
| `c012e5a8` column loop, `CMPGT 4` | edit-screen row renderer (per the brief's own citation) | Re-confirmed as a **columns-per-page** loop (4 columns, matches the hardware-confirmed "4 columns of 31px" layout in FW_RND_ANSWERS), explicitly **NOT** a slot-count site | none (unrelated) | n/a | confirmed unrelated, set aside per the brief's own guidance |

**Not located (open, biggest UI risk):** the on-screen "slot icon chain"
draw code (the row of effect-name boxes across the patch screen) and the
effect picker (which effects are offered per slot) — matches FW_RND_
ANSWERS' pre-existing open lead ("The effect picker... was not found").
Not pursued further given this pass's budget. This matters because the
row-drawing code's layout constants (box pitch, how many boxes fit the
LCD width) were never found and may carry their OWN independent
hardcoded slot/width limit — a real risk to the size estimate, not just
an RE gap.

## MIDI/editor

- `c013b8c0 CMPLTU 7` (used-slot-count + free-slot-count combined with
  the picker's header-byte dspload cost, per FW_RND_ANSWERS) — re-cited,
  not re-derived; note this function is more "effect catalog/menu" than
  strictly MIDI (flagging the category mismatch in the brief's own source
  material, not a new finding).
- SysEx patch-dump size: already fully covered by CF_STORAGE_SONNET's Q1
  (the 736-byte PTCF record IS the over-the-wire SysEx patch-dump format
  per PATCH_STORE_ARGON, cited there) — slot_count-generic, no separate
  hardcoded-5 beyond what CF_STORAGE already found. Not re-derived here.
- `11809800`-`11809a30`: confirmed loop `for(slot=0;slot<5;slot++){ CALLP
  0x118099a0(slot) }` immediately followed by calls to the **same**
  `0x1180bcc0`/`0x1180bd10` sanitize pair the main patch loader uses
  (confirmed by direct read). Sits in the `1180 9xxx` address range,
  adjacent to (but not proven to BE) the USB/MIDI string-builder
  functions FW_RND_ANSWERS names nearby (`11803514`, `1180af78`).
  Confidence: **likely**, not confirmed — this function's own caller was
  not traced within this pass's budget, so whether it runs specifically
  on SysEx patch receive (vs. some other UI/reload path) is unresolved.
  Flagged as the clearest remaining lead for a future MIDI-specific pass.

## Other

- `1181822c CMPGT.L2 5,B3,B0`: read in context (inside the `118182xx`
  audio-sample-mixing code, `ADDSP` floating adds, a `CMPEQ.L2 2,B3,B0`
  check immediately follows). `B3` here is combined with other floating/
  mode flags, not indexed into any of the known per-slot tables —
  classified **guess/unrelated** to the slot-count architecture, not
  pursued further, per the brief's "many 5s are unrelated" guidance.
- Not individually triaged this pass: the remaining raw hits beyond the
  ~24 addressed above — spot-check candidates noted but not read:
  `c011fad8`, `c011fbcc`, `c012adf4`, `c012b3ac`, the `c0140xxx` cluster
  (`c01402a8`, `c0140530`, `c0140578`), the `c0143xxx` cluster (5 sites),
  and scattered singletons (`c0148154`, `c014da60`, `c01515ec`,
  `c0154f60`, `c0157c30`, `c0160e94`, `c0167578`, `c016810c`,
  `c0168150`), plus all 139 `MVK ...,5,[AB]n` sites and the 9+11 hex-form
  compares. Given the strong, repeated pattern found everywhere else in
  this pass (the same NUM_SLOTS=5-inlined idiom recurring verbatim at
  dozens of call sites of a small, shared set of helper functions), it is
  **likely** most of these are further instances of the same pattern
  rather than new subsystems — but this is a guess. **Shortcut for a
  future pass:** grep each candidate's surrounding ~20 lines for the
  callee fingerprint `{0x1180bcc0, 0x1180bd10, 0xc016f4d0, 0xc016f4c0,
  0xc014ff44, 0xc016f660, 0xc012b2c4}` (now established in this report)
  to triage quickly without re-reading every site by hand.

## Plan

Order for a 6-slot TEST firmware (static sizing only; nothing implemented
or flashed):

1. **Patch-load clamp + sanitize loops** (confirmed ~12+ sites this
   report + CF_STORAGE's ~14 in `c0132xxx` = roughly 25-30 total one/two-
   immediate `CMPGT`/`CMPGTU` edits across the patch-load + UI-menu
   subsystem, plus the clamp's 2 `CMPGTU`+2 `MVK`). Mechanical and low
   risk per-site, but exhaustive correctness matters — miss one and a
   6th slot's data silently gets clamped/ignored somewhere downstream.
   **Size: medium** (many small edits; do this with a scripted sweep
   keyed on the callee fingerprint above, not manual grep, or sites will
   be missed).
2. **Audio Swi slot dispatch loop** (`11818c28`, `CMPGT 5`->`6`) + grow
   the `0x118133e0` callback table by one 4-byte entry. **Real risk
   found this pass**: the table does not sit cleanly before the stack —
   it is physically INSIDE a larger named "peripheral pointer block"
   (`0x1181329c..0x118134a4`, per FW_RND_ANSWERS) that continues ~176
   bytes past the table's current end (`0x118133f4`). Inserting 4 bytes
   at the table shifts every pointer after it in that block, which other
   hardcoded-address code may reference directly. **Size: small-but-
   risky** (needs either a 4-byte insert with everything after it
   re-addressed, or relocating the table elsewhere in SDRAM).
3. **DSP-load admission gate** (`c0141ad8`-`c0141b48`, `CMPGT 5`->`6`) —
   trivial edit; separately decide whether the `230.0f` budget ceiling
   should rise for a 6th slot's worst case (product decision, not RE).
4. **Per-slot resource tables** (`c01839c0`, `c01839a8`, `c01839f0`) —
   append a 6th entry to all three. Confirmed these are **data tables,
   not computed arithmetic** (correcting the brief's assumed `n*0xa000`
   framing) — simpler in one sense (no multiply to patch) but requires
   flash `.const` layout surgery with the same `.cinit`-shift risk
   CF_STORAGE already flagged for the 53-record and region tables.
   **Size: medium.**
5. **6th slot's physical resources** (a 6th 40 KiB code/const heap + a
   6th `0x81330` work buffer): the work-buffer side needs new SDRAM
   starting at `c04abff0`, which this pass found is **already occupied
   by something else** (unidentified, different size) immediately at
   that address — not confirmed free. **Size: large, highest risk** —
   this is the one finding most likely to force a different plan (e.g.
   relocating other structures, or accepting a smaller 6th-slot resource
   budget) once investigated further.
6. **UI**: reset-all-pages loop (trivial), slot-window table (trivial-
   small, only if the window itself should grow), the 2 traced + ~14-17
   untraced effect-placement loops (small each, needs the fingerprint
   sweep). **The slot-icon-row draw code and effect picker remain
   unlocated** — this is the single biggest open UI unknown and could
   independently enlarge the UI estimate once found.
7. **MIDI/editor**: likely no separate hardcoded-5 beyond what's already
   shared with patch-load (SysEx format already shown slot_count-generic
   by CF_STORAGE); the one open lead (`11809800`'s loop) should be
   traced to its caller before being ruled in or out of scope.

**Total size estimate**: small-to-medium for the mechanical immediate-
edit sweep (steps 1, 3, 4, 6a: on the order of 30-40 individual edits,
each low-risk but requiring exhaustive coverage) wrapped around 2-3
genuinely risky memory-layout changes (step 2's callback-table/
peripheral-pointer-block adjacency; step 4's flash `.const` growth; step
5's SDRAM placement) and one unresolved UI code-location gap (step 6's
icon-row draw code) that could change the overall size materially once
located. **This is not a small job overall** — it is a wide, mostly
mechanical sweep around a handful of real memory-layout landmines.

**Riskiest unknowns** (ranked):
1. Whether SDRAM `c04abff0..c052c320` (where a 6th work buffer would
   live) is actually free — this pass found it is NOT empty at
   `c04abff0` itself, identity/extent of what's there unresolved.
2. Whether `0x118133e0..0x118134a4`'s "peripheral pointer block" has any
   slack, or a 6th callback-table entry forces re-addressing everything
   after it in that block.
3. Whether the 3 `c0183xxx` resource tables have slack in flash `.const`
   immediately after them.
4. The LCD slot-icon-row draw code is still unlocated — unknown whether
   it carries its own independent slot-count/width limit.
5. The `1180xxxx` patch-load/sanitize submodule is bigger than CF_
   STORAGE's Q3 scoped it (4 more confirmed sibling loops found this
   pass alone); a full, non-manual sweep is needed before any patch is
   considered complete, or sites will be missed silently.

## Status

STATUS: done

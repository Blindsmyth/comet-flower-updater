# CF per-patch / global storage analysis (Sonnet, 2026-10-23)

Static analysis only. Builds on `docs/helpers/PATCH_STORE_ARGON_2026-10-17.md`
(DataStore log, PTCF format, pack/unpack, flash map) — not redone here, only
cited. See that file for the base evidence on: record size table
`0x11819be8` (53 u32), 736-byte PTCF records, banks `0x0C0000`/`0x0E1000`,
pack `c0130e04` / unpack `c013150c`, validator `c01312c4`, empty constructor
`c0130ab4`, flash primitives `c01453b4`/`c01454f4`/`c0145568`.

## Q1

### Exact 736-byte PTCF layout for a 5-slot patch (`confirmed`, ground truth from `build/fw/res2_45056.bin`, record0 = file `0x200+idx*0x2E0`)

Wrote `build/cf_storage/parse_ptcf.py` (scratch, not committed) and parsed all
50 factory records directly. Fixed header is 56 bytes (`0x00..0x37`), and this
56 is itself `36 + slot_count*4` (see validator arithmetic below, so it is
**not** a hand-picked constant — it falls out of the generic formula at
`slot_count=5`):

| Offset | Size | Field |
|---|---:|---|
| `0x00` | 4 | `"PTCF"` magic |
| `0x04` | 4 | `active_length` (u32) |
| `0x08` | 4 | version = 1 |
| `0x0C` | 4 | `slot_count` (u32) = 5 |
| `0x10` | 10 | constant `20 00 00 00 00 00 00 00 00 00` |
| `0x1A` | 10 | patch name (ASCII, not NUL-terminated) |
| `0x24` | `slot_count*4` = 20 | 5 × u32 effect IDs |
| `0x38` | variable | chunk area: `TXJ1`, `TXE1`, `EDTB`, `PPRM` (tag+u32 len+payload each) |

Measured chunk sizes across all 50 factory records (`confirmed`, exact byte
counts from the parser):

| Record | active_len | TXJ1 payload | TXE1 payload | EDTB payload | PPRM payload | free (736-active_len) |
|---|---:|---:|---:|---:|---:|---:|
| 0 "MS HiGain" | 308 | 44 | 44 | 120 | 12 | 428 |
| 2 "DreamBox" | 404 | 80 | 104 | 120 | 12 | 332 |
| 40/41/49 "Empty" | 220 | 0 | 0 | 120 | 12 | **516** |

EDTB payload is always `120 = 5*24` and PPRM payload is always `12`, in every
one of the 50 factory records — matching `recon/08`. **Free space ranges from
332 to 516 bytes out of 736** in the factory image; worst case (longest
TXJ1/TXE1 Zoom ever ships, from `c0130ab4`'s blank-record scratch buffers,
which memset 208-byte (8+200) staging buffers for TXJ1/TXE1, `confirmed`
instruction `c0130ad0 MVK 248,A6;SET A6,9,9,A6` -> 248|0x200=0x2F8=760
unrelated scratch, and `c0130ae0 MVK 208,A0` for the TXJ1/TXE1 staging size)
gives a worst-case active_len of `56+208+208+128+20=620`, i.e. **at least 116
bytes always free**, even if a user fills both description fields to Zoom's
own maximum.

### Does unpack/validate walk chunks by tag/length and skip unknown tags? YES (`confirmed`, both functions, full instruction trace)

**Validator `c01312c4`** (disassembly `c01312c4..c01313e0`):
1. `c01312d0 MVK 0x10f2,A4;MVKH 0xc0180000,A4` byte-compares `rec[0..3]` against
   `"PTCF"` (`0xc01810f2`); fails (`A4=0`) if it doesn't match.
2. `c0131304 LDW *B6[3],B0` (= `rec+0x0C` = `slot_count`), `c013130a SHL
   B0,0x2,B0` (`*4`), `c0131314 MVK 36,B3;c0131316 ADD B0,B3,B3` -> `B3 = 36 +
   slot_count*4` = first-chunk offset (`0x38` for `slot_count=5`). `B2 =
   active_length - B3` = remaining chunk-area bytes.
3. Loop (`c0131324..c01313cc`): at each position, `LDNDW *B4(0),B9:B8` reads
   the chunk's 8-byte `(tag,len)` header, copies it to a stack scratch, then
   **compares the tag against `"EDTB"` (`0xc01810f7`) and `"PPRM"`
   (`0xc01810fc`)** byte-by-byte (`c0131348..c013139c`). Regardless of whether
   either matched, `c01313aa LDW *B15[2],B0` reloads the SAME header's length
   field and unconditionally does `B2 -= B0; B3 += B0` (`c01313ae/c01313b0`)
   — i.e. **it advances past every chunk by that chunk's own declared length,
   whether or not the tag was recognized.** It only fails if `remaining < 0`
   before both `EDTB` and `PPRM` were seen. No other tag is checked, and no
   tag causes a reject.
4. Conclusion: **an unrecognized chunk tag (e.g. a custom `"CFRT"`) does NOT
   fail validation** as long as it sits inside `active_length` with a correct
   length field and `EDTB`/`PPRM` are still found somewhere in the walk.

**Unpack `c013150c`** does the *identical* walk (`c0131578..c0131678`,
same 8-byte header read, same tag-compare-loop idiom against the same two
string constants `0x10f7`/`0x10fc`, same unconditional `remaining -= len;
pos += len` at `c013164c..c0131654`). It **never compares against `"TXJ1"` or
`"TXE1"`** anywhere in this function — those two tags are simply skipped like
any unrecognized tag (see Q2). On match it calls `CALLP 0xc0131484` (EDTB ->
84-byte-per-slot unpack) or `CALLP 0xc0131468` (PPRM unpack). If the walk
exits without having found both `EDTB` and `PPRM` (`B11` flag at
`c0131680`), it falls back to `CALLP 0xc0130ab4` (blank constructor) then
re-unpacks that — matches PATCH_STORE_ARGON's "fails validation" note,
now traced end-to-end.

### Does pack rebuild the record, dropping anything else? YES (`confirmed`)

`c0130e04` (pack): zeroes the **entire 736-byte destination** first
(`c0130ac4 CALLP 0xc0167b00` with `A6 = 224|SET(bit9)=0x2E0=736`, i.e.
`memset(dst,0,736)`), then writes the fixed header (name, slot_count — see
Q3), and emits exactly four chunks by calling a generic "create/find chunk"
helper (`CALLP 0xc0169fc0`) four times: `TXJ1` and `TXE1` are populated from
`prev_ptcf` if one was passed in (`c0130e6c CALLP 0xc016f740` /
`c0130e74/c0130e94 CALLP 0xc016f730`, which are find-chunk-by-tag lookups
against the caller-supplied previous record — this is how Zoom round-trips
the PC-editor description text across a save without the 904-byte struct
ever holding it), else an empty 8-byte header is written
(`c0130e82..c0130eb0`, offsets `16/32/64/128` into stack scratch). `EDTB` is
rebuilt from the 904-byte struct's slot array with declared length
`slot_count*24` computed at `c0131076..c0131080` (`LDW *A4[3],B1` =
dst `slot_count`; `SHL B1,0x4,B0` then `ADDAD.D2 B0,B1,B0` = `B1*16 + B1*8 =
B1*24`). `PPRM` is rebuilt with a hardcoded length `12`
(`c01310d8 MVK 12,B0`). **No fifth chunk is ever considered.** Because pack
memsets the whole record to zero first and only ever (re)writes these four
chunks, **any custom chunk placed past `active_length` in a live record is
not merely "ignored" — it is zeroed out byte-for-byte the next time that
patch is saved** (AUTO SAVE, manual STORE/SWAP, or SWAP's `c0131128`
raw-copy path all funnel through this same pack).

**Answer to Q1's "what would we have to patch":** nothing in the validator
is required to change (it already tolerates an extra chunk). To actually
*keep* a custom `"CFRT"` chunk alive across the live edit/save cycle, both
`c0130e04` (pack, so it re-emits the chunk every save) and `c013150c`
(unpack, so it extracts the chunk's payload into the working struct on every
load) need a small addition each — modeled exactly on the existing
`TXJ1`/`TXE1` find-and-copy-from-prev / find-and-extract pattern already in
both functions. A ~64-byte `CFRT` chunk (72 bytes with header) comfortably
fits in the worst-case 116 free bytes computed above.

## Q2

### Are the 904-byte struct's reserved slots 5..9 or the TXJ1/TXE1 chunks available/unused? (`confirmed` for TXJ1/TXE1 non-use; `likely` for reserved-slot safety)

- **`TXJ1`/`TXE1` payload is never read into the 904-byte working struct.**
  Confirmed above: `c013150c`'s chunk walk only ever string-compares against
  `"EDTB"` (`0x10f7`) and `"PPRM"` (`0x10fc`); `"TXJ1"`/`"TXE1"` are never
  compared against, so their bytes are walked past (by declared length) and
  discarded by this function. PATCH_STORE_ARGON's unpacked-struct offset
  table (`+0x000..+0x387`) has no field for description text, consistent
  with this. These chunks exist purely for round-tripping Zoom's Handy
  Guitar Lab PC-editor description fields (Japanese/English) through
  `pack`'s `prev_ptcf`-copy step (Q1); the G1X Four firmware's own LCD/UI and
  DSP never consume them. **They are not "free" storage** in the sense of
  unused flash — they occupy real bytes in every record — but they are
  firmware-invisible payload: overwriting them would not break any firmware
  codepath that reads a `PTCF`, only Handy Guitar Lab's own display of a
  patch's description (not independently confirmed, since the PC editor's
  behavior wasn't inspected here — `likely`).
- **The 904-byte struct's reserved slots 5..9 (`+0x1A4..+0x347`, 420 bytes)
  are zeroed once per unpack and never subsequently written for a 5-slot
  G1X Four patch, but they are NOT independently persisted.** `c0131518`
  zeros the whole 904-byte struct at the top of unpack (`MVK 113,A6;SHL
  A6,3,A6` = 904). The EDTB-unpack call (`c01315d6 CALLP 0xc0131484`) is
  invoked with its length argument `A6` loaded from the chunk's own on-disk
  declared length (`c01315cc LDW *+B15[67],A6`, the EDTB chunk's length
  field, `120` for a 5-slot record) — so only `120/24=5` slot entries are
  ever written by this call; slots 5..9 of the struct stay zero. Symmetrically,
  pack's EDTB-write length is `slot_count*24` (Q1), so pack never reads slot
  entries past `slot_count` either. **Using `+0x1A4` onward as scratch for
  custom per-patch CF data would be safe from Zoom's own code colliding with
  it (confirmed nothing else in `c0131484`/`c0130e04`'s traced paths touches
  it for `slot_count<=5`), but it would NOT survive a save/reload by itself**
  — it is RAM-only working state; `pack()` never serializes bytes past
  `slot_count*84` in the slot area into any `PTCF` chunk. So this reserved
  RAM area is the natural **destination** for an unpacked custom chunk's
  payload (what `unpack` writes a `CFRT` chunk's bytes into), not an
  independent persistence mechanism — it still needs the Q1 pack/unpack
  hooks to round-trip to flash.

## Q3

## Q3

### Is slot_count=5 a constant baked into the pack/unpack/validate pipeline, or read from the field? **Read from the field everywhere in the storage format itself** (`confirmed`)

Three independent instruction-level confirmations that the PTCF format path
is already generic in `slot_count`:

1. **Validator** (`c0131304..c0131316`, quoted in Q1): chunk-area start
   offset is computed as `36 + slot_count*4` from `rec[+0x0C]`, not a literal
   `56`.
2. **Pack's EDTB length** (`c0131076..c0131080`): `B1 = dst[+0x0C]`
   (`slot_count`, itself just written into the record from the 904-byte
   struct's `num_slots` field at `+0x384` by `c0130e4c..c0130e5a`), then
   `B0=B1*24` via `SHL B1,0x4,B0 (B1*16); ADDAD.D2 B0,B1,B0 (+B1*8)`. The
   EDTB chunk's on-disk declared length is **computed from slot_count, not
   hardcoded**.
3. **Unpack's EDTB-entry loop bound** (`c0131484`, called from
   `c01315d6` with `A6` = `c01315cc LDW *+B15[67],A6`, the EDTB chunk's own
   on-disk length field, e.g. `120` for 5 slots): the per-slot-entry
   (84-byte struct <-> 24-byte on-disk) copy loop inside `c0131484` is driven
   by this length argument, which came from the chunk header the firmware
   itself wrote at save time — **not a literal 5**.
4. **The 904-byte in-RAM struct already has room for 10 slots** (confirmed
   independently here: `c0131518 MVK 113,A6;SHL A6,3,A6` = zeroes 904 bytes
   total = `113*8`; slot stride is `84` bytes everywhere these functions
   touch it, `9052 MVK 84,A0` recurring literal in `c0131484`/`c0130e04`/etc,
   consistent with PATCH_STORE_ARGON's offset table: `0x000..0x347` = 10 ×
   84B). 6 or 7 slots need **zero growth** of this struct or the 736-byte
   record (worst-case active_len for 7 slots: `56+8+8*2slots+208+208+128+
   2*24+20 = 676`, still `<736`; see Q1 free-space table).

**The actual hardcoded "5" gate is downstream of unpack, in the post-load
sanitize/load path** (`confirmed`, function `11806450`, called from the
patch-load chain `c012f878 -> 118075e4 -> 1180738c`):

```
11806466  LDHU.D1T1  *A4[0],A1          ; A1 = num_slots (working struct +0x384)
11806468  CMPGTU.L1  0x5,A1,A0          ; A0 = (num_slots < 5)
1180646c  [A0] BNOP  0x11806488,5       ; -> force num_slots = 5
11806470  CMPGTU.L1  0x6,A1,A0          ; A0 = (num_slots < 6), i.e. ==5 given above false
11806474  [A0] BNOP  0x11806494,5       ; num_slots==5 -> leave unchanged, skip the clamp
11806478..11806486                     ; (fallthrough, num_slots>5) force num_slots = 5
11806488  MVK 5,A0; STH A0,*A4[0]       ; one clamp site
11806492  MVK 5,A0; STH A0,*A4[0]       ; the other clamp site (num_slots<5 branch target)
```
This two-comparison / two-store routine forces `num_slots` to exactly `5`
whenever it isn't already 5, immediately after `unpack` and before anything
downstream (effect `.ZD2` loading, UI) ever sees the patch. **This is the
single gate that would need to change (both `CMPGTU` immediates and both
`MVK 5` immediates) to allow 6 or 7.**

**Sites that loop a literal `5` times downstream of the clamp, inside the
`c012f878 -> 118075e4 -> 1180738c` call tree** (`confirmed` presence by
direct grep + spot read of each; not all individually traced to their full
purpose):

| Address | Instruction | Context |
|---|---|---|
| `11806450` region, `11806468`/`11806470`/`11806486`/`11806492` | `CMPGTU 0x5`/`0x6`, `MVK 5` ×2 | the num_slots clamp itself (above) |
| `118060d4` | `CMPGT.L1 5,A11,A0` | per-slot sanitize loop (calls `1180bcc0`, effect-ID range check per PATCH_STORE_ARGON's `11806450..492` note) |
| `118061f8` | `CMPGT.L1 5,A2,A0` | a second per-slot sanitize loop (different register, not individually traced) |
| `11807438` | `CMPGT.L1 5,A10,A0` | loop inside `1180738c`'s slot-resource-check path (calls `11805f14`) |
| `11807494` | `CMPGT.L1 5,A11,A0` | adjacent resource-table loop (uses record-size-table-style stride `53,SHL 4`... different table, not traced further) |
| `118074d4` | `CMPGT.L1 5,A10,A0` | adjacent loop, calls `1180b7b0` |
| `11807504`, `11807570` | `CMPGT.L1 5,A10,A0` | **the effect `.ZD2` binary loader loop** (`CALLP 0x118063c8` per slot, with a conditional unload call `CALLP 0x118072ac` when the slot's effect id changed) — this is the loop that actually loads each slot's DSP effect binary into memory |

A broader grep for the same `CMPGT.L1 5,A<n>` / `CMPGT.L1 5,B<n>` idiom
inside just the patch-load/DataStore module address ranges
(`c012f000-c0138000`, `11800000-11809000`) found **24 occurrences total**
(10 shown above plus 14 more in `c0132xxx`, not individually traced — that
range is adjacent to the manual UI `STORE`/`SWAP` handlers PATCH_STORE_ARGON
already located at `c0138ca4..c0138d88`, so these are `likely` UI/menu
slot-selection loops, a separate subsystem from the storage format).

**Sizing:** the **storage format itself (pack/unpack/validate) is `small`**
— it is already slot_count-generic, confirmed by instruction trace, no
patch needed there at all. The **patch-load/sanitize layer is `small` in
patch-count** (the clamp plus ~9 confirmed sibling loops, each a one- or
two-immediate edit, same repeated idiom) but **cannot be called `small`
overall** because this report did not search the DSP audio-processing
dispatch (which actually runs 5 effects per audio block — a different
module, not reached from `c012f878`) or the LCD/menu slot-selection UI
(the `c0132xxx` region above, and `c013cxxx` `UpdateUI`/`LooperUI` task
code per `FWMAP.md`'s task list) for their own hardcoded-5 loops — those are
very likely present and are `medium`-to-`large` in scope (rendering, menu
state machines, DSP scheduling) and were **not inventoried here** (out of
this report's PTCF/DataStore-storage focus). **Overall Q3 sizing: small for
storage, unknown-but-likely-medium/large for DSP+UI — recommend a separate,
dedicated pass over `c013cxxx`/`c016xxxx` before attempting 6/7 slots.**

## Q4

## Q5

## Status
In progress.

# 00: runtime-library and kernel functions (wave 0)

Scope: the 80 most-called functions named in the wave-0 brief, plus every
function coverage.py detected in c0169f20..c016f780 (fact sheets chunk_17
and chunk_18: the tail of the code section, c016f7a0 being the last
detected function start in the whole firmware). Union: 285 distinct
addresses, listed below in address order per FWMAP.md's table format.

Summary: this range is **not** purely compiler-runtime/kernel code as the
brief's own wording hinted it might be -- it is a mix of:
- the TI C6000 runtime-support primitives it's named for: integer divide
  (`c0168580` unsigned, `c01675c0` signed), float divide (`c016c240`),
  word-granularity memcpy (`c016d4c0`), memset (`c0167b00`, outside the
  range but a top target), and the universal register save/restore
  helpers `c016e020`/`c016e000` (865/853 callers -- by far the most-called
  functions in the whole firmware);
- a small number of genuine SYS/BIOS-style kernel primitives: a
  semaphore pend/post pair (`c0150b20`/`c01628e0`, confirmed this wave by
  reading `c01628e0`'s DINT-guarded count increment) and a raw CSR
  get/set pair (`c016e4c0`/`c016e4e0`) that looks like the mechanic behind
  Hwi_disable/Hwi_restore;
- a large population of tiny, mechanically unambiguous **accessors**:
  getters/setters for single B14 global slots, getters for fixed global
  words/pointers, and struct-field getters off an argument pointer;
- a large population of **tail-call veneers and "preload a constant then
  jump to a shared handler" trampolines** -- in particular, families that
  all jump into `c016ba40` (inside `c016b9c0`), `c0166a80` and `c015a520`
  with a different preloaded pointer each time. These look like
  per-item wrappers for a settings/menu table (FWMAP.md documents a
  settings-menu table around c0182b38) or similar per-slot UI records,
  **not** kernel code -- flagged here so later helpers don't mistake the
  bulk of chunk_17/18 for RTOS internals;
- `c016ec20`, the last detected function start in the firmware (2912
  bytes, running to c016f7a0, just past our range), is itself **not one
  routine**: it is a run of small long-branch veneers that coverage.py's
  stub-folding did not separate into individual functions (recon/15,16,18
  had already traced several of the addresses inside it: c016ef60 ->
  1180a954, c016f1a0/b0/d0 -> 118094xx, c016f450/460/4c0/4d0, c016f740).
  Treat addresses inside it as veneers, not as one meaningful function.
- coverage.py's caller counts mix real CALLP call sites, plain-branch
  tail-calls, and (for a handful of addresses) internal shared-epilogue
  fan-in; `c012daac`, `c0127f58`, `c0139490` and `118037d6` have large
  "caller" counts but are shared tails/epilogues reached only by branch
  or by appearing as filler entries in function-pointer tables, not real
  independently-called library routines. Checked via a refkind pass
  (CALLP vs branch vs `.word` reference counts) before trusting any
  caller count in this report.

Method: a scripted pass (`build/fwmap0/*.py`) pulled per-function size,
callers, callees, strings, B14 slots and roots from the existing fact
sheets, then classified each address by structural shape (B14
getter/setter, constant-return leaf, address-constant getter, tail-call
veneer, MVC/CSR pair, double-word multiply, SPLOOP copy, divide shape).
Every "confirmed" row below was checked by reading the actual
disassembly; "likely" rows combine a clear structural shape with
supporting call-graph/string evidence but were not traced instruction by
instruction; "guess" rows are honest placeholders (mostly small
application-level wrappers in the chunk_17/18 sweep) with whatever
callee/string/B14 evidence was available, per SAVE_PROTOCOL's "a short
honest guess beats a wrong confirmed."

| addr | name | role | conf | evidence |
|---|---|---|---|---|

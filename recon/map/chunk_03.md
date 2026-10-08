# chunk_03: c0122924..c0128134 (150 functions)

Summary: this range holds three clearly separated subsystems. (1)
c0122924..c0124fc0 (~100 functions) is the TI ELF/dynamic-loader
machinery that loads a 5-slot effect module image: header/magic
validation (`c0123478` checks `\x7fELF`, `c01234c4` checks
`e_machine==140`=EM_C6000), section/program-header field population
(`c0123848`'s internal dispatch at `c012387c` fed by a ~10-entry
function-pointer table at `0xc0183d04..3c`, one arm per `Elf32_Shdr`
field), module object creation (`c0123ce4`), PT_LOAD segment loading
(`c01242bc`), special-symbol lookup (`c0124584`, `c0124cf8` for
`__TI_STATIC_BASE`), and relocation-handler selection/invocation
(`c01235ec`/`c0123824`/`c0122d50`, all keyed off B14[132]) feeding the
EM_C6000 handler `c0133f28` outside this range -- this matches recon/14
and recon/18's prior ELF-loader tracing almost exactly and most of
those rows cite it directly. A lock/error-flag pair recurring through
this cluster, `locked_subsystem_op_115`/`validate_and_set_error`
(both keyed on B14[115], already named in 00), guards most stages.
(2) c0125000..c0127070 (~35 functions) is a UI/rhythm bitmap-and-draw
cluster rooted in MainApp/RhythmService/UpdateUI: `c01256c4` is
confirmed (read the code) to be a second "set a run of bits" SPLOOP
primitive -- structurally identical to the already-named LCD primitive
`gfx_set_bit_range` (c011c508, see 00) but targeting a different
bitmap base (`0xc0183ae4`), and is called from 13 sibling draw/pattern
functions. `c0126624`/`c01268e0`/`c01269d4` (700/244/700 instructions,
two near-identical) sit under the already-named `orchestrator_c0126624`
(c0126c90, see 00) and use the signed-divide helper, consistent with
rhythm-pattern timing math. (3) c0127440..c0128134 (~25 functions) is a
MIDI message-building cluster: a table-driven checksum/CRC step
(`c0127440`, read the code), per-parameter "jump-table" entry functions
(`c0127daa..c0127f48`) that each call one small worker then return via
the already-named shared epilogue `epilogue_pop_b3_shared2`
(c0127f58, see 00), driven off a function-pointer table at
`0xc0183b74..c0183c3c`, all exercising the already-named
`midi_tx_locked`/`midi_tx_n` senders (c01274cc/c0127500, see 00) and a
cluster of B14 slots (30-38, 112-119) that look like per-CC-parameter
state.

Functions already named in `recon/map/00_library_kernel.md` (listed
here as "see 00", not re-analyzed): `c0123a74` (thin_arg_adapter),
`c0126c90` (orchestrator_c0126624), `c01274cc` (midi_tx_locked),
`c0127500` (midi_tx_n), `c0127f58` (epilogue_pop_b3_shared2).

| addr | name | role | conf | evidence |
|---|---|---|---|---|

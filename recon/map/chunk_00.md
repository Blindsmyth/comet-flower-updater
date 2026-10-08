# chunk_00: 11800400..118072ac (150 functions)

Scope: the start of the AIS-loaded L2 executable region (recon/16's
`11800400..1180bd40` "AIS executable section; GPIO, drivers,
interrupt/control tasks"). This range holds: two GPIO/peripheral
register init routines run from `c015d428` at boot (`1180044c`,
`11801aa8`, plus a bit-set/bit-clear pair `11800400`/`11800424`); a
locked, low-level serial-transfer driver (`1180673c`, confirmed by
recon/15 and by reading its lock+dispatch code here) built on a small
family of register-poll helpers (`11801498` and siblings) and an
EDMA/PaRAM descriptor builder call-through (`11806700` -> `1180a954`,
confirmed per recon/18); a large 1180-region MIDI command-table
subsystem (`11802a90`..`11803a28`) that reuses the same MIDI lock
B14[161] the c0-region's `c01274cc` (`midi_tx_locked`) uses, dispatched
through a 9-10 entry function-pointer table at `c01840fc..c0184138`
ending in the shared epilogue `118037d6` (already named in 00); a
two-tier rhythm-pattern-table UI renderer family (`11803a60..11804124`
"small" variant, `11804150..118048fc` "large" variant) built on the
already-confirmed `rhythm_get_field117`/`gfx_set_bit_range`; a
TunerService pitch-period measurement core (`11804a44`, reads a
hardware tick counter three times and computes deltas); and the start
of a RhythmService playback/UI dispatcher family (`11806ce0`,
`11806eb4`, `1180710c`) continuing into chunk_01. A dense population of
tiny per-item callback/table-pointer stubs (many `ptr@` references into
`c0185cxx`-`c0186874`) look like settings/menu-item records, consistent
with FWMAP.md's documented settings-menu table.

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| 11800400 | gpio_shadow_set_bit12 | sets bit 12 of the word at offset 0x60 of the struct whose pointer lives at global `0x11813468` (read-modify-write, not a HW SET register) | confirmed | `11800414 LDW *+A3[A4=96]; 1180041a SET A4,12,12,A4; 11800420 STW A4,*+A3[A5=96]` |
| 11800424 | gpio_shadow_clear_bit12 | clears bit 12 of the word at offset 0x180 of the same struct `*0x11813468` | confirmed | `11800440 LDW *B4[0]; 11800444 CLR B4,12,12,B4; 11800448 STW B4,*+A3[0]` with B4=A3+0x180 |
| 1180044c | hw_pinmux_init_block | large (4172 B) peripheral/pinmux init: writes two magic words into fields [14]/[15] of the struct `*0x11813468`, then a long run of CLR+SET passes on 3-4 bit sub-fields all at offset 0x120 of the same struct (bit groups 28,24,20/21-23,16,13,9-11... descending) -- a register-field configuration table, not traced to a specific peripheral name | likely | `11800470 STW A5,*A4[14]`; `11800472 STW A3,*A4[15]`; repeated `CLR.S1 A3,n,m,A3` / `SET.S1 A3,k,k,A3` / `STW *+A4[0x120]` triples from `11800490` to `118004fc` (and beyond, not fully read) |
| 11801498 | serial_cfg_mode_and_poll | sets a 5-bit mode field in reg+0xa28 to 3, sets reg+0 to 1, then busy-polls reg+0x128 bit 0 (via SPLOOP) and reg+0x828 bit 27==3 before returning -- a configure-then-wait-ready step of the shared serial driver | confirmed | `118014c4 CLR B5,0,4,B5; 118014c8 OR 3,B5,B5; 118014cc STW B5,*+B4[0]`; `118014e8 LDW *+A6[0]; 118014ec AND 1,A3,A0` SPLOOP busy-wait; `11801508 LDW; 1180150c EXTU A3,27,27,A3; 11801510 CMPEQ 3,A3,A0` second SPLOOP busy-wait |
| 118015f4 | serial_phase2 | 452 B sibling of `11801498` (same two callers `1180673c`/`c014f5e4`), touches mmio region `01e27000` -- a further configure/poll phase of the serial driver, not read | guess | roots match 11801498 exactly; mmio=01e27000 |
| 118017b8 | serial_phase3 | 512 B sibling, touches mmio `01c10000` and `01e27000` -- likely the data-transfer phase (two peripheral regions at once) | guess | mmio=01c10000,01e27000; same caller pair |
| 118019b8 | serial_phase4 | 240 B sibling, touches mmio `01c10000` only -- likely a GPIO-only (chip-select?) phase | guess | mmio=01c10000; same caller pair |
| 11801aa8 | hw_init_block2 | 3896 B, callers `c015d428` (same as `1180044c`), touches mmio `01c10000`+`01e27000` -- a second large peripheral-register init block run at boot, not traced in detail | guess | n=3896; mmio=01c10000,01e27000; callers=c015d428 |
| 118029e0 | shared_init_helper1 | 48 B, roots DataStore/MIDI/MainApp/PreLoad/RhythmService/UpdateUI, called from the per-task init-table entries `c01453b4`/`c01454f4`/`c0145568` | guess | callers=c01453b4,c01454f4,c0145568 |
| 11802a10 | shared_init_helper2 | 48 B, same roots, single caller `1180b040` | guess | callers=1180b040 |
| 11802a40 | div_wrapper_a | thin wrapper around the integer-divide helper `rts_div32_variant`, caller `11802fcc` | likely | calls=c0169980; n=40 |
| 11802a68 | div_wrapper_b | sibling of `11802a40`, same shape, caller `1180382c` | likely | calls=c0169980; n=40 |
| 11802a90 | midi_tx_forward_1180 | reorders args (A4->B4, B4->A6, A4=0) and tail-calls the veneer `0x1180bd20`, which resolves (MVK 0x4dc8/MVKH 0xc0140000) to `c0144dc8`, the shared UART/MIDI transport also used by `c01274cc`/`c0128580` | confirmed | `11802a98 CALLP 0x1180bd20,B3`; `1180bd20 MVK 0x4dc8,B31` (-> c0144dc8); 9 callers, all in the 1180-region MIDI sender family below |
| 11802aa4 | table9_index_118133cc | indexes a 9-byte-stride table at `0x11810720` using a counter read from global `0x118133cc` (A1 = A0*8+A0) | likely | `11802ab0 LDW *A4[0],A0` (A4=0x118133cc); `11802ab2 SHL A0,3,A1; 11802ab4 ADDAW A1,A0,A1`; B7=0x11810720 |
| 11802b50 | unk_1180_2b50 | 20 B, roots MIDI/MainApp, single caller `c01289ec` | guess | callers=c01289ec |
| 11802b64 | unk_1180_2b64 | 12 B, roots MIDI/MainApp/UpdateUI, callers `c0128788`/`c0134d04`/`c013c54c` | guess | callers=3 |
| 11802b70 | midi_stage_copy_1180 | copies a word+byte pair from global `0x118133d0`/`+4` to `0x11810320`/`+4` -- stages an outgoing byte+flag before the transport call; same 9-caller set as `11802a90` | confirmed | `11802b78 LDW *A4[0],A1` (A4=0x118133d0); `11802b7a LDB *A4[4],A0`; `11802b8a STW A1,*B4[0]`; `11802b8c STB A0,*B4[4]` (B4=0x11810320) |
| 11802b90 | midi_tx_locked_1180 | sem_pend(B14[161]) -> calls `11802a90` (tx forward) and `11802b70` (stage copy) and `c013b8a8` -> sem_post(B14[161]) -- the 1180-region analogue of the c0-region's `midi_tx_locked`, same lock slot B14[161] | likely | b14=138,161; calls=11802a90,11802b70,c013b8a8,bios_sem_pend,bios_sem_post; B14[161] matches c01274cc's confirmed MIDI lock |
| 11802c44 | midi_send_variant1_1180 | locked-sender case: calls `11802b90` then `11805dc0` -- one of ~9 "send MIDI message variant N" cases fed by the table at c0184100-138 | likely | callers=c0168144; calls=11802b90,11805dc0 |
| 11802c58 | midi_send_variant2_1180 | sibling of variant1, calls `11802b90` then `11805dd8` | likely | callers=c0168418; calls=11802b90,11805dd8 |
| 11802c70 | midi_send_variant3_1180 | sibling, calls `11802b90` then `11805de8` | likely | callers=c0168434; calls=11802b90,11805de8 |
| 11802c88 | midi_send_variant4_1180 | sibling, calls `11802b90` then the table-index helper `c0140240` (not the usual `1180xxxx` slot helper) | likely | callers=c012ec80; calls=11802b90,c0140240 |
| 11802ca0 | midi_send_variant5_1180 | sibling, calls `11802b90` then `11805f14` | likely | callers=c0168434; calls=11802b90,11805f14 |
| 11802cb8 | midi_send_variant6_1180 | sibling, calls `11802b90`, `c013b8a8`, and the known table[index] getter `cfg_table_index_1181191c` (c0140320) | likely | callers=c0134650,c013498c; calls=11802b90,c013b8a8,c0140320 |
| 11802cd4 | midi_send_variant7_1180 | sibling, calls `11802b90` then `11805e64` | likely | callers=c016846c; calls=11802b90,11805e64 |
| 11802cec | midi_send_variant8_1180 | sibling, calls `11802b90` then `11805ec4` | likely | callers=c0168488; calls=11802b90,11805ec4 |
| 11802d08 | midi_send_full1_1180 | full locked send (own sem_pend/post on B14[161], not via `11802b90`) calling `11802a90`+`11802b70` directly | likely | callers=c0150738; calls=11802a90,11802b70,bios_sem_pend,bios_sem_post; b14=161 |
| 11802d44 | midi_send_full2_1180 | sibling of `11802d08`, same shape, caller `c01507d8` | likely | b14=161; calls=11802a90,11802b70,bios_sem_pend,bios_sem_post |

# chunk_17: c0169f20..c016e020 (150 fact-sheet functions + hidden starts)

Summary: TBD (fill in after mapping).

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| c0169f20 | block_alloc_init_header | Call allocator c016db80; if result null return 0, else store a 2-word header (self ptr at [0], limit ptr at [1]) and hand back ptr+8. | likely | c0169f2c CALLP 0xc016db80,B3; c0169f44 [!A0] B c0169f88 (return 0) vs [A0] B c0167f60; c0169f6c STW A0,*+A0[0]; c0169f70 STW A10,*+A0[1]; c016a080 ADD A10,8,A10 |
| c0169fc0 | variant_record_copy | Copy a variable-length record from B4 into A5 using mask A6: bit0/1 pull one byte each (2nd byte-indexed), bit2 a word, remaining bits (A6>>3) a SPLOOP of double-words. | likely | c0169fcc/d8 LDB *B4++[1]/[2]; c0169fe8 LDNW *B4++[1]; c0169ff4 SPLOOPW LDNDW/STNDW double-word copy loop gated by A6 bit fields |
| c016a060 | fp64_sub_align_slow | Software double-precision subtract slow/denormal path: extract exponent field (EXTU A5,1,21), compute shift amount, align mantissas (SHL/ANDN), then SUBDP. | likely | c016a070 EXTU.S1 A5,1,21,A3 (exponent extract); c016a0ec SUBDP.L1X A9:A8,B7:B6,A7:A6 |
| c016a100 | fmt_render_wrapper2 | Render a value into the buffer at A4 via core formatter c014fa40, passing fixed helper-code pointers c016ae40 and c016d540 baked in as A8/B6 args. | likely | c016a140 MVK 0xffffae40,A8; MVKH 0xc0160000 -> c016ae40; c016a12c/48 B6=0xc016d540; c016a150 CALLP 0xc014fa40,B3 |
| c016a1a0 | heap_coalesce_list_walk | If a global free-count at c017e35c is >0, jump into a shared block-merge loop (hosted at c016d900) that combines adjacent free-list nodes (size/next/prev at word offsets 1-4) and clears the merged tail. | likely | c016a1a8/ac MVK/MVKH -> A3=c017e35c; c016a1c8 [!A0] skip, else c016a1cc B 0xc016d900; c016a1f0/fc ADD A3,A5/ANDN merge math; c016a200 STW A3,*A4[2] |
| c016a240 | sem_pend_dispatch | Generic "pend on caller-supplied semaphore" adapter: forwards args to c015a520; on failure tail-branches to c015a020 with two fields loaded from the status struct, else returns 0. | likely | c016a26c CALLP 0xc015a520,B3; c016a290 [!A0] B c016a2dc (return 0) vs [A0] load *+A3[0/1] then B c015a020; callers include bios_sem_pend, locked_lookup_big (fact sheet) |
| c016a2e0 | diag_counter_tick_cb | Callback (registered via ptr@ c01864b4): increments two adjacent counters at c0182054/c0182058, calls stat hooks c0168e80 and c016e7c0, then either returns or tail-calls c0164240 with a value from the counter struct+12. | likely | c016a2e8/ec A10=c0182054,A11=c0182058; c016a314 CALLP 0xc0168e80,B3; c016a31c CALLP 0xc016e7c0,B3; ptr@ c01864b4 per fact sheet |
| c016a380 | bios_biglock_pend | Pend on the single fixed big-subsystem lock (descriptor at c0180ee0) via c015a520; used by nearly every task and by big_subsystem_init. | likely | c016a384/90 B5=0xc0180ee0 (fixed, unlike c016a240's caller-supplied B5); c016a3ac CALLP 0xc015a520,B3; fact-sheet callers include c0155ac0=big_subsystem_init and all task roots |
| c016a4c0 | buf_pool_slot_init | Initialize a pool of N (global count at c0181a1c) buffer-descriptor slots: for each slot, memset its backing buffer (size field<<5 bytes) via c0167b00 and mark the slot free (flag fields set). | likely | c016a4d0 A10=LDW c0181a1c (count); c016a50c CALLP 0xc0167b00,B3 (memset, named row example in FWMAP.md); c016a52c/38 STW A5/A3 into +3/+5/+6 slot fields |
| c016a560 | ringbuf_push_byte | Generic circular-buffer helper (single 480-byte function, several internal entry points reached by local branch): validates a caller string/pointer, computes free space in a ring (tables at c0181a3c/c01821f4), and pushes one byte (A12) at the tail with wraparound, calling c016e9a0 on wrap/full. | guess | c016a58c LDB *A10++[1],A0 scan loop; c016a658 SUB A3,A4,A3 (distance calc); c016a6f4 STB A12,*+A5[A3] (ring write); c016a704 [B0] STH A31,*+A11[4] (full flag) then CALLP 0xc016e9a0,B3 |

## Data

## Open questions

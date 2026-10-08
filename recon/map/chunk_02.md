# Chunk 02 function map: 1180b020..c0122924

Summary: this range splits into two unrelated subsystems. The low addresses
(1180b020..c011f8d8) are an LCD/graphics primitive layer for UpdateUI/MainApp
screens: a paged (8-row-per-byte) monochrome framebuffer with a single-bit-set
primitive (c011b5d0, confirmed: byte = buf+(y>>3)*128, bit = y&7), a bulk
bit-range/rectangle-fill primitive (c011adc0, called through the already-named
gfx_set_bit_range c011c508), a line/shape-draw family built on those two
primitives (uses the signed-divide helper for slope) sharing a common fan-out
dispatcher (c011eef0, called from the already-named big_mvc_subsystem
c011f8d8), and a cluster of small icon/box-fill wrappers layered two deep
(outer wrapper -> inner gfx_set_bit_range caller). From c011fa20 onward
(c011fa20..c0122904) the range is almost entirely the SoC's integrated USB0
device-controller driver that recon/15,17,18,20 already partially traced:
CPPI completion-queue pop/test/push primitives (c011fa20/fa54/fa70), the USB
top-half ISR actually entered at the c011fc8c label inside c011fb94, five
fixed-stride per-endpoint I/O-state-reset helpers (c011fd40/fd98/fdc8/fe20/
fe4c) reused by both the global endpoint-table clear (c011fe70, confirmed in
recon/17) and the per-endpoint FIFO configurator (c01212e0, confirmed in
recon/17), the TX/RX CPPI descriptor build-and-submit chain (c0120250
confirmed; c012032c/c012042c/c01204b4/c0120550/c0120650/c0120904/c0120acc/
c0120b2c/c0120ca4 as its wrapper layers), EP0 control-transfer helpers
(c0122370 FIFO read, c0120ef8 stall-set, c0122710 speed selector, all
confirmed by direct recon quotes), the USB/controller event decoder c0121d80
(confirmed by recon quote) fanning out through c01219f4/c01216a8/c0121804/
c0121960/c0121b4c into a small endpoint-state-machine case table (c0121c54/
c74/c94/ca2/cb0/cc4, reached by pointer not CALLP, same "settings-table
trampoline" shape flagged in 00_library_kernel.md), and the controller init
path c0122260 (confirmed) with its SYSCFG/CPPI-region sub-steps (c011ffc0,
c0120004, c01215e4, c01221e0). A handful of functions (c01200f0, c01215a8,
c01221b8, c0122358, c0122900) are tiny stubs whose only callers sit outside
this chunk; their role is a guess from size/caller context alone. Eight
functions in this range are already named in recon/map/00_library_kernel.md
and are skipped here (see 00): 1180b020, c011c508, c011cb64, c011d4d8,
c011d84c, c011d938, c011f87c, c011f8d8.

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| 1180b020 | see 00 | ui_event_post_byte | - | - |
| 1180b040 | cfg_apply_and_notify | calls 11802a10 then tail-veneer 1180b080->c0160a94, then returns 1 (success) | likely | 1180b044 CALLP 0x11802a10,B3; 1180b048 CALLP 0x1180b080,B3 (veneer resolves to c0160a94); 1180b04c MVK 1,A4; roots DataStore,MIDI,MainApp,PreLoad,RhythmService,UpdateUI |
| 1180b060 | cfg_get_global_11813488 | getter: returns global word at 0x11813488 | confirmed | 1180b060 MVK 0x3488,A4; MVKH 0x11810000,A4; LDW *A4[0],A4; BNOP B3,5 |
| 1180b06c | cfg_get_global_1181348c | getter: returns global word at 0x1181348c (slot adjacent to 1180b060's) | confirmed | 1180b06c MVK 0x348c,A4; MVKH 0x11810000,A4; LDW *A4[0],A4; BNOP B3,5 |
| c011adc0 | gfx_fill_bit_rect | bulk bit-rectangle fill: computes left/right byte boundary via SHR/SHRU-by-3 rounding, builds a run mask with an SPLOOP OR-shift loop; gfx_set_bit_range (c011c508, see 00) CALLPs it after computing the row base | likely | c011ae4e SPLOOP 2; c011ae50 SHL A3,A1,A2; c011ae56 OR A2,A0,A0 (mask-build loop); opening SHR/ANDN-by-7 boundary rounding matches gfx_set_bit_range's own byte-rounding; sole caller c011c508 |
| c011b0b8 | ui_blit_leaf_b0b8 | large (952B) leaf, no internal calls, sole caller c011dff8 (a screen-compose routine); likely a glyph/bitmap blit given size and UpdateUI/MainApp roots | guess | n=952, 0 calls, 1 caller c011dff8; roots MainApp,UpdateUI |
| c011b470 | ui_render_leaf_b470 | 304B leaf (no further calls) shared by two mid-level screen builders c011cdec and c011e4f4; role not traced | guess | n=304; callers=c011cdec,c011e4f4; roots UpdateUI |
| c011b5a0 | ui_render_leaf_b5a0 | 48B leaf shared by the diag-mask-tested wrappers c011e3ac/c011e444; role not traced | guess | n=48; callers=c011e3ac,c011e444; roots UpdateUI |
| c011b5d0 | gfx_set_pixel | sets one pixel in a paged monochrome framebuffer: byte = buf + (y>>3)*128 + x, bit = y&7, read-modify-write OR | confirmed | c011b5d8 SHR A1,0x2,A0 / SHRU 0x1d / ADD / SHR 0x3 (divide-by-8 idiom on A1=y), then SHL A0,7 (x128); c011b5ec LDBU *B4[B5]; c011b5f0 AND B0,7,B0 (y&7); c011b5f4 SHL 1,B0; c011b5fa OR; c011b600 STB |
| c011b608 | gfx_shape_draw_1 | 512B shape-draw routine calling the pixel-set primitive c011b5d0; sole caller is the dispatcher c011eef0 | likely | calls=c011b5d0; caller=c011eef0 (dispatcher); n=512 |
| c011b808 | gfx_shape_helper_b808 | 64B helper shared by the three large shape-draw siblings b848/bbc4/c22c | likely | callers=c011b848,c011bbc4,c011c22c (all three fanned out from c011eef0) |
| c011b848 | gfx_shape_draw_2 | 704B shape-draw routine, calls c011b808; one of the three siblings called both from orchestrator_c011b848 (c011d84c, see 00) and from c011eef0's dispatcher | likely | calls=c011b808; callers=c011d84c(see00),c011eef0 |
| c011bb08 | gfx_shape_draw_3 | 188B shape-draw routine calling the pixel-set primitive c011b5d0; sole caller c011eef0 | likely | calls=c011b5d0; caller=c011eef0 |
| c011bbc4 | gfx_shape_draw_4 | 244B shape-draw routine calling c011b808; sibling of b848/c22c, called by c011d84c(see00) and c011eef0 | likely | calls=c011b808; callers=c011d84c(see00),c011eef0 |
| c011bcb8 | gfx_line_plot_point | 72B leaf, sole caller c011bd00 (the line-draw routine); likely the inner per-step point/segment plotter | likely | callers(1)=c011bd00; n=72, no further CALLP (bit-set presumably inlined) |
| c011bd00 | gfx_draw_line | line-draw routine: computes dx/dy bounds via chained CMPLT, calls the signed-divide helper rts_sdiv32 for the slope and c011bcb8 per step; sole caller c011eef0 | likely | c011bd84 CALLP 0xc01675c0,B3 (slope divide); c011bd90 CALLP 0xc011bcb8,B3; opening min/max bound compares typical of a bounding-box line draw |
| c011bfc8 | gfx_shape_draw_5 | 612B shape-draw routine calling c011b5d0 (pixel-set) and rts_sdiv32; sole caller c011eef0 | likely | calls=c011b5d0,c01675c0=rts_sdiv32; caller=c011eef0 |
| c011c22c | gfx_shape_draw_6 | 732B shape-draw routine calling c011b808 and rts_sdiv32; sibling of b848/bbc4, called by c011d84c(see00) and c011eef0 | likely | calls=c011b808,c01675c0=rts_sdiv32; callers=c011d84c(see00),c011eef0 |
| c011c508 | see 00 | gfx_set_bit_range | - | - |
| c011c588 | ui_draw_proportional_bar | 380B routine calling gfx_set_bit_range, c0142ec4 and rts_sdiv32 together -- shape matches a proportional bar/meter draw (width = value/divide, then bit-range fill); sole caller c0154290 | likely | calls=c011c508=gfx_set_bit_range,c0142ec4,c01675c0=rts_sdiv32; caller=c0154290 |
| c011c704 | unk_c704 | 132B routine, sole caller big_mvc_subsystem (c011f8d8, see 00); not traced | guess | n=132; caller=c011f8d8(see00) |
| c011c788 | unk_c788 | 520B routine, sole caller big_mvc_subsystem (c011f8d8, see 00); not traced | guess | n=520; caller=c011f8d8(see00) |
| c011c990 | unk_c990 | 468B routine, sole caller orchestrator_c011c990 (c011cb64, see 00); not traced | guess | n=468; caller=c011cb64(see00) |
| c011cb64 | see 00 | orchestrator_c011c990 | - | - |
| c011cc14 | unk_cc14 | 472B standalone routine, both callers (c01431f2, c014c6d0) outside this chunk; not traced | guess | n=472; callers outside chunk |
| c011cdec | ui_render_item_a | 552B routine calling the leaf c011b470; called by c011d014 and c011e700 | likely | calls=c011b470; callers=c011d014,c011e700 |
| c011d014 | ui_render_item_a_wrap | thin (96B) wrapper forwarding to c011cdec; called by c011d124, c011e3ac, c011e4b4, and c012e330(outside) | likely | calls=c011cdec; 4 callers |
| c011d074 | unk_d074 | 176B routine, sole caller c011d124; not traced | guess | n=176; caller=c011d124 |
| c011d124 | ui_screen_render_1 | 432B orchestrator entered via the save/restore pair, calling orchestrator_c011c990 (c011cb64, see 00), c011d014 and c011d074 -- a screen-render driver; sole caller c014dc08(outside) | likely | calls=c011cb64=see00,c011d014,c011d074,c016e000,c016e020 |
| c011d2d4 | unk_d2d4 | 188B routine shared by c011d390 and c011dff8; not traced | guess | n=188; callers=c011d390,c011dff8 |
| c011d390 | ui_draw_box_a | 328B routine calling gfx_set_bit_range and c011d2d4 -- an icon/box-fill drawer; sole caller unk_d4d8 (c011d4d8, see 00) | likely | calls=c011c508=gfx_set_bit_range,c011d2d4; caller=c011d4d8(see00) |
| c011d4d8 | see 00 | unk_d4d8 | - | - |
| c011d590 | unk_d590 | 188B routine shared by c011d64c and c011dff8 -- structurally identical sibling of c011d2d4 | guess | n=188; callers=c011d64c,c011dff8 |
| c011d64c | ui_draw_box_b | 328B routine calling gfx_set_bit_range and c011d590 -- sibling of c011d390; sole caller c011d794 | likely | calls=c011c508=gfx_set_bit_range,c011d590; caller=c011d794 |
| c011d794 | ui_draw_box_b_wrap | thin (184B) wrapper forwarding to c011d64c; callers c013a4ec, c013a710 (outside chunk) | likely | calls=c011d64c; 2 callers |
| c011d84c | see 00 | orchestrator_c011b848 | - | - |
| c011d8f0 | unk_d8f0 | 72B routine forwarding to orchestrator_c011b848 (c011d84c, see 00); sole caller big_subsystem_2 (c011d938, see 00) | guess | calls=c011d84c(see00); caller=c011d938(see00) |
| c011d938 | see 00 | big_subsystem_2 | - | - |
| c011dca8 | unk_dca8 | 604B routine calling big_subsystem_2 (c011d938, see00), rts_sdiv32 and c0168640; no caller found inside this chunk (reached by table/pointer or an external CALLP) | guess | calls=c011d938=see00,c01675c0=rts_sdiv32,c0168640; 0 in-chunk callers listed |
| c011df04 | ui_draw_box_c | 244B routine calling gfx_set_bit_range only; no caller found inside this chunk | guess | calls=c011c508=gfx_set_bit_range; 0 in-chunk callers listed |
| c011dff8 | ui_screen_compose_1 | 656B routine combining the blit leaf c011b0b8 with the two box-fill pairs c011d2d4/c011d590 -- composes a screen from box + blit elements; callers c01341e4,c0140740,c01408cc,c01695c0 (outside chunk) | likely | calls=c011b0b8,c011d2d4,c011d590; 4 callers (none in this chunk) |
| c011e288 | unk_e288 | 200B routine, sole caller c011e350; not traced | guess | n=200; caller=c011e350 |
| c011e350 | unk_e350_wrap | 92B wrapper forwarding to c011e288; sole caller c013a810(outside) | guess | calls=c011e288 |
| c011e3ac | ui_render_item_a_logged | 152B routine calling c011b5a0, c011d014 (-> c011cdec) and diag_mask_test, inside a save/restore frame -- a logged/instrumented variant of the item-render path; sole caller c012e010(outside) | likely | calls=c011b5a0,c011d014,c0169fc0=diag_mask_test,c016e000,c016e020 |
| c011e444 | ui_render_leaf_logged | 112B routine calling c011b5a0 and diag_mask_test -- sibling pattern to c011e3ac; sole caller c011e4b4 | likely | calls=c011b5a0,c0169fc0=diag_mask_test,c016e000,c016e020 |
| c011e4b4 | ui_render_item_a_wrap2 | 64B wrapper combining c011d014 (-> c011cdec) and c011e444; callers c012dca4,c012e164,c012e4b8,c01374c8 (outside chunk) | likely | calls=c011d014,c011e444,c016e000,c016e020 |
| c011e4f4 | ui_render_item_b | 524B routine calling the leaf c011b470 (sibling of c011cdec); sole caller c011e700 | likely | calls=c011b470; caller=c011e700 |
| c011e700 | ui_screen_render_2 | 408B routine combining c011cdec (item-render-a) and c011e4f4 (item-render-b); callers c013a710,c01407b0,c0140a30,c0154338,c0157876,c015e588 (outside chunk) | likely | calls=c011cdec,c011e4f4; 6 callers |
| c011e898 | ui_draw_box_d | 152B routine calling gfx_set_bit_range only; sole caller c011e930; recon:10 | guess | calls=c011c508=gfx_set_bit_range; recon=10 |
| c011e930 | unk_e930_wrap | 60B wrapper forwarding to c011e898; sole caller c013a810(outside) | guess | calls=c011e898 |
| c011e96c | ui_draw_box_e | 136B routine calling gfx_set_bit_range only -- sibling of c011e898; sole caller c011e9f4 | guess | calls=c011c508=gfx_set_bit_range |
| c011e9f4 | unk_e9f4_wrap | 60B wrapper forwarding to c011e96c; sole caller c013a810(outside) | guess | calls=c011e96c |
| c011ea30 | ui_draw_box_f | 216B routine calling gfx_set_bit_range only -- sibling of e898/e96c; sole caller c011ec84 | guess | calls=c011c508=gfx_set_bit_range |
| c011eb08 | ui_draw_box_shared | 76B routine calling gfx_set_bit_range only, shared by three outer wrappers (eb54/ebc8/ec48) -- a common small icon-fill primitive; roots UpdateUI | likely | calls=c011c508=gfx_set_bit_range; callers=c011eb54,c011ebc8,c011ec48 |
| c011eb54 | ui_draw_box_shared_wrap1 | 116B wrapper forwarding to c011eb08; sole caller c0137a98(outside) | guess | calls=c011eb08 |
| c011ebc8 | ui_draw_box_shared_wrap2 | 128B wrapper forwarding to c011eb08; callers c0137a98,c0137eac,c015942c (outside) | guess | calls=c011eb08 |
| c011ec48 | ui_draw_box_shared_wrap3 | 60B wrapper forwarding to c011eb08; callers c0137748,c0137a98,c014c70c,c01594f0 (outside) | guess | calls=c011eb08 |
| c011ec84 | unk_ec84_wrap | 148B wrapper forwarding to c011ea30; callers c013a810,c0164880(outside) | guess | calls=c011ea30 |
| c011ed18 | unk_ed18 | 472B routine calling rts_sdiv32 only; no caller found inside this chunk | guess | calls=c01675c0=rts_sdiv32; 0 in-chunk callers |
| c011eef0 | gfx_shape_dispatch | 356B dispatcher fanning out to the whole shape/line-draw family (b608,b848,bb08,bbc4,bd00,bfc8,c22c); sole caller big_mvc_subsystem (c011f8d8, see 00) | likely | calls=c011b608,c011b848,c011bb08,c011bbc4,c011bd00,c011bfc8,c011c22c,c016e000,c016e020; caller=c011f8d8(see00) |
| c011f054 | unk_f054 | tiny (24B) leaf, six callers all outside this chunk; not traced | guess | n=24; 6 callers outside chunk |
| c011f06c | unk_f06c | large (1208B) leaf with no internal CALLPs detected, 2 callers outside chunk (1180aea0,c012e474); not traced given size | guess | n=1208; 0 calls; 2 callers outside chunk |
| c011f524 | ui_screen_render_logged | 500B routine calling orchestrator_c011c990 (c011cb64, see00), rts_memset and diag_mask_test; callers c01545c4,c015460c(outside) | likely | calls=c011cb64=see00,c0167b00=rts_memset,c0169fc0=diag_mask_test,c016e000,c016e020 |
| c011f718 | ui_logged_leaf_1 | 220B routine calling diag_mask_test only (plus save/restore); callers c0135cd0,c01361ac,c0145ec8(outside); roots MainApp | likely | calls=c0169fc0=diag_mask_test,c016e000,c016e020 |
| c011f7f4 | ui_logged_leaf_2 | 136B routine calling diag_mask_test only (plus save/restore) -- sibling of c011f718; callers c011f87c(see00),c0135cd0,c0137748,c014dc08 | likely | calls=c0169fc0=diag_mask_test,c016e000,c016e020 |
| c011f87c | see 00 | wrapper_c011f7f4 | - | - |
| c011f8d8 | see 00 | big_mvc_subsystem | - | - |
| c011fa20 | usb_cppi_queue_pop_index | pops a completion-queue head-descriptor-pointer register (base ~0x01e00000, indexed by queue arg A4) and converts it into a 32-byte-stride index relative to the CPPI descriptor table at 0xc87b9000 (masks low 4 bits, range-checks against the base, returns -1 if below it) | likely | c011fa22/26 SHL/ADD building 0x01e00000+index<<4; c011fa34/38 MVK/MVKH 0xc87b9000,A2; c011fa40 CLR A0,0,4,A1 (mask descriptor flags); c011fa44 CMPLTU A1,A2,A0 -> return -1; else c011fa4e SHRU A0,0x5,A0 (/32 index) |
| c011fa54 | usb_cppi_desc_test_field28 | reads the CPPI descriptor at 0xc87b9000+32*index and tests whether bits 27:31 of word 0 equal 16, returning a boolean | likely | c011fa58 MVKH 0xc87b0000,B0 (+0x9000 low via earlier MVK); c011fa60 SHL A4,0x5,A0 (x32); c011fa64 LDW *A4[0],A0; c011fa66 SHRU A0,0x1b,A0; c011fa6a CMPEQ A0,16,A0 |
| c011fa70 | usb_cppi_queue_push | submits a CPPI descriptor pointer+flags to queue manager register 0x01e0600c + 16*queue -- confirmed queue-submission primitive, recon/17 B4 finding1 | confirmed | c011fa90 ADDK 24588,A4 (0x600c); c011fa96 STW B0,*A4[0]; matches recon/17 quote verbatim |
| c011faa0 | usb_cppi_completion_drain | services one CPPI completion queue: pops an entry via c011fa20, tests its field via c011fa54, processes up to 32 entries per activation; called twice from the top-half ISR (recon/17: "queues 24,25") | likely | calls=c011fa20,c011fa54; c011faa6 CMPGT 0,A4,A0 (empty check) -> skip; c011faae MVK 32,A6 (bounded loop count); caller c011fb94 (the top-half ISR) |
| c011fb94 | usb_isr_top_half | USB interrupt top half: the actual installed callback entry is the label c011fc8c inside this function's body (registered for event 19 by c0122260/c014a524 per recon/17 B4 finding1); reads status 0x01e00038, services completion queues 24-27 (twice via c011faa0, twice via an internal call at c011fcc4/c8), masks/acks via 0x01e00034/003c and posts the Swi handle at B14[181] | confirmed | c011fc9a LDW *A4[0],B0 (0x01e00038, matches recon quote exactly); c011fcb8/c0 CALLP c011faa0; c011fd24/36 STW *A4[0] (mask clear / EOI); recon/17 B4 finding1 quotes these exact addresses |
| c011fd40 | usb_ep_iostate_reset_1 | zeroes fields +6/+7/+8 and writes sentinel -1 to field +9 of a 168-byte-stride per-endpoint I/O-state record at base 0xc0112c08+0x8c, indexed by arg A4; reused by both c011fe70 (clear-all) and c01212e0 (per-endpoint configure) | likely | c011fd44 MPY32 A0(168),A4,A1; c011fd48/50 MVK/MVKH 0xc0112c08; c011fd62/64/68 STW 0 to +6/+7/+8; c011fd80 STW -1 to +9 |
| c011fd98 | usb_ep_iostate_reset_2 | zeroes fields +6..+11 of a sibling 168-byte-stride record at base 0xc011297c, indexed by A4 -- same family as c011fd40 but a different table and no -1 sentinel | likely | c011fda0 MPYLI A0(168),A4,A7:A6; c011fda4/a8 MVK/MVKH 0xc011297c; c011fdb2..c2 STW 0 to +6,+7,+8,+9,+10,+11 |
| c011fdc8 | usb_ep_iostate_reset_3 | zeroes fields +6/+7/+8 and writes sentinel -1 to field +9 of a third 168-byte-stride record at base 0xc0112c08+0x14 -- sibling of c011fd40 with a different field bit | likely | c011fdcc MPY32 168,A4,A1; c011fdd0/d8 MVK/MVKH 0xc0112c08; offset 0x14; c011fe02 STW -1 to +9 |
| c011fe20 | usb_ep_iostate_reset_4 | zeroes fields +6..+11 of a fourth 168-byte-stride record at base 0xc011341c -- sibling of c011fd98 with no -1 sentinel; used by c01203b8 and c0121224/c01212e0 | likely | c011fe24 MPYLI 168,A4,A7:A6; c011fe28/2c MVK/MVKH 0xc011341c; STW 0 to +6,+7,+8,+9,+10,+11 |
| c011fe4c | usb_ep_iostate_reset_5 | zeroes fields +1..+4 of a different, smaller-stride record at base 0xc0114150 (index via SHL A4,4 + A4, not the x168 scheme of its siblings) -- used by c01203b8 and c0121224/c01212e0 | likely | c011fe4e SHL A4,0x4,A0; c011fe50 ADDAW A0,A4,A0; c011fe54/58 MVK/MVKH 0xc0114150; STW 0 to +1,+2,+3,+4 |
| c011fe70 | usb_ep_tables_clear_all | clears the per-endpoint TX/RX FIFO reservation tables for all 4 endpoints before (re)configuration, calling the five iostate-reset helpers above plus its own 680-byte-stride loop bound to 4 -- confirmed verbatim by recon/17 B2 finding2 | confirmed | calls=c011fd40,c011fd98,c011fdc8,c011fe20,c011fe4c; recon/17: "c011feb8 STW A1,*B6[8]" / "c011feda STW B0,*B5[1]" with 680-byte increments and bound 4, both addresses fall inside this function's 184-byte body |
| c011ff28 | usb_ep_shutdown | clears bit 6 at 0x01e00401 and writes words at 0x01e01800/01808 with 32-byte strides -- the USB shutdown/error path, confirmed by recon/15's direct quote; calls c011fe70 (table clear) and c014a2a0 | confirmed | recon/15: "UsbTask's shutdown/error path c013826c calls c011ff28, which clears bit 6 at 01e00401 and writes words at 01e01800/01808"; mmio 01e00000,01e01000,01ff1000 |
| c011ffc0 | usb_syscfg_toggle_1 | 68B routine touching the SYSCFG MMIO region at 0x01c14000, called from the USB controller init c0122260; recon/19 cross-reference | guess | mmio 01c14000; caller=c0122260(confirmed init); recon=19 |
| c0120004 | usb_cppi_region_init | 188B routine touching the 0x01e24000/0x01e27000 MMIO region (near the CPPI RAM/queue-manager block used elsewhere in this driver); called from c0122260 (confirmed init), c01200c0 and c0155720(outside) | guess | mmio 01e24000,01e27000; caller=c0122260(confirmed init) |
| c01200c0 | usb_controller_subinit | 48B routine combining c011ff28 (shutdown/clear), c011ffc0 (syscfg) and c0120004 (CPPI region init) plus c014a36c; B14 global 131 (shared with c0122260) | guess | calls=c011ff28,c011ffc0,c0120004,c014a36c; B14=131 |
| c01200f0 | unk_00f0 | tiny (4B) stub, sole caller c015e924(outside); not traced | guess | n=4; 1 caller outside chunk |
| c01200f4 | usb_pending_table_op | 236B routine touching a rodata table at 0xc0172c30 and an MMIO region near 0x01e02800, with a loop (B1 index) that ORs a shifted bit into a word -- looks like a per-item pending/notify bitmap update; used by nearly every endpoint-service routine below (9 callers) | guess | c0120124/28 LDW *A5[1]/[0] (table scan); c012014c SHL A2,A0,A0; OR A0,A1,A1 (bit-set into accumulator); callers=c0120550,c0120650,c01207c8,c0120904,c0120a94,c0120b2c,c0120ca4,c0122824,c01229e8 |
| c01201e0 | unk_01e0 | 112B routine, callers c0120650 and c0120dd0; not traced in detail | guess | n=112; callers=c0120650,c0120dd0 |
| c0120250 | usb_cppi_desc_build_submit | obtains a free descriptor from CPPI queue 28, builds a 32-byte host descriptor at c87b9000+32*index (length/buffer/original-buffer fields) and enqueues it via c011fa70 -- confirmed verbatim by recon/17 B4 finding1 | confirmed | recon/17: "c0120280 SHL B7,5,B0; c01202b8 STW B0,*B4[0]; c01202e2/ea STW A6,*B4[4]/[7]; c0120318 CALLP c011fa70"; calls=c011fa20,c011fa70 |
| c012032c | usb_ep_resubmit_a | thin (140B) wrapper forwarding to c0120250 (descriptor build+submit); callers c01203b8, c01216a8 | likely | calls=c0120250 |
| c01203b8 | usb_ep_reset_resubmit | resets two endpoint I/O-state records (c011fe20, c011fe4c) then rebuilds/submits a CPPI descriptor via c012032c; callers c0120550, c0122418 | likely | calls=c011fe20,c011fe4c,c012032c,c016e000,c016e020 |
| c012042c | usb_ep_resubmit_b | thin (136B) wrapper forwarding to c0120250 -- sibling of c012032c on the TX side; sole caller c01204b4 | likely | calls=c0120250; recon/17: "CPPI TX chain: c01204b4 -> c012042c -> c0120250" |
| c01204b4 | usb_tx_cppi_submit | performs a cache writeback (c016e380) before calling c012042c to build/submit a TX CPPI descriptor -- confirmed by recon/17 B4 finding2's exact TX-chain quote; callers c0120550, c0120f64 | confirmed | recon/17: "c012050c invokes cache operation c016e380 before queuing"; calls=c012042c,c016e380=wrapper_c016e380,c016e000,c016e020 |
| c0120550 | usb_ep_complete_resubmit | per-endpoint completion/resubmit step: calls the free-queue check c011fa70, the pending-table op c01200f4, the reset-resubmit path c01203b8 and the TX-submit path c01204b4; callers c0120650, c0120904, c01216a8, c01219f4 | likely | calls=c011fa70,c01200f4,c01203b8,c01204b4,c016e000,c016e020 |
| c0120628 | usb_dma_ctrl_set_bit3 | sets bit 3 of a per-channel 16-bit register at 0x1e00000+ch*16+0x502 (read-modify-write, written twice); callers c0120650, c0121960 | likely | c0120630 MVK 0x0502,A0; c0120640 SET A0,3,3,A0; c0120648/4a STH *A4[0] (twice) |
| c0120650 | usb_tx_ep_service_step | per-TX-endpoint service step on the c011297c TX-state table: masks ch=A4&0xF, indexes a stride-9 descriptor-template table at c01805d0, then pops/tests a CPPI entry (c011fa20,c011fa54), runs the pending-table op (c01200f4), completion-resubmit (c0120550) and the bit3 setter (c0120628); callers c0120800, c0121224, tbl_step_c011297c (see chunk_03) | likely | c0120654..74 builds c01805d0+9*ch; calls=c011fa20,c011fa54,c01200f4,c0120550,c0120628 |
| c01207c8 | usb_tx_ep_reset_notify | resets TX I/O-state record 1 (c011fd40) then runs the pending-table op (c01200f4); sibling of c0120a94 on the RX side; callers c0120800, c0121960 | likely | calls=c011fd40,c01200f4 |
| c0120800 | usb_tx_ep_service | per-endpoint TX service entry on the c011297c table: masks ch=A4&0xF, checks table field+2 (else error 0xffff8ad0), clears field+5, and if field+9>0 sets field+9=-2 and calls c0120650 then (for ch>0) c01207c8 | likely | c0120824 LDW *+B4[2]; c0120838 LDW *B4[9]; CMPGT 0,B0; calls=c0120650,c01207c8 |
| c0120860 | usb_dma_ctrl_set_bit4 | sets bit 4 of a per-channel 16-bit register at 0x1e00000+ch*16+0x506 -- sibling of c0120628 at a different per-channel offset; callers c0120904, c0121804 | likely | c0120868 MVK 0x0506,A0; c0120874 SET A0,4,4,A0; c0120880/82 STH *A4[0] (twice) |
| c0120888 | usb_dma_chan_cfg_build_a | builds a 32-bit channel-config word from a template table at c0180598/c018059c (selected by flag B4) combined with channel index A4, storing it into a config array near c0180000+0x17e8 (ADDK 6120); exact bit layout not resolved; callers c0120904, c0120dd0 | guess | c01208a4/ac table at c0180598/59c; c01208f8 ADDK.S2 6120,B4; sibling of c01201e0 (see row 123) |
| c0120904 | usb_rx_ep_service_step | per-RX-endpoint service step on the c011341c RX-state table -- sibling of c0120650 but for RX: masks ch, builds a config word via c0180000+0x5a0 template, then pops/tests a CPPI entry, pending-table op, completion-resubmit and the bit4 setter (c0120860); callers c0120acc, c0121224, tbl_step_c011341c (see chunk_03) | likely | c012090c MVK 0x05a0,A3 (table base, sibling of c0120650's 0x5d0); calls=c011fa20,c011fa54,c01200f4,c0120550,c0120860,c0120888; mmio 01e00000,01e04000 |
| c0120a94 | usb_rx_ep_reset_notify | loads TX/RX-table field+7 as a pointer and writes -1 (sentinel) through it, resets RX I/O-state record 3 (c011fdc8), clears field+3, then runs the pending-table op (c01200f4) -- sibling of c01207c8 for the c011341c table; callers c0120acc, c0121804 | confirmed | c0120ab0 LDW *B5[7],B4; c0120ab2/b6 MVK -1,B0; STW B0,*B4[0]; calls=c011fdc8,c01200f4 |
| c0120acc | usb_rx_ep_service | per-endpoint RX service entry on the c011341c table -- exact mirror of c0120800 for RX: masks ch, checks field+2 (else error), clears field+5, and if field+9>0 sets field+9=-2 and calls c0120904 then (for ch>0) c0120a94 | confirmed | same shape as c0120800 one-for-one; calls=c0120904,c0120a94 |
| c0120b2c | usb_tx_desc_prepare | TX descriptor-prepare step: copies length/pointer fields from the per-endpoint ctrl struct (c0112c08-based, stride168) into the c011297c TX record, and if the size field is positive bulk-copies that many bytes via an SPLOOPW byte loop into the record's buffer before (per facts) calling the pending-table op and c0120250 build/submit; recon/17 names it as a TX/RX CPPI wrapper layer | likely | c0120b58..7a field copies; c0120bac SPLOOPW 13 (byte-copy loop); calls=c01200f4,c0120250 (facts) |
| c0120ca4 | usb_rx_desc_prepare | sibling of c0120b2c for the RX side (c011341c table) -- same calls (pending-table op c01200f4, build/submit c0120250) and recon/17 tag; sole caller c0121804 | likely | calls=c01200f4,c0120250; recon=17 |
| c0120dd0 | usb_controller_resume_seq | USB resume/reconnect sequence: writes 0x1ff01e1f to the interrupt-enable register 0x1e00030, calls c014a278(7) (outside), then for ch=0..3 calls c0120888 and c01201e0 with flag=1, and finally sets bit6 of the POWER byte at 0x1e00401; sole caller c0138720(outside) | likely | c0120de4 STW 0x1ff01e1f,*0x1e00030; c0120e18/20 SET bit6,*0x1e00401; calls=c0120888,c01201e0,c014a278 |
| c0120e28 | usb_ep_csr_write | low-level per-endpoint CSR/command writer selected via the INDEX register scheme (args: A4=CSR value, B4=endpoint address); called 8x in a row by c0120ef8's broadcast path; mmio 01e00000 | likely | called with (A4=value,B4=ep) pairs from c0120ef8; mmio 01e00000 |
| c0120ef8 | usb_ep_csr_apply | applies a CSR value to one endpoint, or broadcasts it to endpoints {0,1,129,2,130,3,131,4,132} when the endpoint arg is -1 (sentinel); recon/18,20 quote the exact call `CALLP c0120ef8 \|\| MVK 128,A4 \|\| MVK 1,B4` as EP0 IN's stall path; callers c0135ab8(outside) and 3 others | confirmed | recon/18: "stall path c0135ab8 CALLP c0120ef8 \|\| MVK 0x80,A4 \|\| MVK 1,B4"; recon/20 matches verbatim; calls=c0120e28 |
| c0120f64 | usb_tx_buffer_enqueue | stores a TX buffer pointer+length into the c011297c TX record's field+6/+7 (after checking field+2 is set, else error 0xffff8ad0), and if field+5 ("ready") is set calls c01204b4 to submit; sole caller c012116c | likely | c0120f84 LDW *B4[2]; c0120f94/96 STW B1/A1,*B4[6]/[7]; c0120f98 LDW *B4[5]; calls=c01204b4 |
| c0120fb0 | usb_tx_ep_io_entry | large (444B) per-endpoint TX entry point: special-cases ep==128 (EP0, far branch) and ep 129..131 (far branch), else walks the ctrl-state struct and a 140/168-byte-stride pair of tables, returning error codes 0xffff8a59/0xffff8a65 on failure; calls c011fd98 (iostate reset 2); callers c012116c, c015b2b4(outside) | likely | c0120fc0/d0 ep==128 and ep-129<3 special cases; c012100c/10 error consts; calls=c011fd98 |
| c012116c | usb_ep_io_dispatch | combines the TX buffer-enqueue (c0120f64) and the big TX entry dispatcher (c0120fb0) behind one save/restore pair; sole caller c01384ac(outside); mmio 01e00000 | likely | calls=c0120f64,c0120fb0 |
| c0121224 | usb_ep_reset_full | resets an endpoint's full I/O state across both TX and RX tables: calls all five iostate-reset helpers (c011fd40,fd98,fdc8,fe20,fe4c) then re-triggers both service-step dispatchers (c0120650,c0120904); callers c01212e0 (confirmed FIFO configurator), c0122ad0(outside wrapper); mmio 01e00000 | likely | calls=c011fd40,c011fd98,c011fdc8,c011fe20,c011fe4c,c0120650,c0120904 |
| c01212e0 | usb_ep_fifo_configure | the dynamic per-endpoint FIFO configuration routine (A4=endpoint,B4=attributes,A6=max packet) -- confirmed verbatim by recon/17,18,20 B2 finding1: selects INDEX at 0x1e0040e, rounds max-packet up to a power of two, enables double buffering, sets TXMAXP/RXMAXP/TXFIFOSZ via the indexed region; calls c0121224 to reset state first; sole caller c01358b4(outside) | confirmed | recon/18 B2 finding1 quotes c0121338 STB A1,*+B7[0] (INDEX select) and the TXMAXP/RXMAXP offsets verbatim; calls=c011fd40,c011fd98,c011fdc8,c011fe20,c011fe4c,c0121224; mmio 01e00000; recon=17,18,20 |
| c0121508 | usb_faddr_flag_set | conditionally sets bit 7 of the FADDR byte at 0x1e00400 based on bit 6 of the caller's argument (clears the low 7 bits of FADDR first); roots MIDI, sole caller c0134e24 | likely | c0121518 EXTU B0,25,25,B0 (arg bit); c0121520/22 SHRU/SHL A0,7 (isolate FADDR bit7); c0121528 STB *A4[0] |
| c0121530 | usb_irq_enable_dispatch | two-way dispatcher: if A4!=0 calls c014a0b4 else calls c014a230 (both outside this chunk); called twice by c012154c with A4=1 then A4=0 | likely | c0121534 [A0] BNOP c0121544 (A4!=0 path); calls=c014a0b4,c014a230 |
| c012154c | usb_irq_enable_sequence | USB top-level interrupt-enable sequence: save regs, call c0121530(1), clear the ctrl-struct field at c0112c10, write 0x1ff01e1f to the interrupt-enable register 0x1e00030, call c0121530(0), then if the low nibble of 0x1e04094 is nonzero set bit24 of a word 12 bytes before that register; mmio 01e00000,01e04000,01ff1000; recon=17 | likely | c0121562 STW 0,*0x...2c10(B4); c0121576 STW 0x1ff01e1f,*0x1e00030; c012158c AND 15,A0 (0x1e04094 low nibble) |
| c01215a8 | usb_stub_ret0_a | returns 0; sole caller c015e924(outside) | confirmed | c01215a8 MVK 0,A4; BNOP B3,5 |
| c01215ac | usb_const_ptr_c01816dc_get | returns the constant pointer 0xc01816dc (role of the pointed-to table not identified); roots MainApp, sole caller c015576c(outside) | guess | c01215ac/b0 MVK 0x16dc,A4; MVKH 0xc0180000,A4; BNOP |
| c01215b8 | usb_cppi_desc_template_init | builds a CPPI descriptor template into caller-supplied output pointers: stores 0xc87b5000 (a pool base distinct from the 0xc87b9000 descriptor table), a size field with bit12 set (0x1000), the descriptor-table base 0xc87b9000, and flags=7; roots MainApp, sole caller c0155628(outside) | likely | c01215c4/c8 STW 0xc87b5000; c01215ce STW 0x1000(bit12 set); c01215d4/d8 STW 0xc87b9000; c01215e0 STW 7 |
| c01215e4 | usb_cppi_powerseq_init | PSC-style module reset/enable-and-wait sequence on the 0x01e27xxx region: checks 0x1e207804 bit26==3, else SPLOOP-waits on 0x1e207128 bit0 to clear, enables 0x1e207a04 (OR 3), waits again, then re-polls 0x1e207804 bit26==3; called from c0122260 (confirmed init) and c01554c0(outside); mmio 01e21000,01e27000 | likely | c01215f0 EXTU A0,26,26 (bit26); c0121600/60 SPLOOPW (wait loops) on 0x1e207128/0x1e207a04 |
| c01216a4 | usb_stub_ret0_b | returns 0; roots MainApp, sole caller c01554c0(outside) | confirmed | c01216a4 MVK 0,A4; BNOP B3,5 |
| c01216a8 | usb_queue_service_resubmit_a | one dispatch case from c01219f4's event fanout: pops a CPPI entry (c011fa20), forwards it through c012032c (resubmit wrapper), and runs the completion/resubmit step c0120550; sole caller c01219f4 | likely | calls=c011fa20,c012032c,c0120550 |
| c0121804 | usb_queue_service_case_b | another dispatch case from c01219f4: builds/submits a descriptor (c0120250), sets DMA-ctrl bit4 (c0120860), runs the RX reset-notify (c0120a94) and the RX desc-prepare (c0120ca4); sole caller c01219f4 | likely | calls=c0120250,c0120860,c0120a94,c0120ca4 |
| c01218c4 | usb_queue_service_case_c | a third dispatch case from c01219f4; no CALLPs seen in the facts sheet -- a self-contained MMIO leaf not traced in detail; sole caller c01219f4 | guess | n=156; 0 calls listed |
| c0121960 | usb_queue_service_case_d | a fourth dispatch case from c01219f4: builds/submits a descriptor (c0120250), sets DMA-ctrl bit3 (c0120628), runs the TX reset-notify (c01207c8) and the TX desc-prepare (c0120b2c); sole caller c01219f4 | likely | calls=c0120250,c0120628,c01207c8,c0120b2c |
| c01219f4 | usb_event_dispatch_body | the main event-dispatch body called from c0121d80: pops/tests CPPI entries (c011fa20,c011fa54), runs the completion/resubmit step (c0120550) and fans out to the four case handlers above (c01216a8,c0121804,c01218c4,c0121960); sole caller c0121d80 | likely | calls=c011fa20,c011fa54,c0120550,c01216a8,c0121804,c01218c4,c0121960 |
| c0121b4c | usb_ep0_event_decode | decodes the EP0 control register at 0x1e00502 (bit2 session/error branch, bit27 and bit31 status branches), reads the EP0 control-transfer state variable at c0112c14 (compared against 1/2), and for state>=6 dispatches through a 6-entry jump table at c018442c to the case handlers c0121cc4/c94/c74/cb0/c54 (same "settings-table trampoline" shape as 00_library_kernel.md); sole caller c0121d80; mmio 01e00000 | likely | c0121b50/54 LDHU *0x1e00502; c0121b70/78 LDW *0xc0112c14 (state var); c0121c44/4c LDW *+A7[A1] (jump through c018442c) |
| c0121c54 | usb_ep0_fsm_case5 | EP0 control-FSM case: checks a sub-flag (word at A5+12), writes state=7 and command=128 to the CSR, then sets state=0 -- reached via the c018442c jump table (index5, ptr@ c0184440) and possibly by fallthrough from c0121c74 | likely | c0121c64/6e STW 7,*A4; STW 128,*B4; STW 0,*A5; ptr@=c0184440 |
| c0121c74 | usb_ep0_fsm_case2 | EP0 control-FSM case: same shape as c0121c54 but ends in state=6 instead of 0 -- reached via the jump table (index2, ptr@ c0184434) | likely | c0121c84/8e STW 7,*A4; STW128,*B4; STW6,*A5; ptr@=c0184434 |
| c0121c94 | usb_ep0_fsm_case1 | EP0 control-FSM case: writes state=5 and forwards a status word to the CSR without touching the state var -- reached via the jump table at two slots (index1 ptr@ c0184430, index3 ptr@ c0184438), and also CALLP'd directly from c0121b4c | likely | c0121c96/9a STW5,*A4; STW A2,*B4; ptr@=c0184430,c0184438; direct caller=c0121b4c |
| c0121ca2 | usb_ep0_fsm_case6 | EP0 control-FSM case: writes state=5 plus a status word, then writes state=7 to a second CSR -- distinct from case1 by the extra second write; ptr@ c0184444 (outside the 6-entry table checked by c0121b4c, so reached from elsewhere) | guess | c0121ca4/ca8 STW5,A2; c0121caa STW7,*A5; ptr@=c0184444 |
| c0121cb0 | usb_ep0_fsm_case4 | EP0 control-FSM case: writes state=6/command=128 then state=5 -- reached via the jump table (index4, ptr@ c018443c) | likely | c0121cb2/ba STW6,128,5; ptr@=c018443c |
| c0121cc4 | usb_ep0_fsm_case0 | EP0 control-FSM case: writes state=3 and forwards a status word -- reached via the jump table (index0, ptr@ c018442c); mmio 01e00000 | likely | c0121cc6/ca STW3,*A4; STW B1,*B4; ptr@=c018442c |
| c0121d80 | usb_event_decode | the USB/controller event decoder -- confirmed by recon/17 B4 finding1's exact quote of its caller c0138378; fans out to c01219f4 and the EP0 decoder c0121b4c; sole caller c0138370(outside); mmio 01e00000; recon=15,17,20 | confirmed | recon/17: "c0138378 CALLP c0121d80 ; decode USB/controller event"; calls=c01219f4,c0121b4c |
| c01221b8 | usb_stub_ret0_c | returns 0; sole caller c015e9c0(outside) | confirmed | c01221b8 MVK 0,A4; BNOP B3,5 |
| c01221c0 | usb_cppi_freequeue_init | pre-populates CPPI free/completion queue 28 with 4096 sequential raw index values (0..4095) via c011fa70, instead of real descriptor pointers -- explains how c0120250's "pop a free descriptor from queue 28" can use the popped value directly as a table index; roots MainApp, sole caller c0155628(outside) | likely | c01221c4 SET A3,12,12,A3 (bound=0x1000=4096); c01221cc CALLP c011fa70,B3 \|\| MVK 28,A4 (loop) |
| c01221e0 | usb_phy_calibrate_init | writes two magic configuration words to SYSCFG registers 0x1c14038/3c, then runs a calibrate-bit sequence at 0x1c14184 (set bit15, delay loop of 50, clear bit15/bit10/bit9, poll a status bit via SPLOOP) -- a USB PHY/PLL calibration sequence; roots MainApp,SwitchNrmlSpdRead; sole caller c0122260(confirmed init); mmio 01c14000 | likely | c01221f0/0200 STW to 0x1c14038/3c; c0122212 delay loop(50); c0122244 SPLOOPW poll |
| c0122260 | usb_controller_init | the USB0 controller init routine -- confirmed by recon/17 B4 finding1: installs callback c011fc8c with interrupt/event argument 19 into B14[131] via c014a524, and calls c01215e4, c01221e0, c011fe70 (ep-table clear), c011ffc0 (syscfg) and c0120004 (CPPI region init); roots MainApp,SwitchNrmlSpdRead; sole caller c0138a78(outside); B14=131; recon=17,18,20 | confirmed | recon/17: "USB init c0122260 installs c011fc8c as callback with interrupt/event argument 19 (c0122288..2290 callback pointer; c0122296 MVK 19,A0; c01222a8 CALLP c014a524)"; calls=c011fe70,c011ffc0,c0120004,c01215e4,c01221e0,c014a524 |
| c01222d8 | usb_otg_mode_flag_get | reads the OTG/DEVCTL byte at 0x1e00460, extracts a 4-bit mode field, and writes 1 through the output pointer A4 if the field equals 3, else 0; sole caller c015e880(outside); mmio 01e00000 | likely | c01222e0/e8 LDBU *0x1e00460; EXTU A0,27,30,A0; CMPEQ 3,A0 |
| c0122304 | usb_ep_ready_check | per-endpoint ready/status check: computes the 0x1e00000+ep*16+0x502 register (same family as c0120628/c0120860), tests a CSR bit (either the indexed one at fixed 0x1e00502 or the per-endpoint one depending on an endpoint-class test), and returns 0 on success or error 0xffff8a64; sole caller c01354f8(outside); mmio 01e00000 | likely | c0122310 MVK 0x0502,A0 (same offset family); c012232c/48 LDHU+EXTU bit27:31 checks; error=0xffff8a64 |
| c0122358 | usb_ctrlstate_field1_get | copies the ctrl-struct global word at c0112c0c (adjacent to the c0112c08 EP0-state block mapped around c0121b4c/c0122370) into the caller's output pointer *A4, returns 0; sole caller c015e924(outside) | confirmed | c0122358/60 MVK 0x2c0c,A5;MVKH 0xc0110000,A5; LDW *A5[0],A0; STW A0,*A4[0] |
| c0122370 | usb_ep0_read_setup | reads the EP0 FIFO data register at 0x1e00420 (two 32-bit words) and decodes them into the caller's 8-byte SETUP-packet struct (bmRequestType/bRequest/wValue/wIndex/wLength), updates the EP0 control-transfer state variable at c0112c14, and clears RXPKTRDY via the indexed CSR -- confirmed as the SETUP reader used by the common request decoder per recon/18,20: "c01359e4 ... reads SETUP via c0122370"; sole caller c01359e4(outside); mmio 01e00000 | confirmed | recon/18: "Common decoder c01359e4 reads SETUP via c0122370"; c0122378/80 MVK 0x0420,A4 (FIFO0 data reg); c0122388..a2 STB/STH decode into *A5 |
| c0122404 | usb_ep_struct_defaults_init | writes the 16-byte constant sequence {1,2,3,4} into the caller's struct (two STNDW double-word stores) and writes queue number 28 into a second output pointer; sole caller c0155628(outside) | likely | c012240a STNDW 2:1,*A5(0); c0122410 STNDW 4:3,*A5(8); c0122414 STW 28,*B4[0] |
| c0122418 | usb_rx_buffer_enqueue | stores an RX buffer pointer+length into the c011341c RX record's field+6/+7 (after checking field+2 is set, else error 0xffff8ad0), and if field+5 ("ready") is set calls c01203b8 to reset+resubmit -- exact mirror of c0120f64 on the TX side; sole caller c0122468 | likely | same shape as c0120f64; calls=c01203b8 |
| c0122468 | usb_rx_ringbuf_drain | drains up to N bytes (count from the ctrl struct at c0112c1c) byte-by-byte from a computed ring-buffer address into the caller's output pointer, decrementing a pending-count field each iteration, then re-arms the endpoint via c0122418; callers c01380b4, c01384ac, c015b2b4(all outside) | likely | c012249c/a0 LDB/STB loop (byte drain); c01224ac/ae ADD -1,*A5[0] (count decrement); calls=c0122418 |
| c0122570 | usb_rx_ep_io_entry | the RX-side counterpart to c0120fb0: large (416B) per-endpoint entry point on the c011341c table, special-casing ep==0 (far branch) and reading the EP0 control-state var at c0112c14 (compared against 3/7) for a second branch, else checking a 0x1e00508 FIFO-count-style register (>64) and resetting RX I/O-state record 4 (c011fe20); caller c015b168(outside); mmio 01e00000 | likely | c0122584 ep==0 special case; c01225d8 LDW *0xc0112c14 (state var, ==3/7); c0122610/16 LDHU 0x1e00508, CMPGTU 64; calls=c011fe20 |
| c0122710 | usb_speed_selector_get | reads the POWER byte at 0x1e00401, tests a status bit, and returns 0, 1 or 2 -- confirmed by recon/17 as the "current-speed reader" supplying the descriptor-template selector to GET_DESCRIPTOR at c0134fe4; roots MainApp,SwitchNrmlSpdRead; 7 callers (c0134fe4,c0135138,c0135250,c01354f8,c0135660,c01357c8,c0152500); mmio 01e00000; recon=17 | confirmed | recon/17: "Current-speed reader c0122710 supplies the selector to GET_DESCRIPTOR at c0134fe4"; c0122718/20 LDBU 0x1e00401, EXTU bit27:31 |
| c0122734 | usb_ep_intr_enable_bit_set | maps an endpoint number (1..4) to a bit mask (2,8,4,16 respectively, else default) and conditionally writes it into the interrupt-enable register at 0x1e00024, after first setting a flag=1 in the c011298c-based 168-stride table; sole caller c0122824 | likely | c012278a..a6 CMPEQ 4/3/2/1,A1 -> B0=16/8/4/2; c01227b0/b8 STW A0,*0x1e00024 |
| c01227c0 | usb_tx_pending_count_update | 2-state transition on the c011297c TX table's field+3 counter: if (count-1) wraps to 0/1 sets count=3, else sets count=2; sole caller c0122824 | likely | c01227d4 LDW *B4[3]; c01227d8/da ADD -1,CMPLTU 1; c01227e4/ec STW 3/2,*B4[3] |
| c01227f0 | usb_rx_pending_count_update | same 2-state transition as c01227c0 but on the c011341c RX table's field+3 -- exact mirror; sole caller c0122824 | likely | identical shape to c01227c0, base=0xc011341c |
| c0122824 | usb_ep_event_service | per-endpoint event-service step combining the pending-table op (c01200f4), the interrupt-enable bit setter (c0122734) and both pending-count updaters (c01227c0, c01227f0); callers c01380b4, c01384ac, c015b2b4(all outside) | likely | calls=c01200f4,c0122734,c01227c0,c01227f0 |
| c0122900 | usb_stub_ret0_d | returns 0; sole caller c015e880(outside) -- same caller as c01222d8, possibly a null/no-op counterpart in a function-pointer table | confirmed | c0122900 MVK 0,A4; BNOP B3,5 |
| c0122904 | usb_ep_state_field_clear | zeroes field+0x10 of the 680-byte-stride per-endpoint record based near 0xc011298c, indexed by endpoint arg A4 -- same 680-byte stride confirmed for c011fe70 by recon/17 (B2 finding2's "680-byte increments and bound 4" quote); roots MainApp,Swi:USB,SwitchNrmlSpdRead | likely | c0122904/06 MVK168,SET bit9 ->680; c012290c MVK 0x298c,B0; c012291a STW 0,*B4[0]; recon/17 680-byte-stride precedent |

## Data

Three separate per-endpoint software-state table families emerged in the
second half of this chunk, all in the low-SRAM 0xc0110000-ish region used
throughout this driver:

- **TX-state table**, 168-byte stride, base `0xc011297c`: field+2 "enabled",
  field+5 "ready", field+6/+7 buffer pointer/length, field+9 retry/depth
  counter, field+3 a 2-state pending counter. Consumers: c0120650 (drain
  step), c01207c8 (reset+notify, via c011fd40), c0120800 (service entry),
  c0120f64 (buffer enqueue -> c01204b4 TX submit), c0120b2c (desc prepare),
  c01227c0 (pending-count update).
- **RX-state table**, 168-byte stride, base `0xc011341c`: same field layout
  as the TX table. Consumers: c0120904 (drain step), c0120a94 (reset+notify,
  via c011fdc8), c0120acc (service entry), c0122418 (buffer enqueue ->
  c01203b8 RX resubmit), c0120ca4 (desc prepare), c01227f0 (pending-count
  update).
- **EP0 control-transfer ctrl struct**, base `0xc0112c08` (168-byte stride
  per the reset helpers c011fd40/fdc8, which touch `+0x8c`/`+0x14` sub-
  offsets of it): field at `+4` (0xc0112c0c, read by c0122358), `+8`
  (0xc0112c10, cleared by c012154c), `+0xC` (0xc0112c14, the EP0 FSM state
  variable read/written by c0121b4c, c0121c54..cc4 and c0122370/c0122570 --
  observed values 0,1,2,3,5,6,7).
- A fourth, 680-byte-stride array near `0xc011298c`/`0xc0112988` region is
  touched by c0122904 (field+0x10) and by the already-confirmed
  `c011fe70` (recon/17: 680-byte increments, bound 4) -- likely a bigger
  per-endpoint struct that nests or sits beside the two 168-byte tables.
- Register-offset family `0x1e00000 + ch*16 + {0x502,0x506,0x508,...}`:
  per-channel DMA/CPPI control bits, each offset apparently a different
  flag/field (bit3 at +0x502 via c0120628, bit4 at +0x506 via c0120860,
  a 16-bit threshold-compared-to-64 at +0x508 read by c0122570). The fixed
  (non-indexed) register at `0x1e00502` is read by c0121b4c as a *global*
  EP0/session status word (bits 2, 27, 31 tested), distinct from its
  per-channel use elsewhere.
- CPPI "free queue" 28 is pre-populated by c01221c0 with 4096 raw sequential
  index values (0..4095) via c011fa70 -- this is why c0120250's "pop a free
  descriptor from queue 28" can treat the popped value directly as a table
  index into 0xc87b9000+32*index, unlike the real HW completion queues
  24-27 whose entries need c011fa20's pointer-to-index translation.
- Template/config tables in the 0xc0180000 data-table region: `0x5d0`
  (9-field, read by c0120650), `0x598/59c` (read by c0120888), `0x5a0`
  (read by c0120904), `0x5c8/5cc` (read by c01201e0, row 123) -- all feed
  a "build a 32-bit channel-config word" pattern whose exact bit layout
  was not resolved.
- EP0 FSM case-handler jump table at `0xc018442c` (6 word-sized entries,
  indices 0..5): c0121cc4, c0121c94 (twice, indices 1 and 3), c0121c74,
  c0121cb0, c0121c54, selected by c0121b4c from the ctrl-state variable at
  0xc0112c14. c0121ca2's own table-pointer slot (`0xc0184444`) sits one
  entry past this 6-entry table, so it is reached from a different site
  not traced here.
- SYSCFG/PHY registers: `0x1c14038/3c` (magic config words, c01221e0),
  `0x1c14184` (calibrate-bit sequence, c01221e0), `0x1e207804/7128/7a04`
  (PSC-style module reset/enable-and-wait, c01215e4).

## Open questions

- Exact bit/field semantics of the three "DMA/CPPI control" register
  offsets `0x502/0x506/0x508` relative to `0x1e00000+ch*16` were not
  confirmed against a register reference -- named by observed effect
  (set bit3 / set bit4 / compare-to-64) rather than by TRM name.
- The 0x180000-region template tables at `0x5d0/598/59c/5a0/5c8/5cc` feed
  a repeated "build a channel-config word, store at base+0x17e0-ish"
  pattern (c0120650/c0120888/c0120904/c01201e0) whose output consumer and
  exact bit layout were not traced.
- The relationship between the 168-byte-stride TX/RX tables
  (c011297c/c011341c) and the 680-byte-stride array near c011298c is
  unresolved -- they may be nested substructures of one bigger per-endpoint
  record, or entirely separate arrays that happen to sit close together.
- c01218c4 (usb_queue_service_case_c) has no CALLPs in the facts sheet and
  was not read directly (self-contained MMIO leaf, 156B) -- its specific
  role among the c01219f4 dispatch cases is a guess from position alone.
- c0121ca2's jump-table slot (0xc0184444) lies just past the 6-entry table
  c0121b4c indexes (0xc018442c..440) -- which code reaches it was not
  identified in this chunk.
- c01215ac returns a bare constant pointer (0xc01816dc); the structure it
  points to was not inspected, so its role is an unverified guess.

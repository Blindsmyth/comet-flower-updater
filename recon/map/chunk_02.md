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

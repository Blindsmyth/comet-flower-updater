/* USB audio silence-stream candidate (OFFLINE). 32 KiB at c01a8000, inside
   the free SDRAM gap c0187024..c01f4000 and clear of the controller's
   c01a0000..c01a3fff (recon/20 3). */
--retain="usb_audio_descriptor_veneer"
--retain="usb_audio_sof_tick"
--retain="ua_usbmidi_open"
--retain="ua_map_thunk"
--retain="ua_note_build"
--retain="*(.ua_state)"
--retain="*(.ua_mode)"
--retain="*(.text:ua_map)"
--retain="*(.text:ua_ack)"
stock_descriptor_builder = 0xc0160ec0;   /* stock USB descriptor builder */
stock_map_continue = 0xc015c678;         /* c015c66c after its gate, selector == 6 */
stock_map_reject = 0xc015c6ac;           /* c015c66c reject path */
MEMORY {
    CTL2: o = 0xc01a8000, l = 0x8000
}
SECTIONS {
    .ua_mode  > 0xc01a8000   /* fixed: controller_start writes it (UA_MODE) */
    .ua_state > CTL2
    .text     > CTL2
    .text:ua_map > CTL2
    .text:ua_ack > CTL2
    .const    > CTL2
    .fardata  > CTL2
    .far      > CTL2
    .neardata > CTL2
    .bss      > CTL2
}

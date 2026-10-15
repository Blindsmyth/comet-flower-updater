/* USB audio silence-stream candidate (OFFLINE). 32 KiB at c01a8000, inside
   the free SDRAM gap c0187024..c01f4000 and clear of the controller's
   c01a0000..c01a3fff (recon/20 3). */
--retain="usb_audio_descriptor_veneer"
--retain="usb_audio_sof_tick"
--retain="ua_usbmidi_open"
--retain="ua_map_thunk"
--retain="*(.ua_state)"
--retain="*(.text:ua_map)"
--retain="*(.text:ua_ack)"
MEMORY {
    CTL2: o = 0xc01a8000, l = 0x8000
}
SECTIONS {
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

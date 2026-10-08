/* Scratch build only (round 4 Helper B prototype, recon/20_usb_audio_proto.md).
   Placed in the SDRAM window ROUND4.md reserves for this helper:
   c01a8000..c01affff (32 KiB). Not wired into any firmware image; no
   stock AIS section references this region. */
--retain="usb_audio_descriptor_veneer"
--retain="usb_audio_setup_ep1"
--retain="usb_audio_sof_tick"
--retain="usb_audio_build_descriptors"
--retain="usb_audio_copy_descriptors"
--retain="desc_ptrs"
--retain="usb_audio_state"
--retain="usb_audio_resp_buf"
MEMORY {
    CTL2: o = 0xc01a8000, l = 0x8000
}
SECTIONS {
    .ua_state > CTL2
    .text     > CTL2
    .const    > CTL2
    .fardata  > CTL2
    .far      > CTL2
    .neardata > CTL2
    .bss      > CTL2
}

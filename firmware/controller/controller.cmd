/* One contiguous image in SDRAM that no stock code or data references:
   c0187024 (end of the last AIS section) .. c01f4000 (slot 0 heap).
   recon/17 "Placement in SDRAM". 16 KiB reserved at c01a0000. */
--retain="*(.text:dispatch)"
--retain="*(.text:worker_wait)"
--retain="*(.ctl_state)"
MEMORY {
    CTL: o = 0xc01a0000, l = 0x4000
}
SECTIONS {
    .ctl_state > CTL
    .text      > CTL
    .text:dispatch > CTL
    .text:worker_wait > CTL
    .const     > CTL
    .fardata   > CTL
    .far       > CTL
    .neardata  > CTL
    .bss       > CTL
}

/* Linker script for the OFFLINE teardown-diagnostic candidate only. Same
   region as controller.cmd; adds the diagnostic thunk section. The
   lifecycle candidate keeps using controller.cmd unchanged (its source
   hashes are recorded by tools/verify_controller_candidate.py). */
--retain="*(.text:dispatch)"
--retain="*(.text:worker_wait)"
--retain="*(.text:diag_teardown)"
--retain="*(.ctl_state)"
MEMORY {
    CTL: o = 0xc01a0000, l = 0x4000
}
SECTIONS {
    .ctl_state > CTL
    .text      > CTL
    .text:dispatch > CTL
    .text:worker_wait > CTL
    .text:diag_teardown > CTL
    .const     > CTL
    .fardata   > CTL
    .far       > CTL
    .neardata  > CTL
    .bss       > CTL
}

; CF Probe SysEx hook, assembly part (TEST builds only: make_usb_audio_fw.py --probe).
;
; The MIDI task's end-of-SysEx path c0129320.. holds a compact pair at c0129324:
;   CALLP.S2 c0128e54,B3   (16-bit; the dispatcher, its only caller)
;   BNOP.S1  c012932c,5    (16-bit; skips the STB at c0129328)
; make_usb_audio_fw.py makes that word one 32-bit CALLP.S2 to cfp_sysex_thunk
; and clears its layout bit in the packet header c012933c (ea40a000 -> ea00a000).
; Our CALLP returns to c0129328, so the thunk never returns through B3: it runs
; cfp_sysex() (C, EABI: keeps A10-A15, B10-B15, B14 = the firmware's DP), then
; the stock dispatcher c0128e54, which takes no register arguments (it reads
; B14[38]), then continues where the stock BNOP went, c012932c. Register state
; there is the same as after the stock call: the dispatcher already clobbered
; every caller-saved register.
    .sect ".text:cfp"
    .global cfp_sysex_thunk
    .ref cfp_sysex
cfp_sysex_thunk:
        CALLP   .S2     cfp_sysex,B3
        MVKL    .S2     0xc0128e54,B5
        MVKH    .S2     0xc0128e54,B5
        B       .S2     B5
        ADDKPC  .S2     cfp_after,B3,4
cfp_after:
        MVKL    .S2     0xc012932c,B5
        MVKH    .S2     0xc012932c,B5
        B       .S2     B5
        NOP     5

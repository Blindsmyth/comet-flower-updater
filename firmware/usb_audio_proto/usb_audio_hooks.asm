; Adapts usb_audio_build_descriptors' plain EABI C calling convention
; (no args, fills the file-scope desc_ptrs[] state) to
; the exact register convention of the stock descriptor builder c0160ec0:
; A6 is the caller's out-pointer, written through directly (confirmed in
; recon/20 item 2.1: c0160ec2 "MV A6,A5" then the final c0161040
; "STW A0,*+A5[0]" writes the array base back through that same A6).
;
; If a future patch retargets c0135014's "CALLP c0160ec0,B3" at this
; veneer instead of the stock builder, the caller's A6 receives the
; address of desc_ptrs exactly as it would have received the stock
; array's address. A4/B4 (the stock builder's other inputs, a count-ish
; value and a speed selector) are accepted but unused here: this
; prototype always builds the one full-speed, 4-interface descriptor set
; from recon/17 B5, never an alternate/high-speed variant (recon/18 3.6
; point 2: "do not advertise an unimplemented high-speed variant").
;
; SCRATCH / PROTOTYPE ONLY -- not referenced by firmware/, no stock call
; site is modified by this file.

    .sect ".text"
    .global usb_audio_descriptor_veneer
    .ref usb_audio_build_descriptors
    .ref desc_ptrs

usb_audio_descriptor_veneer:
    STW   .D2T2 B3,*B15--[2]
    CALLP .S2   usb_audio_build_descriptors,B3
    LDW   .D2T2 *++B15[2],B3
    NOP   4
    MVKL  .S1   desc_ptrs,A0
    MVKH  .S1   desc_ptrs,A0
    STW   .D1T1 A0,*A6[0]
    BNOP  .S2   B3,5

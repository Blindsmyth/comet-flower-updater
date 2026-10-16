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
    .ref stock_descriptor_builder   ; = 0xc0160ec0, defined by the linker command file
    .ref ua_mode                    ; ua_glue.c: 0 = USB-audio mode off -> all stock
    .ref ua_note_build              ; ua_glue.c: status counter for the settings page

usb_audio_descriptor_veneer:
    ; USB-audio mode off: the stock builder for every type (A0 is scratch,
    ; see below; A4, B4, A6 and the caller's B3 are untouched).
    MVKL  .S1   ua_mode,A0
    MVKH  .S1   ua_mode,A0
    LDW   .D1T1 *A0[0],A0
    NOP   4
 [!A0] B     .S1   stock_descriptor_builder
    NOP   5
    ; Only A4 = 1 (DEVICE) or 2 (CONFIGURATION) build the fragment-pointer
    ; array in stock (c0160ee2..ee6: A4-1 <= 1). A4 = 3 (STRING) builds a
    ; different 8-byte-record table (c0160eea -> c0161008) read as
    ; {len,..,ptr} by c01352a4; A4 = 6/7 (qualifier / other-speed) take
    ; c0161002 and return an empty array, so a full-speed device STALLs them.
    ; Every other A4 therefore tail-branches to the stock builder with all of
    ; its inputs (A4, B4, A6) and the caller's B3 untouched. A0 is a scratch
    ; register the stock builder overwrites itself (c0160ed6).
    ; (docs/helpers/REVIEW_USB_AUDIO_CANDIDATE.md, string-descriptor finding)
    SUB   .L1   A4,1,A0
    CMPLTU .L1  1,A0,A0
 [A0] B     .S1   stock_descriptor_builder
    NOP   5
    ; A6 is caller-saved under EABI; the C builder may overwrite it.
    ; Preserve the stock out-pointer above the callee's stack frame.
    STW   .D2T2 B3,*B15--[4]
    STW   .D2T1 A6,*+B15[3]
    CALLP .S2   ua_note_build,B3
    CALLP .S2   usb_audio_build_descriptors,B3
    LDW   .D2T1 *+B15[3],A6
    LDW   .D2T2 *++B15[4],B3
    NOP   4
    MVKL  .S1   desc_ptrs,A0
    MVKH  .S1   desc_ptrs,A0
    STW   .D1T1 A0,*A6[0]
    MVK   .S1   0,A4
    BNOP  .S2   B3,5

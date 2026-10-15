; USB audio integration glue, assembly part (OFFLINE candidate only).

; ---------------------------------------------------------------------------
; ua_map_thunk: replaces the fixed ownership writes of stock c015c66c.
; Reached by the CALLP.S2 that make_usb_audio_fw.py writes over the gate
; "[!A0] BNOP c015c6ac,5" at c015c674. At that point the stock packet
; c015c66c..c015c672 has run:  A0 = (selector == 6), A4 = slot, B0 = record.
; Our CALLP overwrote B3, so return to the only caller's continuation:
; c015c760 (16-bit CALLP c015c66c, sole reference) returns to c015c768.
; Clobbers only A0, A4, A5 (+B3 = c015c768), within the stock routine's own
; clobber set {A0, A4, A5, B0, B4}. Mapping (recon/24 5.1):
;   all:    record_vector[slot] (c011aa18) = record
;   slot 0: IF0, IF1, EP3 (c011aa4c), EP 0x84 (c011aa90) = 0   (stock MIDI)
;   slot 1: IF2 = 1;   slot 2: IF3 = 2
    .sect ".text:ua_map"
    .global ua_map_thunk
ua_map_thunk:
        MVKL    .S2     0xc015c768,B3
        MVKH    .S2     0xc015c768,B3
 [!A0]  B       .S1     ua_map_reject
        NOP     5
        MVKL    .S1     0xc011aa18,A5
        MVKH    .S1     0xc011aa18,A5
        STW     .D1T2   B0,*A5[A4]          ; record_vector[slot] = record
        MVKL    .S1     0xc011aac0,A5       ; interface ownership map
        MVKH    .S1     0xc011aac0,A5
        CMPEQ   .L1     0,A4,A0
 [!A0]  B       .S1     ua_map_audio
        NOP     5
        STW     .D1T1   A4,*A5[0]           ; IF0 = 0
        STW     .D1T1   A4,*A5[1]           ; IF1 = 0
        MVKL    .S1     0xc011aa4c,A5
        MVKH    .S1     0xc011aa4c,A5
        STW     .D1T1   A4,*A5[0]           ; endpoint map[3]  (EP3 OUT)
        STW     .D1T1   A4,*A5[17]          ; endpoint map[20] (EP 0x84 IN)
        B       .S1     ua_map_ok
        NOP     5
ua_map_audio:
        CMPEQ   .L1     1,A4,A0
 [A0]   STW     .D1T1   A4,*A5[2]           ; slot 1 -> IF2
        CMPEQ   .L1     2,A4,A0
 [A0]   STW     .D1T1   A4,*A5[3]           ; slot 2 -> IF3
ua_map_ok:
        MVK     .S1     0,A4
        B       .S2     B3
        NOP     5
ua_map_reject:
        MVKL    .S1     0xffff8a5c,A4       ; stock c015c6ac result
        MVKH    .S1     0xffff8a5c,A4
        B       .S2     B3
        NOP     5

; ---------------------------------------------------------------------------
; ua_ep0_ack: zero-length EP0 status ACK, the exact argument set the MIDI
; callback uses at c0151f5a..c0151f74 for its own SET_INTERFACE:
;   c015af48(A4=128, B4=0, A6=0, B6=0, A8=-2, A10=0, B8=0).
; A10 is callee-saved under EABI, so it is preserved around the call.
    .sect ".text:ua_ack"
    .global ua_ep0_ack
ua_ep0_ack:
        STW     .D2T2   B3,*B15--[4]
        STW     .D2T1   A10,*+B15[3]
        MVK     .S1     128,A4
        MVK     .S2     0,B4
        MVK     .L1     0,A6
        MVK     .L2     0,B6
        MVK     .D1     0,A10
        MVK     .S1     -2,A8
        MVK     .D2     0,B8
        MVKL    .S2     0xc015af48,B31
        MVKH    .S2     0xc015af48,B31
        B       .S2     B31
        ADDKPC  .S2     ua_ack_ret,B3,4
ua_ack_ret:
        LDW     .D2T1   *+B15[3],A10
        LDW     .D2T2   *++B15[4],B3
        NOP     4
        B       .S2     B3
        NOP     5

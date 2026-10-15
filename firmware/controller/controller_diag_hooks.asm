; Diagnostic thunk for the stock USB endpoint-abort drain loop.
; Hook site c0120744 is a stock 32-bit CALLP to c011fa54 (type==16 test).
; Entry state (decoded from main.dis, see USB_TEARDOWN_PATCH_SITES doc):
;   A4 = popped descriptor index (also copied to A3 at c0120742)
;   A10 = endpoint slot (callee-saved), B3 = return address c0120748
; The stock call c011fa54 itself overwrites A0, A1, A4, B0 only (decoded), so
; every OTHER caller-saved register is preserved here around the C call,
; because liveness after the return was not fully traced. Frame: 20 words
; (80 bytes, 8-aligned). The stack-depth gate remains OPEN: this adds 80 B plus
; the C callee frame to the abort path of whichever task runs it.
; After logging, tail-branch to c011fa54 with A4 = idx and the original B3.

    .sect ".text:diag_teardown"
    .global controller_diag_teardown_hook
    .ref controller_diag_teardown
controller_diag_teardown_hook:
    ADDK .S2 -80,B15
    STW .D2T1 A2,*+B15[1]
    STW .D2T1 A3,*+B15[2]
    STW .D2T1 A5,*+B15[3]
    STW .D2T1 A6,*+B15[4]
    STW .D2T1 A7,*+B15[5]
    STW .D2T1 A8,*+B15[6]
    STW .D2T1 A9,*+B15[7]
    STW .D2T2 B1,*+B15[8]
    STW .D2T2 B2,*+B15[9]
    STW .D2T2 B3,*+B15[10]
    STW .D2T2 B4,*+B15[11]
    STW .D2T2 B5,*+B15[12]
    STW .D2T2 B6,*+B15[13]
    STW .D2T2 B7,*+B15[14]
    STW .D2T2 B8,*+B15[15]
    STW .D2T2 B9,*+B15[16]
    MV .L2X A10,B4
    CALLP .S2 controller_diag_teardown,B3
    LDW .D2T1 *+B15[1],A2
    LDW .D2T1 *+B15[2],A3
    LDW .D2T1 *+B15[3],A5
    LDW .D2T1 *+B15[4],A6
    LDW .D2T1 *+B15[5],A7
    LDW .D2T1 *+B15[6],A8
    LDW .D2T1 *+B15[7],A9
    LDW .D2T2 *+B15[8],B1
    LDW .D2T2 *+B15[9],B2
    LDW .D2T2 *+B15[10],B3
    LDW .D2T2 *+B15[11],B4
    LDW .D2T2 *+B15[12],B5
    LDW .D2T2 *+B15[13],B6
    LDW .D2T2 *+B15[14],B7
    LDW .D2T2 *+B15[15],B8
    LDW .D2T2 *+B15[16],B9
    NOP 4
    MV .L1 A3,A4
    ADDK .S2 80,B15
    MVKL .S2 0xc011fa54,B31
    MVKH .S2 0xc011fa54,B31
    B .S2 B31
    NOP 5

; ---------------------------------------------------------------------------
; Site 2: stock c0121a18 is a 32-bit CALLP c011fa54 (type==16 test) in the
; queue 32..35 consumer c01219f4. Entry state (decoded from main.dis):
;   A4 = popped descriptor index (also in A2 after the stock MV at c0121a0c)
;   B4 = queue number (callers: MVK 32/33/34/35,B4), B3 = stock return address
; Stock c011fa54 overwrites only A0, A1, A4, B0, so everything else is
; preserved around the C call; A4 is reloaded from the frame for the
; tail-call. Same 80-byte frame as the site-1 thunk; the stack-depth gate
; stays OPEN for whichever context runs this consumer.

    .sect ".text:diag_consumer"
    .global controller_diag_consumer_hook
    .ref controller_diag_consumer
controller_diag_consumer_hook:
    ADDK .S2 -80,B15
    STW .D2T1 A2,*+B15[1]
    STW .D2T1 A3,*+B15[2]
    STW .D2T1 A5,*+B15[3]
    STW .D2T1 A6,*+B15[4]
    STW .D2T1 A7,*+B15[5]
    STW .D2T1 A8,*+B15[6]
    STW .D2T1 A9,*+B15[7]
    STW .D2T2 B1,*+B15[8]
    STW .D2T2 B2,*+B15[9]
    STW .D2T2 B3,*+B15[10]
    STW .D2T2 B4,*+B15[11]
    STW .D2T2 B5,*+B15[12]
    STW .D2T2 B6,*+B15[13]
    STW .D2T2 B7,*+B15[14]
    STW .D2T2 B8,*+B15[15]
    STW .D2T2 B9,*+B15[16]
    STW .D2T1 A4,*+B15[17]
    CALLP .S2 controller_diag_consumer,B3
    LDW .D2T1 *+B15[1],A2
    LDW .D2T1 *+B15[2],A3
    LDW .D2T1 *+B15[3],A5
    LDW .D2T1 *+B15[4],A6
    LDW .D2T1 *+B15[5],A7
    LDW .D2T1 *+B15[6],A8
    LDW .D2T1 *+B15[7],A9
    LDW .D2T2 *+B15[8],B1
    LDW .D2T2 *+B15[9],B2
    LDW .D2T2 *+B15[10],B3
    LDW .D2T2 *+B15[11],B4
    LDW .D2T2 *+B15[12],B5
    LDW .D2T2 *+B15[13],B6
    LDW .D2T2 *+B15[14],B7
    LDW .D2T2 *+B15[15],B8
    LDW .D2T2 *+B15[16],B9
    LDW .D2T1 *+B15[17],A4
    NOP 4
    ADDK .S2 80,B15
    MVKL .S2 0xc011fa54,B31
    MVKH .S2 0xc011fa54,B31
    B .S2 B31
    NOP 5

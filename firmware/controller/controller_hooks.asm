; MainApp dispatch hook (replaces c0134df0 CALLP c0127fe0).
; Stock mode: tail-branch to c0127fe0 with the caller's B3, so it returns
; to c0134df4 exactly as before. Controller mode: hand the caller's event
; record (caller B15+4) to controller_event, then resume the MainApp loop
; at c0134dc4, skipping the stock patch/menu dispatchers (recon/15 section 6).

    .sect ".text:dispatch"
    .global controller_dispatch
    .ref controller_event
    .ref ctl_state
controller_dispatch:
    MVKL .S2 ctl_state,B31
    MVKH .S2 ctl_state,B31
    LDBU .D2T1 *B31,A0
    NOP 4
 [!A0] B .S1 normal_dispatch
    NOP 5
    STW .D2T2 B3,*B15--[2]
    ADD .L1X 12,B15,A4
    CALLP .S2 controller_event,B3
    LDW .D2T2 *++B15[2],B3
    NOP 4
    MVKL .S2 0xc0134dc4,B31
    MVKH .S2 0xc0134dc4,B31
    B .S2 B31
    NOP 5
normal_dispatch:
    MVKL .S2 0xc0127fe0,B31
    MVKH .S2 0xc0127fe0,B31
    B .S2 B31
    NOP 5

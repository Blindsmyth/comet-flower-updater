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

; Only c0149d4c calls this entry. Its parallel delay instructions provide
; B6=worker B15+4 and A6=1, and its architectural return is c0149d56.
; Tail-calling EVENT_WAIT leaves no controller frame on the worker stack.
; Stock mode preserves every incoming argument and the original B3.
    .sect ".text:worker_wait"
    .global controller_worker_wait
    .ref controller_worker_pump
    .ref controller_wait_event
controller_worker_wait:
    MVKL .S2 ctl_state,B31
    MVKH .S2 ctl_state,B31
    LDBU .D2T1 *B31,A0
    NOP 4
 [!A0] B .S1 controller_worker_stock_wait
    NOP 5
    MVKL .S2 controller_wait_event,B31
    MVKH .S2 controller_wait_event,B31
    STW .D2T1 A4,*B31
    MVK .S1 0,A0
    STW .D2T1 A0,*B6
    MVK .S1 10,A8
    MVKL .S2 controller_worker_after_wait,B3
    MVKH .S2 controller_worker_after_wait,B3
controller_worker_stock_wait:
    MVKL .S2 0xc014a0cc,B31
    MVKH .S2 0xc014a0cc,B31
    B .S2 B31
    NOP 5

; EVENT_WAIT and its restore helper restore the incoming worker B15 before
; reaching here. A4 is the stock wait result; the bits slot is B15+4.
; The saved event belongs to this worker, not a newly loaded global handle.
controller_worker_after_wait:
    MV .L1 A4,A6
    MVKL .S2 controller_wait_event,B31
    MVKH .S2 controller_wait_event,B31
    LDW .D2T1 *B31,A4
    ADD .L2 4,B15,B4
    MVKL .S2 0xc0149d56,B3
    MVKH .S2 0xc0149d56,B3
    B .S1 controller_worker_pump
    NOP 5

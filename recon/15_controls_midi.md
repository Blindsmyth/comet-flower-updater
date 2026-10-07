# Firmware map part 3: controls and MIDI

Static analysis only. Addresses refer to the main firmware disassembly unless stated otherwise. Findings are saved individually with confidence and instruction evidence.

## 1. Footswitches and buttons

### Direct GPIO switch map (confirmed)
Sampling c0156f00 assembles bits 0..9 from three direct readers and seven indexed readers. Veneers c016f1d0/c0/b0 resolve respectively to 11809530/11809540/11809524; c016f1a0 resolves to 118094c4. Those routines call 11809484, which reads `*(GPIO_base + 40*(pin>>5) + 32)` and extracts bit `pin&31`. GPIO_base is 01e26000 from initialized word 11813214. Instruction evidence: `118094a2 SHR A4,5,B0`; `118094a4 SHL B0,5,B1`; `118094a6 SHL B0,3,B0`; `118094a8 ADD B1,B0,B0`; `118094b2 LDW *A5[8],A0`; `118094b6 SHRU A0,A1,A0`.

| Bitmap bit | GPIO pin index | Input register / bit | Zero / one event |
|---|---|---|---|
|0|4|01e26020 / 4|5 / 6|
|1|2|01e26020 / 2|7 / 8|
|2|6|01e26020 / 6|9 / 10|
|3|27|01e26020 / 27|11 / 12|
|4|24|01e26020 / 24|13 / 14|
|5|26|01e26020 / 26|15 / 16|
|6|37|01e26048 / 5|17 / 18|
|7|38|01e26048 / 6|19 / 20|
|8|86|01e26070 / 22|21 / 22|
|9|0|01e26020 / 0|23 / 24|

Indexed-reader evidence: 118094c4..9504 selects pins 27,24,26,37,38,86 for indices 0..5 and defaults to 0 for index 6, which c0157018 actually passes. Physical legends and press polarity remain unresolved; GPIO pin indices must not be confused with package pin numbers. There is no ADC/SPI read in this ten-bit switch sampler.


### Event queue and MainApp dispatcher (confirmed)
MainApp c0134e10 calls c015d428 then enters c0134db8. Its loop calls c015350c with A4 pointing to a stack event word and B4=-1; that wrapper calls c01534c4, which receives from the same B14[162] handle used by the switch task. Evidence: `c01534c8 CALLP c0166680; c01534cc ADD 8,B15,B4; c01534d0 LDW *+B14[162],A4; c01534d4 MV A4,A6` (parallel argument forwarding). Receive failure becomes sentinel 42 at c01534e0. Main loop ignores event 42 (`c0134de6 MVK 42,B1; c0134dea CMPEQ B0,B1,B0`), calls c0127fe0 to choose between dispatchers c0134acc and c0134d04, passing the event-word pointer. These are useful interception points before stock UI actions; patch up/down versus menu/effect semantics are not established merely by this queue trace.


## 2. Knobs and expression pedal

### AD read and change callback (confirmed value path; ADC identity unresolved)
Task 11809004 calls read routine 1180abc0. That routine locks through B14[149], drives GPIO 90 low via 11809474 -> 118093c0, calls serial-transfer routine 1180673c with A4=0, B4=stack+8, A6=4, B6=4, A8=1, B8=0, drives GPIO 90 high, and unlocks. It returns `((byte0<<2)|(byte1>>6)) & 255`: `1180ac0c LDBU *+B15[8],B0; 1180ac10 LDBU *+B15[9],B1; 1180ac16 SHL B0,2,B0; 1180ac18 SHRU B1,6,A0; 1180ac20 OR A0,B0,A0; 1180ac24 EXTU A0,24,24,A4`. Task inverts that byte (`11809038 NOT A4,A0; 1180903c EXTU A0,24,24,A1`), so the application value is 0..255. This proves an external serial conversion path, not an internal ADC read or direct codec sample; converter model and serial peripheral are still to be identified.

Change filtering is at 11808f40: compares absolute delta with a halfword threshold at channel state+8; adjusts thresholds from 11813318/1181331a with a 250-tick interval. Task keeps recent samples at 118133f8 and chooses a median-like value at 118090ca..90ee, then calls 11808f40. A successful change calls `*(11813320 + 40*channel + 4)` with A4=channel descriptor, B4=value, A6=channel (`11809100 SHL A1,5,A0; 11809104 ADDAD A0,A1,A0; 1180910c LDW *A4[1],A0; 11809110 B A0; 11809118 MV A12,B4; 1180911a MV A11,A6`). Initial sampling also calls that callback at 11809068. The actual loop initializes channel=0 and exits after increment makes it nonzero (11809124 truncates to byte; 1180912c branches only if zero), so this task scans ONE analog channel, not proven four knob pots. The four knobs may be encoders on a separate path; do not assign them to AD without evidence.


### AD consumer and knob notification are separate (confirmed)
Initialized AD descriptor 11813320 has callback c015f08c at +4 and last-value word 254 at +8. c015f08c compares B4 against descriptor[2], optionally calls descriptor[7] with A4=value, then descriptor[9], stores new value at [2], and calls c012f840(2). Excerpt: `c015f094 LDW *A4[2],A0; c015f0a2 LDW *A4[7],A0; c015f0a8 B A0; c015f0b6 LDW *A4[9],A0; c015f0cc STW A0,*A4[2]`. Initial descriptor[9]=c015ffe8, which calls c015f194(0) then c015ff60(value,1), a downstream analog consumer; initial [7]=0. Callback installation routine c015f118 writes B4 into 11813324+40*A4.

Four distinct accumulated controls live at 11813430+4*i: `1180afec LDW *A4[A5],A0; 1180aff0 ADD B0,A0,B0; 1180aff2 STW B0,*A4[A5]` in 1180afe0(index A4, delta B4). c0169554(index A4, clear B4) reads the accumulator; normal-speed task calls it for indices 0..3 via 1180b6e0. Nonzero values call c0169520 via 1180b6d0, which posts event 25+i through c016ef70 -> 1180b000 -> c0166780. Evidence: `c0169530 ADD A4,0x19,A4`; `1180b004 STW A4,*B15[2]`; `1180b008 LDW *+B14[162],A4`. These are very likely the four rotary knobs (delta accumulators, not AD channels); electrical decoder and parameter application still need tracing. Correction to the early queue shorthand: dispatchers copy a 16-byte event record (c0134ad6/4ad8 and c0134ae6/4ae8), whose first word is the event ID. Producers shown here initialize that first word; do not assume the queue's message size is four bytes.


### Calibrated expression candidate (confirmed arithmetic, likely pedal identity)
The AD descriptor's c015ffe8 calls c015f194(0) to fetch the analog value, then c015ff60(raw,1). c015ff60 rejects raw >255; clamps at calibration bounds B14[74] and B14[75]; between them computes `1 + floor(126*(raw-low)/(high-low))`, yielding 0..127. Evidence: `c015ff94 SHL A0,7,A1; c015ff98 ADD A0,A0,A0; c015ff9a SUB A1,A0,A4; c015ffa0 CALLP c0168580; c015ffa4 SUB B1,B0,B4; c015ffa8 ADD 1,A4,A10`. With B4 enabled, a changed in-range result calls c014aef4(A4=value) at c015ffd0, then saves result in B14[76]. Calibration setup c015fff8 uses c014d0bc/c014d0c8 and 8%/92% bounds (`c0160012 SHL A3,3,A4`, divisor 100 at c0160010; `c0160024 MVK 92,A0; c016002c MPY32 A0,A3,A4`). This is likely the expression pedal and an attractive already-scaled CC source, but physical association is not proven by the arithmetic alone.


## 3. MIDI out

### Editor-reply send API (confirmed)
`c01274cc(A4=byte_buffer, B4=byte_length)` saves both arguments, takes semaphore B14[161] with timeout -1, calls `c0144dc8(A4=0, B4=byte_buffer, A6=byte_length)`, then releases the semaphore. Evidence: `c01274d0 MV B4,A11; c01274d2 MV A4,A10; c01274d4 CALLP c0150b20; c01274d8 LDW *+B14[161],A4; c01274e4 CALLP c0144dc8; c01274e8 MV A11,A6; c01274ea MV A10,B4; c01274ec MVK 0,A4; c01274f0 CALLP c01628e0`. Treat return value as unspecified: the wrapper does not preserve the transport return across semaphore release.

Reply builder c0127500 copies seven bytes from c0181880 (raw `f0 52 00 00 00 00 f7`), fills offset 3 from c0183b48 and offset 5 from its argument masked to seven bits, and calls c01274cc with length 7 at c0127548. This proves the API accepts raw MIDI/SysEx bytes, not already packetized USB event words. B14 base is c0184e00 (`c0169a38 MVK 0x4e00,B14; c0169a3c MVKH 0xc0180000,B14`), so semaphore-handle storage B14[161] is c0185084.


### Transmit scheduling and backpressure (confirmed)
c0144dc8 checks port A4==0, nonzero length, and readiness at c01152b8+12 and +36; it can return ffff63c0 (invalid port) or ffff63be (not ready). c0149de4 copies bytes into a 1025-byte ring at c0117b28 through c0149db0/c0149d74 under B14[89]'s lock, then signals B14[90] bit 1. The ring deliberately leaves one byte unused; c0149d74 detects next-write==read before storing. Evidence: `c0149d84 SET A0,10,10,A0` (1024); `c0149d8e CMPEQ B1,B0,B0`; `c0149da6 STB B2,*A5[8]`; `c0149de0..9e20` bulk append; `c0149e64 CALLP c014a240` with B4=1. c0149de4 returns number accepted on normal success, so arbitrary long sends are not guaranteed whole-message acceptance. c01274cc hides that return.

Worker c0149d40 waits for bit 1 then calls c0149c14; it drains the ring into c0117318, normalizes running status through c0149b60, and calls c01489a0(0,buffer,length,&result). Evidence: `c0149c5a CALLP c0149b60`; `c0149c6c STB A4,*B7++[1]` (optional status); `c0149c78 STB B0,*B7++[1]`; `c0149c8c CALLP c01489a0`. The send API queues/copies caller data; it does not directly perform SPI in the caller's context. A controller implementation still needs a bounded queue/coalescing policy for disconnected/full conditions.


## 4. Start-up

## 5. USB controller

## 6. Plan

### Task-entry anchors (confirmed)
Decoded C-initialization in build/codex3/init_c0181b28.bin associates task-name pointers and entry pointers in repeated 0x48-byte records: MainApp name c0172e9f at c0181b6c, entry c0134e10 at c0181b50; MIDI name c0172ee6 at c0181c8c, entry c0129118 at c0181c70; SwitchNrmlSpdRead name c0172ef2 at c0181cd4, entry 118076c0 at c0181cb8; RepeatEventHandler name c0172f0b at c0181d1c, entry 11809d40 at c0181d00; AD name c0172f62 at c0181e3c, entry 11809004 at c0181e20. Instruction cross-check: `118076c0 CALLP 1180bd10; 118076c8 CALLP 1180b710`; `11809034 CALLP 1180abc0`; MIDI `c012912c LDW *+B14[147],A4; c0129130 CALLP c0144580` waits on an event before consuming input. MIDI task entry is a receive/parser anchor, not yet a transmit API.

### Switch event encoding (confirmed; physical labels unresolved)
The normal-speed task compares a sampled/masked bitmap at 1181330c against its previous value, XORs to obtain changed bits, and loops over ten bits. For bit i it posts event 5+2*i when the sampled bit is zero, or 6+2*i when it is one. Do not yet call these press/release without establishing electrical polarity. Excerpt: `11807718 XOR A0,A1,A1`; `11807734 ADD A10,A10,A2`; `11807738 ADD A2,5,A0`; `11807748 [!A0] BNOP 11807750`; `1180774c ADD A2,6,A0`; `11807754 LDW *+B14[162],A4`; `11807758 ADD 8,B15,B4`; `11807760 MVK -1,A6`. Call 1180b6f0 is a veneer to c0166780 (`1180b6f0 MVK 0x6780,B31; 1180b6f4 MVKH 0xc0160000,B31; 1180b6f8 B B31`). Thus the message pointer B4 addresses a stack word containing the event ID, with handle A4 and timeout A6=-1. Loop bound: `11807768 CMPGT 10,A10,A0`. Sampling call 1180b700 resolves to c0156f00. The task uses a 16-tick pacing calculation at 118077c4..77e4; ticks are not proven milliseconds.

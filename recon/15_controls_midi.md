# Firmware map part 3: controls and MIDI

## Handoff continuation: Task A implementation (Codex GPT-6 Astra)

### Startup toggle latch

### MainApp dispatcher interception

### Rotary and analog interception

### Machine code and trampoline placement

Static analysis only. Addresses refer to the main firmware disassembly unless stated otherwise. Findings are saved individually with confidence and instruction evidence.

> **Review by Claude (2026-10-07).** Codex (gpt-6-astra, LOW effort), 15
> committed findings before its usage cap. Spot-checked: the USB register
> accesses are real (c011ff2c/30 and c0122000/04 build 0x01e00401 and
> 0x01e00512; 36 resolved references into 0x01e0xxxx). **Major correction
> of recon/07 and recon/10:** USB is the C6745's integrated USB0 controller,
> not an external SPI chip; it supports isochronous transfers, so USB audio
> is not ruled out by the hardware (a large firmware project nonetheless).
> Unfinished: section 4 (start-up / update-mode check) is empty; the plan
> section is partial. Promising for the MIDI controller mode: a calibrated
> 7-bit analog change hook and a send path that already packetizes CC, PC
> and SysEx.

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


### Two footswitches use a separate fast path (confirmed GPIO/events; likely physical role)
Do not confuse the ten normal-speed buttons with the two-switch path. `c0157034` samples two bits through c016f340 -> 1180954c. Index 0 reads GPIO3; index 1 reads GPIO5 (`11809550 [A0] BNOP 11809556; 11809554 MVK 5,A4; 11809556 MVK 3,A4; 11809558 CALLP 11809484`). Both use 01e26020, bits 3 and 5. Their state is 118132e4 (raw), 118132e8 (masked), 118132ec (prior). 11807858 calls sampler via 1180b6b0; it is called from 1180ac40 at 1180ac68, separately from SwitchNrmlSpdRead.

Debounce path waits for elapsed >19 ticks (`118078e4 MVK 19,A1; 118078ea CMPGTU A0,A1,A0`). Changed bit i starts event 2*i (`11807968 ADD A10,A10,A0`); sampled high adds 1 at 1180799a, giving low/high pairs 0/1 and 2/3. A two-switch coincidence path can replace the event with 4 when timestamp distance <=100 (`11807a22 MVK 100,A0; 11807a2e MVK 4,A0`). A remapper 118077e8 can substitute the event before the nonblocking queue post at 11807a80 (A6=0). This is strongly consistent with the two footswitches, including a both-held gesture, but left/right labels and electrical pressed polarity remain to be proved from boot/UI behavior.


## 2. Knobs and expression pedal

### AD read and change callback (confirmed value path; ADC identity unresolved)
Task 11809004 calls read routine 1180abc0. That routine locks through B14[149], drives GPIO 90 low via 11809474 -> 118093c0, calls serial-transfer routine 1180673c with A4=0, B4=stack+8, A6=4, B6=4, A8=1, B8=0, drives GPIO 90 high, and unlocks. It returns `((byte0<<2)|(byte1>>6)) & 255`: `1180ac0c LDBU *+B15[8],B0; 1180ac10 LDBU *+B15[9],B1; 1180ac16 SHL B0,2,B0; 1180ac18 SHRU B1,6,A0; 1180ac20 OR A0,B0,A0; 1180ac24 EXTU A0,24,24,A4`. Task inverts that byte (`11809038 NOT A4,A0; 1180903c EXTU A0,24,24,A1`), so the application value is 0..255. This proves an external serial conversion path, not an internal ADC read or direct codec sample; converter model and serial peripheral are still to be identified.

Change filtering is at 11808f40: compares absolute delta with a halfword threshold at channel state+8; adjusts thresholds from 11813318/1181331a with a 250-tick interval. Task keeps recent samples at 118133f8 and chooses a median-like value at 118090ca..90ee, then calls 11808f40. A successful change calls `*(11813320 + 40*channel + 4)` with A4=channel descriptor, B4=value, A6=channel (`11809100 SHL A1,5,A0; 11809104 ADDAD A0,A1,A0; 1180910c LDW *A4[1],A0; 11809110 B A0; 11809118 MV A12,B4; 1180911a MV A11,A6`). Initial sampling also calls that callback at 11809068. The actual loop initializes channel=0 and exits after increment makes it nonzero (11809124 truncates to byte; 1180912c branches only if zero), so this task scans ONE analog channel, not proven four knob pots. The four knobs may be encoders on a separate path; do not assign them to AD without evidence.


### AD consumer and knob notification are separate (confirmed)
Initialized AD descriptor 11813320 has callback c015f08c at +4 and last-value word 254 at +8. c015f08c compares B4 against descriptor[2], optionally calls descriptor[7] with A4=value, then descriptor[9], stores new value at [2], and calls c012f840(2). Excerpt: `c015f094 LDW *A4[2],A0; c015f0a2 LDW *A4[7],A0; c015f0a8 B A0; c015f0b6 LDW *A4[9],A0; c015f0cc STW A0,*A4[2]`. Initial descriptor[9]=c015ffe8, which calls c015f194(0) then c015ff60(value,1), a downstream analog consumer; initial [7]=0. Callback installation routine c015f118 writes B4 into 11813324+40*A4.

Four distinct accumulated controls live at 11813430+4*i: `1180afec LDW *A4[A5],A0; 1180aff0 ADD B0,A0,B0; 1180aff2 STW B0,*A4[A5]` in 1180afe0(index A4, delta B4). c0169554(index A4, clear B4) reads the accumulator; normal-speed task calls it for indices 0..3 via 1180b6e0. Nonzero values call c0169520 via 1180b6d0, which posts event 25+i through c016ef70 -> 1180b000 -> c0166780. Evidence: `c0169530 ADD A4,0x19,A4`; `1180b004 STW A4,*B15[2]`; `1180b008 LDW *+B14[162],A4`. These are very likely the four rotary knobs (delta accumulators, not AD channels); electrical decoder and parameter application still need tracing. Correction to the early queue shorthand: dispatchers copy a 16-byte event record (c0134ad6/4ad8 and c0134ae6/4ae8), whose first word is the event ID. Producers shown here initialize that first word; do not assume the queue's message size is four bytes.


### Calibrated expression candidate (confirmed arithmetic, likely pedal identity)
The AD descriptor's c015ffe8 calls c015f194(0) to fetch the analog value, then c015ff60(raw,1). c015ff60 rejects raw >255; clamps at calibration bounds B14[74] and B14[75]; between them computes `1 + floor(126*(raw-low)/(high-low))`, yielding 0..127. Evidence: `c015ff94 SHL A0,7,A1; c015ff98 ADD A0,A0,A0; c015ff9a SUB A1,A0,A4; c015ffa0 CALLP c0168580; c015ffa4 SUB B1,B0,B4; c015ffa8 ADD 1,A4,A10`. With B4 enabled, a changed in-range result calls c014aef4(A4=value) at c015ffd0, then saves result in B14[76]. Calibration setup c015fff8 uses c014d0bc/c014d0c8 and 8%/92% bounds (`c0160012 SHL A3,3,A4`, divisor 100 at c0160010; `c0160024 MVK 92,A0; c016002c MPY32 A0,A3,A4`). This is likely the expression pedal and an attractive already-scaled CC source, but physical association is not proven by the arithmetic alone.


### Analog change reaches the effect parameter setter (confirmed)
c014aef4(value A4) checks its assignment mode through c014ad4c, locks B14[155], iterates effect slots, checks assignment masks, obtains a parameter descriptor via c012afe0(slot,param), scales the incoming 0..127 value through c014aea0, and calls c0141684(slot A4, parameter B4, value A6, apply B6=1). Evidence: `c014af68 CALLP c012afe0`; `c014af78/c014af86 CALLP c014aea0`; `c014af90 CALLP c0141684; c014af94 MV A4,A6; c014af96 MV A14,A4; c014af98 MV A13,B4; c014af9a MVK 1,B6`.

c0141684 stores value in 11811ca8+84*slot+4*parameter (`c0141698 MVK 0x54,B0; c01416a0 MPYLI B0,A10,B3:B2; c01416c4 STW A1,*A4[0]`). It can invoke a parameter descriptor's callback with the effect instance from c014ff44 and shared service context from c01502cc (`c01416ea LDW *A4[7],A0; c0141704 B A11; c014170c MV A4,B4; c014170e MV B10,A4`). Thus intercepting before c014aef4 prevents this analog assignment from mutating effect parameters, while preserving the existing calibration/filter path.


## 3. MIDI out

### Editor-reply send API (confirmed)
`c01274cc(A4=byte_buffer, B4=byte_length)` saves both arguments, takes semaphore B14[161] with timeout -1, calls `c0144dc8(A4=0, B4=byte_buffer, A6=byte_length)`, then releases the semaphore. Evidence: `c01274d0 MV B4,A11; c01274d2 MV A4,A10; c01274d4 CALLP c0150b20; c01274d8 LDW *+B14[161],A4; c01274e4 CALLP c0144dc8; c01274e8 MV A11,A6; c01274ea MV A10,B4; c01274ec MVK 0,A4; c01274f0 CALLP c01628e0`. Treat return value as unspecified: the wrapper does not preserve the transport return across semaphore release.

Reply builder c0127500 copies seven bytes from c0181880 (raw `f0 52 00 00 00 00 f7`), fills offset 3 from c0183b48 and offset 5 from its argument masked to seven bits, and calls c01274cc with length 7 at c0127548. This proves the API accepts raw MIDI/SysEx bytes, not already packetized USB event words. B14 base is c0184e00 (`c0169a38 MVK 0x4e00,B14; c0169a3c MVKH 0xc0180000,B14`), so semaphore-handle storage B14[161] is c0185084.


### Transmit scheduling and backpressure (confirmed)
c0144dc8 checks port A4==0, nonzero length, and readiness at c01152b8+12 and +36; it can return ffff63c0 (invalid port) or ffff63be (not ready). c0149de4 copies bytes into a 1025-byte ring at c0117b28 through c0149db0/c0149d74 under B14[89]'s lock, then signals B14[90] bit 1. The ring deliberately leaves one byte unused; c0149d74 detects next-write==read before storing. Evidence: `c0149d84 SET A0,10,10,A0` (1024); `c0149d8e CMPEQ B1,B0,B0`; `c0149da6 STB B2,*A5[8]`; `c0149de0..9e20` bulk append; `c0149e64 CALLP c014a240` with B4=1. c0149de4 returns number accepted on normal success, so arbitrary long sends are not guaranteed whole-message acceptance. c01274cc hides that return.

Worker c0149d40 waits for bit 1 then calls c0149c14; it drains the ring into c0117318, normalizes running status through c0149b60, and calls c01489a0(0,buffer,length,&result). Evidence: `c0149c5a CALLP c0149b60`; `c0149c6c STB A4,*B7++[1]` (optional status); `c0149c78 STB B0,*B7++[1]`; `c0149c8c CALLP c01489a0`. The send API queues/copies caller data; it does not directly perform SPI in the caller's context. A controller implementation still needs a bounded queue/coalescing policy for disconnected/full conditions.


### USB-MIDI packetizer and short messages (confirmed)
The worker reaches c01489a0, whose state table c0181138 dispatches to c0148740 (new status), c0148930 (remaining short-message bytes), and c01488b2 (SysEx). Per-cable packet state is c0116308+12*cable. Header byte is stored at +4; MIDI data at +5..7; byte count at +8. `c01485ee STB B0,*A5[5]` appends a MIDI byte; `c01485b2 STB B0,*A4[A5]` writes header. c0148668 loads the four-byte word at c011630c+12*cable and c0148600 appends it to c0115300, indexed by a halfword count at c0116300.

Short-message completion c01486c8 extracts status high nibble for channel messages (`c014870c EXTU A1,20,24,A0`), combines `(cable<<4)|CIN` (`c0148724 SHL A2,4,A1; c0148728 OR A0,A1,A0`) and emits the word. Thus raw `B0 cc value` becomes bytes `0B B0 cc value`; raw `C0 program` becomes `0C C0 program 00` on cable 0. Packet reset c0148648 zeros the four-byte packet and byte counts, establishing padding. Existing normalizer's channel table c017d778 has two data bytes for status Bn (entry c017d7d0=2) and one for Cn (c017d7d8=1). Short CC and PC are already supported by the transmit machinery; a stock user-action caller that emits CC/PC has not yet been established.

SysEx c01488b2 recognizes F7 (`c01488c4 MVK 247,B7; c01488f2 CMPEQ B0,B7,B0`). c0148854 selects CIN 4 for continued three-byte payloads, or CIN 5/6/7 for terminal payload length 1/2/3 (`c0148888 MVK 7,A0; c014888c MVK 6,A0; c0148890 MVK 5,A0; c0148894 MVK 4,A0`). Example seven-byte editor reply is three USB words: `04 F0 52 00`, `04 model 00 result`, `05 F7 00 00`. No new USB-MIDI framing implementation is needed for controller CC output.


## 4. Start-up

## 5. USB controller

### USB hardware premise needs correction (confirmed MMIO, controller identity pending)
USB code directly accesses the 01e00000 register region; the inspected USB paths do not show MAX3420E-style SPI register commands. UsbTask's shutdown/error path c013826c calls c011ff28, which clears bit 6 at 01e00401 and writes words at 01e01800/01e01808 with 32-byte strides. Evidence: `c011ff2c MVK 0x0401,A4; c011ff30 MVKH 0x01e00000,A4; c011ff34 LDBU *A4[0],A1; c011ff4a CLR A1,6,6,A1; c011ff4c STB A1,*A4[0]`. Endpoint code directly accesses 01e00512/522/532/542 and 01e00516/526/536/546; e.g. `c0122000 MVK 0x0512,A4; c0122004 MVKH 0x01e00000,A4; c0122008 LDHU *A4[0],A0; c0122012 CLR A0,5,5,A0; c0122014 STH A0,*A4[0]`.

This contradicts recon/10's inference that USB must be a separate SPI controller. SPI semaphores alone do not locate USB. The exact SoC variant and register-map match require checking; do not rule out USB audio based on the earlier external-chip guess.


### Controller identification and audio consequence (confirmed register-family match)
The observed map matches the SoC's integrated USB0, not an external MAX3420E. TI's TMS320C6745/C6747 datasheet SPRS377F section 6.26 explicitly gives USB0 base 01e00000, full-speed device capability on C6745, and control/bulk/interrupt/isochronous transfers with four TX and four RX endpoints plus EP0. Source: https://www.ti.com/lit/gpn/TMS320C6745 (section 6.26 and table 6-96); https://www.ti.com/product/TMS320C6745 . Firmware evidence remains c011ff2c..ff4c and c0122000..2014 above. The prior statement that C6745 has no USB controller is false. Identifying C6745 versus C6747 from these shared registers alone is not possible, but no external USB chip is required to explain this code.

**Likely feasibility, not implemented:** USB audio is not excluded by the controller's transfer types. Full-speed bandwidth, FIFO allocation, clock synchronization, buffering, audio format and CPU/DMA budget still need design and validation. Current MIDI descriptors/packetizer do not establish an existing USB-audio implementation.


## 6. Plan

### Task-entry anchors (confirmed)
Decoded C-initialization in build/codex3/init_c0181b28.bin associates task-name pointers and entry pointers in repeated 0x48-byte records: MainApp name c0172e9f at c0181b6c, entry c0134e10 at c0181b50; MIDI name c0172ee6 at c0181c8c, entry c0129118 at c0181c70; SwitchNrmlSpdRead name c0172ef2 at c0181cd4, entry 118076c0 at c0181cb8; RepeatEventHandler name c0172f0b at c0181d1c, entry 11809d40 at c0181d00; AD name c0172f62 at c0181e3c, entry 11809004 at c0181e20. Instruction cross-check: `118076c0 CALLP 1180bd10; 118076c8 CALLP 1180b710`; `11809034 CALLP 1180abc0`; MIDI `c012912c LDW *+B14[147],A4; c0129130 CALLP c0144580` waits on an event before consuming input. MIDI task entry is a receive/parser anchor, not yet a transmit API.

### Switch event encoding (confirmed; physical labels unresolved)
The normal-speed task compares a sampled/masked bitmap at 1181330c against its previous value, XORs to obtain changed bits, and loops over ten bits. For bit i it posts event 5+2*i when the sampled bit is zero, or 6+2*i when it is one. Do not yet call these press/release without establishing electrical polarity. Excerpt: `11807718 XOR A0,A1,A1`; `11807734 ADD A10,A10,A2`; `11807738 ADD A2,5,A0`; `11807748 [!A0] BNOP 11807750`; `1180774c ADD A2,6,A0`; `11807754 LDW *+B14[162],A4`; `11807758 ADD 8,B15,B4`; `11807760 MVK -1,A6`. Call 1180b6f0 is a veneer to c0166780 (`1180b6f0 MVK 0x6780,B31; 1180b6f4 MVKH 0xc0160000,B31; 1180b6f8 B B31`). Thus the message pointer B4 addresses a stack word containing the event ID, with handle A4 and timeout A6=-1. Loop bound: `11807768 CMPGT 10,A10,A0`. Sampling call 1180b700 resolves to c0156f00. The task uses a 16-tick pacing calculation at 118077c4..77e4; ticks are not proven milliseconds.

### Completion log (Codex GPT-6, 2026-10-07)

Startup and controller-mode findings follow; proposed patches are static designs, not installed changes.

### Startup decision in the boot program (confirmed)
The update/normal decision is **res5 boot code c020a4d0**, not MainApp. After GPIO/platform init c020ce20, c020a4d8 calls c022ba0c(0), then c020a4e8 calls c022ba0c(1). Any nonzero result branches to normal loading c020a568 -> c022ba40. Boot reader c022ba0c selects GPIO3 for index 0 and GPIO5 for index 1; c022b928 reads input register at base+32 and extracts the requested bit. Evidence: `c022ba10 [!A0] BNOP c022ba16; c022ba14 MVK 5,A4; c022ba16 MVK 3,A4; c022ba18 CALLP c022b928`; `c022b956 LDW *A5[8],A0; c022b95a SHRU A0,A1,A0`. Boot and main reader index labels need not be assumed identical.

Both footswitch inputs must be **low** to continue to the update checks. The code additionally requires normal buttons GPIO0,27,24,26,37,38,86,2,4,6 to be high (c020a4f0..a55a); any low goes to normal load. With that pattern it calls **c0201404** at c020a560, the update application (UI and USB service initialization at c0201460..1498). Normal c022ba40 reads a signature near flash 0xBFFF0, then parses AIS starting at flash **0x33000**: `c022baac MVK 0x33,A10; c022bab4 SHL A10,12,A10; c022bac8 CALLP c01fda8c`, followed by AIS command comparisons c022bad8..baf6. Thus holding an extra normal button along with both footswitches can prevent the update branch. Physical left/right names remain unassigned, but electrical low=held is established by this boot gesture.

**Controller startup hook (likely design, untested):** interpose the MainApp call at **c0134e14 -> c015d428** (or insert immediately after that initialization and before c0134e18 -> c0134db8). Sample a chosen normal GPIO using the already configured input reader 11809484 / normal button sampler c0156f00, latch a dedicated controller-mode flag in newly reserved storage, then continue stock initialization. Prefer sampling on entry to c015d428 for an early main-firmware latch; defer all MIDI sending until USB is ready. Require stable samples and consume the entry button until release. This is a main-firmware start test, not the exact power-edge sample; the user must hold through boot. Keep res5 unchanged so the proven both-foot update route takes precedence. Do not use an unallocated B14 offset or presumed empty L2 address for the flag.

### Minimal MIDI controller patch plan (likely design; anchors confirmed)
1. **Latch mode at startup** using the main-firmware hook above. Allocate flag, bounded event queue and transmit worker storage explicitly. Keep normal path bit-for-bit equivalent when flag=0. Initially retain the stock audio pipeline and loaded patch; controller mode here means local controls stop changing it, not that DSP/USB initialization is skipped.
2. **Intercept MainApp events before both stock dispatchers.** Replace the call at **c0134df0 -> c0127fe0** with a mode-aware wrapper. In normal mode return the stock result. In controller mode, consume the event word at caller B15+4, enqueue its CC mapping, and route back to **c0134dc4** before c0134df8/c0134e06 can call c0134acc/c0134d04. This requires a control-flow trampoline, not just returning a chosen boolean (either boolean still selects a stock dispatcher). Evidence: `c0134de4 LDW *B15[1],B0; c0134dea CMPEQ B0,42,B0`; `c0134df8 CALLP c0134acc; c0134e00 ADD 4,B15,A4`; `c0134e06 CALLP c0134d04`. Preserve queue housekeeping c01537f4 and sentinel handling. Alternative: wrap both dispatcher entries and return immediately after controller handling, with a caller audit to avoid double handling. Do not block the fast timer/switch producer on MIDI.
3. **Map events explicitly.** Raw footswitch low/high events are 0/1 and 2/3; low is press from the boot proof. Event 4 is the combined gesture, not a third physical switch. Normal-button pairs are 5+2*i / 6+2*i; the boot check supports active-low for the listed pins. Proposed momentary CC values: press=127, release=0; toggle behavior and CC numbers/channel are user policy, not firmware facts. The existing remapper at 118077e8 and hold/repeat logic can transform events: for exact independent footswitch edges, bypass the coincidence/remap behavior only in controller mode near 11807968..11807a80, or provide a separate raw-edge queue. A single consumer hook is the minimum implementation but preserves stock combined/repeat semantics. Encoder mappings remain unproven; do not label the one AD channel as four knobs.
4. **Intercept calibrated analog change.** Replace **c015ffd0 -> c014aef4** with a wrapper taking A4=0..127. If controller flag is set, coalesce the latest CC value and return; otherwise call c014aef4 with original A4. Keep the caller's last-value update B14[76] so unchanged values remain filtered. Evidence: c015ff94..ffa8 scaling and c014af90 -> c0141684 effect setter above. This blocks expression-driven normal effect edits while keeping calibration. Any other c015f08c descriptor callback remains a separate route requiring audit; the initial descriptor[7]=0 does not prove it stays null.
5. **Use the existing raw-byte send path in task context.** Worker builds `{0xB0 | (channel&15), cc&127, value&127}`; call **c01274cc(A4=&bytes, B4=3)** for the minimal implementation. Evidence: c01274e4 -> c0144dc8 with A4=0/B4=buffer/A6=length and semaphore c0185084. The packetizer supplies USB CIN 0xB. For robust backpressure, duplicate the wrapper's semaphore acquire/release but retain c0144dc8's result before release; verify and handle partial acceptance. Sending one three-byte message can still be partial if the ring has fewer than three free bytes, so reserve capacity atomically or retain the unsent suffix under serialization; do not blindly resend an accepted prefix. Coalesce analog changes, bound switch queue growth, and do not queue stale motion indefinitely while disconnected. The provided wrapper hides transport success, so it cannot alone guarantee lossless delivery.
6. **Suppress actions at their source, not just save operations.** The dispatcher gate stops queued local patch/menu/effect actions; the analog wrapper stops the known direct parameter path. Preserve initialization, audio scheduling and USB worker. Audit rotary/hold-repeat producers and any direct parameter callbacks before claiming every control is covered. Incoming editor MIDI can still change the patch unless its receive handler is also gated; decide that policy separately. No stock patch/effect-save routine needs to run for a CC. These are concrete patch anchors, not assembled bytes: trampoline placement, execute-packet boundaries, relocation range, ABI preservation and all-controller coverage still need implementation checks.

### Four rotary controls recovered from the newly decoded audio section (confirmed decoder; likely front-panel knobs)
The earlier unknown knob path is **11818540**, called each audio Swi at **11818c70**. It reads four GPIO pairs: (65,66), (67,68), (59,58), (57,55), via 11809484. Evidence: `11818568 CALLP 11809484 || ... MVK 65,A4`; 11818574/78 selects 66; 1181858c/94 selects 67; 11818598/a0 selects 68; 118185b0/b8 selects 59; 118185c0/c4 selects 58; 118185d4/e0 selects 57; 118185e4/e8 selects 55. The pairs are inverted and packed into 2-bit quadrature states at **11f03e90+4*i**, with history at **11f03e80+4*i**. Recognized histories **0x387 / 0x34b** call **1180afe0(A4=index, B4=+1/-1)** (`11818630 MVK 0x34b,A4; 11818640 CMPEQ A3,A12,A0; 1181867c EXTU A10,24,24,A4; 11818680 MVK -1,B4; 11818698 MVK 1,B4`). Clockwise labeling is not established.

1180afe0 only accumulates signed motion in **11813430+4*i** (`1180afec LDW *A4[A5],A0; 1180aff0 ADD B0,A0,B0; 1180aff2 STW B0,*A4[A5]`). Event IDs **25..28** map to indices 0..3 through c01534f0; c015350c at **c0153634** calls **c0169554(index,1)** to fetch-and-clear motion and stores it into the normalized event record at +8 (`c0153642 STW A0,*B4[2]`). Zero motion becomes sentinel 42. Thus the MainApp gate can map IDs 25..28 and signed word[2] to four relative CCs, or clamp a per-knob absolute 0..127 accumulator. Do not emit USB/MIDI calls from 11818540/1180afe0: they run in audio Swi context. The consumer hook after c015350c already has the normalized delta and can stop normal rotary actions with the other controls. This closes the earlier four-knob source gap; event direction-to-panel clockwise still needs mapping. The read-clear routine is not an atomic read-modify-write against a preempting Swi, so preserve existing scheduling assumptions or add a short critical section if changing that interaction.

## Handoff continuation (Codex GPT-6 Astra)

### Task A: startup latch, dispatch, rotary/analog hooks and placement

**Confirmed placement blocker:** the proposed file offsets are AIS structure boundaries, not usable trampoline caves. Section c011adc0 starts at file 0xed3c, length 0x549c0, and ends exactly at 0x636fc. Bytes 0x636fc..0x63707 are the next section-load command/address/length; its payload starts at 0x63708 (VMA c016f780), length 0x123a4, ending exactly at 0x75aac. Bytes 0x75aac..0x75ab7 are again AIS metadata, followed by c0183b74's payload. Verified by the AIS walk in build/codex6/ais.ps1 against res1_493412.bin. Overwriting either suggested end offset with instructions corrupts the boot stream. No trampoline has been installed. An implementation needs a genuinely reserved executable region plus a new/extended AIS load record, or a separately verified in-section cave.

Instruction evidence for the hooks remains `c0134df0 CALLP c0127fe0,B3`, `c0134e14 CALLP c015d428,B3`, and `c015ffd0 CALLP c014aef4,B3`. In particular c0134df4 onward must remain intact in normal mode; a controller wrapper must restore its own stack frame before branching to c0134dc4. Memory reservation and transport backpressure remain prerequisites for a deployable implementation.

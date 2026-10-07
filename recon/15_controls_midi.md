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

## 3. MIDI out

## 4. Start-up

## 5. USB controller

## 6. Plan

### Task-entry anchors (confirmed)
Decoded C-initialization in build/codex3/init_c0181b28.bin associates task-name pointers and entry pointers in repeated 0x48-byte records: MainApp name c0172e9f at c0181b6c, entry c0134e10 at c0181b50; MIDI name c0172ee6 at c0181c8c, entry c0129118 at c0181c70; SwitchNrmlSpdRead name c0172ef2 at c0181cd4, entry 118076c0 at c0181cb8; RepeatEventHandler name c0172f0b at c0181d1c, entry 11809d40 at c0181d00; AD name c0172f62 at c0181e3c, entry 11809004 at c0181e20. Instruction cross-check: `118076c0 CALLP 1180bd10; 118076c8 CALLP 1180b710`; `11809034 CALLP 1180abc0`; MIDI `c012912c LDW *+B14[147],A4; c0129130 CALLP c0144580` waits on an event before consuming input. MIDI task entry is a receive/parser anchor, not yet a transmit API.

### Switch event encoding (confirmed; physical labels unresolved)
The normal-speed task compares a sampled/masked bitmap at 1181330c against its previous value, XORs to obtain changed bits, and loops over ten bits. For bit i it posts event 5+2*i when the sampled bit is zero, or 6+2*i when it is one. Do not yet call these press/release without establishing electrical polarity. Excerpt: `11807718 XOR A0,A1,A1`; `11807734 ADD A10,A10,A2`; `11807738 ADD A2,5,A0`; `11807748 [!A0] BNOP 11807750`; `1180774c ADD A2,6,A0`; `11807754 LDW *+B14[162],A4`; `11807758 ADD 8,B15,B4`; `11807760 MVK -1,A6`. Call 1180b6f0 is a veneer to c0166780 (`1180b6f0 MVK 0x6780,B31; 1180b6f4 MVKH 0xc0160000,B31; 1180b6f8 B B31`). Thus the message pointer B4 addresses a stack word containing the event ID, with handle A4 and timeout A6=-1. Loop bound: `11807768 CMPGT 10,A10,A0`. Sampling call 1180b700 resolves to c0156f00. The task uses a 16-tick pacing calculation at 118077c4..77e4; ticks are not proven milliseconds.

# Firmware map part 3: controls and MIDI

Static analysis only. Addresses refer to the main firmware disassembly unless stated otherwise. Findings are saved individually with confidence and instruction evidence.

## 1. Footswitches and buttons

## 2. Knobs and expression pedal

## 3. MIDI out

## 4. Start-up

## 5. USB controller

## 6. Plan

### Task-entry anchors (confirmed)
Decoded C-initialization in build/codex3/init_c0181b28.bin associates task-name pointers and entry pointers in repeated 0x48-byte records: MainApp name c0172e9f at c0181b6c, entry c0134e10 at c0181b50; MIDI name c0172ee6 at c0181c8c, entry c0129118 at c0181c70; SwitchNrmlSpdRead name c0172ef2 at c0181cd4, entry 118076c0 at c0181cb8; RepeatEventHandler name c0172f0b at c0181d1c, entry 11809d40 at c0181d00; AD name c0172f62 at c0181e3c, entry 11809004 at c0181e20. Instruction cross-check: `118076c0 CALLP 1180bd10; 118076c8 CALLP 1180b710`; `11809034 CALLP 1180abc0`; MIDI `c012912c LDW *+B14[147],A4; c0129130 CALLP c0144580` waits on an event before consuming input. MIDI task entry is a receive/parser anchor, not yet a transmit API.

### Switch event encoding (confirmed; physical labels unresolved)
The normal-speed task compares a sampled/masked bitmap at 1181330c against its previous value, XORs to obtain changed bits, and loops over ten bits. For bit i it posts event 5+2*i when the sampled bit is zero, or 6+2*i when it is one. Do not yet call these press/release without establishing electrical polarity. Excerpt: `11807718 XOR A0,A1,A1`; `11807734 ADD A10,A10,A2`; `11807738 ADD A2,5,A0`; `11807748 [!A0] BNOP 11807750`; `1180774c ADD A2,6,A0`; `11807754 LDW *+B14[162],A4`; `11807758 ADD 8,B15,B4`; `11807760 MVK -1,A6`. Call 1180b6f0 is a veneer to c0166780 (`1180b6f0 MVK 0x6780,B31; 1180b6f4 MVKH 0xc0160000,B31; 1180b6f8 B B31`). Thus the message pointer B4 addresses a stack word containing the event ID, with handle A4 and timeout A6=-1. Loop bound: `11807768 CMPGT 10,A10,A0`. Sampling call 1180b700 resolves to c0156f00. The task uses a 16-tick pacing calculation at 118077c4..77e4; ticks are not proven milliseconds.

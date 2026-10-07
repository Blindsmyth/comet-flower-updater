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

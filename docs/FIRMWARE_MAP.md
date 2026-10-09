# G1X Four main firmware map

The overview of the main firmware (res1, AIS image) and where to find each
part. The detail lives in `recon/map/chunk_NN.md` (one row per function) and
in the recon notes cited below. Status: 2026-10-09.

## 1. How to use the map

| need | where |
|---|---|
| what a function does | `grep -n '^| <addr>' recon/map/chunk_*.md` |
| its instructions | `build/fw/map/main.dis` (`grep -n '^<addr>'`, then a `sed -n` window) |
| MVK/MVKH constants (globals, MMIO, tables) | `build/fw/map/refs.txt` (`<insn> <reg> <value>`) |
| callers, callees, strings, reaching tasks | fact sheets `build/fw/map/facts/chunk_NN.md` (`tools/fwmap/facts.py`) |
| coverage and confidence counts | `python tools/fwmap/coverage.py` |
| which task/interrupt reaches a function | `python tools/fwmap/subsystems.py` (`build/fw/map/subsystems.tsv`) |
| function starts the fact sheets fold into neighbours | `python tools/fwmap/hidden_starts.py [chunk_NN]` |
| helper rules and pitfalls | `docs/helpers/FWMAP.md`, `docs/helpers/SAVE_PROTOCOL.md` |

After any map change, run `coverage.py`, then `subsystems.py`, then `facts.py`.
Rebuilding `main.dis` is described in recon/10. Ghidra was tested and does
not decode this image well (docs/GHIDRA_TEST.md); use `dis6x`.

Confidence words in the rows: **confirmed** (the code is unambiguous),
**likely**, **guess**. Helpers wrote most rows. Each chunk was reviewed by a
second pass plus spot checks by Claude, but treat "likely" and "guess" as
leads, not facts.

## 2. Memory layout

| address | contents |
|---|---|
| 0x11800400..0x1180bd40 | fast code in internal L2 (drivers, input sampling, tasks) |
| 0x118164c0..0x1181a1a0 | L2 code: the audio Swi and its DSP helpers (chunk_19) |
| 0x11810000..0x11815fff | L2 data: effect-slot table 118133e0, cfg table 11813490, ... |
| 0x11f00000.. | L2/L1 work buffers: audio RX/TX ping-pong 11f03630 / 11f036b0, planar buffers 11f03730 / 11f03770, float buffers 11f037b0 / 11f037f0 |
| 0xc0100000..0xc011adc0 | SDRAM data/bss: USB state (alt array c011a1b0, EP0 reply buffer c0119fb0, interface map c011aac0), ... |
| 0xc011adc0..0xc016f780 | main code (SDRAM) |
| 0xc016f780..0xc0183b24 | constant data: rhythm table, strings, fonts, bitmaps, tables |
| 0xc0183b74..0xc0187024 | initialised data |
| 0x01c00000.. / 0x01e00000.. | MMIO: EDMA3 (PaRAM 01c04000..), McASP, USB0 MUSB core (01e00400..) |

Entry point 0xc0169a20 (TI SYS/BIOS start-up). The boot/update program (res5,
c020xxxx..c022xxxx) is a separate image and is **not mapped yet**.

## 3. Execution roots

SYS/BIOS tasks (entry addresses from `init_c0181b28`, recon/15):

| task | entry | does |
|---|---|---|
| MainApp | c0134e10 | patch/effect state, event dispatch, settings |
| UpdateUI | c013c754 | LCD screens and menus |
| MIDI | c0129118 | MIDI/SysEx protocol, USB MIDI |
| SwitchNrmlSpdRead | 118076c0 | footswitch and button sampling |
| AD | 11809004 | knobs, expression pedal, battery ADC |
| TunerService | c01674e0 | tuner |
| RhythmService | c016aac0 | drum machine |
| LooperUI | c013b38c | looper |
| QFuncService | c0161ce4 | quick functions |
| RepeatEventHandler | 11809d40 | key repeat |
| PopUpTimeCounter | 11809580 | pop-up timeouts |
| PreLoad | c016c0c0 | effect module preloading |
| DataStore | c016d340 | patch/settings storage |
| BatteryManagement | 11809bd4 | battery |

Interrupt-level roots:

| root | entry | notes |
|---|---|---|
| Swi:audio (prio 15) | 11818ba0 | 16-frame block: RX unpack, 5-slot effect loop, TX pack (chunk_19) |
| Swi:USB (prio 13) | — | USB control and endpoint service |
| Hwi:USB (CPU int 7, event 19) | c011fc8c | SOF ack, empty hook 11818e80 (via c016f770), TX completion queues |
| Hwi:EDMA-RX | — | McASP RX ping-pong, posts the audio Swi (recon/16) |

## 4. Subsystems and where they are

| subsystem | main ranges / entry points | chunks | recon |
|---|---|---|---|
| LCD graphics (paged mono framebuffer, fonts, bitmaps) | 1180b020..c011f8d8; draw bitmap c011c508 | 02 | 10 |
| Switch/knob input | 118072ac..1180b020 | 01 | 15 |
| ELF dynamic loader (5-slot effect modules) | c0122924..c0124fc0, c01453b4..c0146e18, c0163324.. (endian swaps) | 03, 10, 16 | 13, 14 |
| Zoom SysEx replies and MIDI | c0128134..c0128dd4, c012dab0.. | 04, 05, 09, 11 | 15 |
| UI lists, settings screens, menus | c012dab0..c012e5a8, c0137388.., c0157876.. | 05, 07, 14 | — |
| Effect-slot parameters and ramps | c0132430..c0133398, c014ab00..c014aef4, c014f284..c0150340 | 06, 11, 12 | 14, 16 |
| USB device stack | std requests c0134e60..c01359b8, SETUP decoder c01359e4, endpoint set-up c01212e0, record registry c015afa0 / c015c66c, CPPI c0120xxx | 02, 06, 07, 11, 12, 15 | 17, 18, 20..24 |
| Looper | c013abc0..c013b690 | 07, 08 | — |
| Rhythm (drum machine) | c0153f00..c0154290, c0156430..c0156660 | 13, 14 | — |
| Audio DMA (McASP, EDMA3) | c0153cb8, c0153d6c | 13 | 16 |
| Audio processing Swi | 11818ba0 and callees | 19 | 16, 21 |
| Runtime, RTOS and ABI helpers | c0169f20..c016ec40 (save/restore c016e020 / c016e000, trampolines c016fXXX) | 17, 18 | — |

## 5. Status and remaining work

Coverage (coverage.py, 2026-10-09): 2768 of 2790 fact-sheet functions named
(836 confirmed, 1189 likely, 743 guess), plus hidden starts as extra rows.

Still to do:
1. **Hidden-start clean-up**: 114 starts that hidden_starts.py finds still
   have no row (brief `docs/helpers/SOL_HIDDEN.md`, batches A/B/C). Each needs
   a row and a rewritten host row.
2. Summary paragraphs missing in chunk_00 and chunk_09.
3. The boot/update program (res5).
4. Function names are mostly descriptive; a later pass can merge duplicates
   and give the main subsystem APIs stable prefixes.

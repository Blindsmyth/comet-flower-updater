# Comet Flower settings page: menu candidate (2026-10-16)

Folder: `build/cf_menu_2026-10-16/` (owner use only: it contains Zoom's firmware code).

| File | SHA-256 (start) | Contents |
|---|---|---|
| `Comet Flower G1X4 Updater (menu candidate).exe` | `8ae5d67c754acbf1` | Slide candidate + our settings page with MODE |
| `res1_cf_menu.bin` | `3cdcd29c52a3fa6c` | `make_controller_fw.py --ui --usb-product "Comet Flower ZG1X4 MIDI"`, base `res1_cf_usbname.bin` |

Presets and effects as in the release. `check_updater_stages.py` ok. Payload 10,072 B of 16 KiB.
It contains everything in `docs/CF_MODES_SLIDE_CANDIDATE_2026-10-16.md` (slide, port name). **Not flashed.**

## Owner decisions (2026-10-16)

- No stock menu item is given up; our page goes on a second SETTING chooser page, with room for more
  of our pages and settings later.
- On the SETTING screen, a knob turn flips chooser pages (right = page 2, left = page 1); the arrow
  buttons as well once their events are known (see below).
- Page 2 shows only our page(s), not Zoom's dormant pages.
- The pedal always boots in FX mode (the MODE value is not saved).

## How it works (`firmware/controller/controller_menu.c`)

At start-up (`controller_start`, after the C auto-init) it rewrites RAM tables, after checking each
holds its stock boot contents (otherwise it changes nothing and the menu stays stock):

| Table (RAM, from .cinit) | Stock | Now |
|---|---|---|
| ID 0 chooser c01833dc word 8 (event) | c0157bac | our chooser event (knob flip, else stock) |
| ID 1 chooser c0183400 word 8 | c0157bac | same; ID 1 was never selected by stock code |
| List B c0181368 {5,9,3,8,12} | Zoom's dormant pages | {5,1,1,1,1}: slot 1 our page; slots 2..5 empty |
| ID 5 c0183740 words 1..3 (icons) | OUTPUT icons | our "CF" flower icons (`tools/make_menu_icon.py`) |
| ID 5 word 6 (draw) | c016a97a (OUTPUT) | stock page builder c0154564(1 item, "COMET FLOWER") |
| ID 5 word 8 (event) | c016a95a (EQ only) | stock item editor c0149948(1 item) on knob 1 |

MODE record (0x2c bytes): label "MODE", min 0, max 1 (2 = USB once that mode exists), formatter
FX/MIDI, getter/setter = `controller_get_mode`/`controller_set_mode` (enter or leave MIDI mode with
the slide). MIDI mode consumes every control event, so in MIDI mode the menu cannot change it back;
the Rhythm 2 s hold still leaves MIDI mode and returns to the page showing FX.

## Evidence checked by Claude in main.dis (helper reports: MENU_RE_*, MENU_PAGES_ARGON)

- Boot contents of descriptors 0, 1, 5, 10, 13 decoded from .cinit (RLE24) and consistent with
  the code they point to: c0157bac = chooser event, c016a97a = OUTPUT draw (B4=c0182b00, B6 "OUTPUT").
- c0157bac ignores ids outside 6..20 (`c0157bb2 ADD A1,-6; c0157bb4 CMPLTU 0xe`); its table c0184178:
  6 -> c0157b6c, 7 -> c0157b44 (leave), 12/14/16/18/20 -> c0157ae8 (slot; slot index = event word 2,
  `c0157b28 LDW *+A5[A4]` with A4 = word 2). c0157ae8 picks list B iff c01497f4() == 1.
- Icons: c0149ad4 reads descriptor words 1..3 with **no null check** on the descriptor (so empty
  slots point at ID 1, whose icon words are 0); c01579cc skips a null icon (`c0157a10`).
- Item editor c0149948: index = id - 25 < count; getter word 8 required; delta c0153464(word 6, ev);
  clamp c01418ec(sum, word 5, word 6); setter word 9, after-change word 10 when changed; returns 1.
  (Argon's record layout in MENU_PAGES_ARGON P5 is wrong for words 0..6; Astra's is right.)
- Page builder c0154564(A4 count, B4 records, A6 centres, B6 title, A8 label font, B8 value font)
  -> c0154338 (loop over count; formatter word 7 returns a string, else "%d") + c013a7b4 title bar.
- Knob events: word 2 = signed raw delta (c0153144 `LDW *B4[2]`; zero = no movement).
- Events 23/24 are Rhythm (GPIO0, bit 9), not an arrow as MENU_PAGES_ARGON P2 claims; the arrow
  buttons' events are unknown.

## Pedal checklist

1. Boot normally: stock screen. Open SETTING: the usual five icons.
2. Turn any knob right: page 2 shows one icon ("CF" + flower) in slot 1, the other slots empty.
   Turn left: back to the usual five. Pressing an empty slot on page 2 does nothing.
3. Press slot 1 on page 2: the "COMET FLOWER" page with MODE = FX under knob 1.
4. Turn knob 1 right: MODE shows MIDI and the MIDI page slides in. Controls send CCs.
5. Hold Rhythm 2 s: back to the COMET FLOWER page, MODE = FX. SETTING/exit leaves the menu as usual.
6. Stock pages (SETUP, PWR/LCD, ...) still work from page 1.
7. **Arrows:** in MIDI mode, press each arrow button and note the name shown (B1..B10): that tells us
   their events so they can flip pages too.
8. Power-cycle: FX mode.

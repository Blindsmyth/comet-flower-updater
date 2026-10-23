# CF Rig: a Bradshaw-style rig as the pedal's main screen (design, 2026-10-23)

Owner decisions (2026-10-23):
- The rack follows the **standard Bradshaw (Custom Audio Electronics) rig** layout.
- The rig is **not an effect picked into a slot**: a rig engine in our firmware, with its own screens.
- **The 5 stock slots are the switcher's loops** inside the rig.
- When a patch is a rig patch, **the RIG overview replaces the patch screen** (it is the main screen).
Mock-ups (pedal fonts, layout ideas only): `docs/design/rig_mock_2026-10-23.png` (made with `tools/ui_mock.py`).

## The Bradshaw rig, mapped onto the G1X Four
80s CAE rig: floor controller (preset buttons) -> switcher whose loops hold the pedals in front of the amp
(compressor, wah, overdrive, fuzz) -> cranked amp -> load box -> line level -> rack effects in parallel,
100 % wet (delays, chorus, pitch) -> stereo power amp -> **wet / dry / wet**: dry amp in the centre cab,
wet effects in the left and right cabs. Volume pedal and tuner out on the floor unit.

| Bradshaw | CF Rig |
|---|---|
| Switcher loops (front-end pedals) | the 5 stock slots, in order; any Zoom or CF effect (incl. CFM Pre) |
| Loop on/off from the floor | slot on/off (stock state), shown and toggled on the RIG screen |
| Amp + load box | rig AMP block: CF WattL kernel (+ cab for the dry path), in our code after the slots |
| Rack (parallel, 100 % wet) | rig RACK blocks: stereo delay (CF Delay kernel), chorus (CF CE2 kernel), later pitch |
| Stereo power amp + 3 cabs | W/D/W mixer: L = dry + wetL, R = dry + wetR; Dry, Wet L, Wet R, Width |
| Volume pedal | expression pedal (calibrated 0..127 value already traced, recon/15) |
| Preset buttons | patches; footswitch modes (patch up/down vs loop toggles) later |

## Where it runs
- **DSP:** our audio payload already runs inside the audio Swi before the slots (Pre looper hook 11818bc0)
  and after them (Post looper hook 11818c50, after patch level, before drums/master), on the stereo bus
  A 0x11f037b0 / B 0x11f037f0 (separate L/R to the output; docs/FW_RND_ANSWERS_2026-10-22.md Q8; codec
  TLV320AIC3101, stereo DAC). The rig's AMP and RACK + mixer run at the Post hook. Not limited to a slot's
  40 KiB: code and delay memory go in the free SDRAM (c0187024..c01f4000, ~370 KiB checked live; a 1.5 s
  stereo float delay is ~265 KiB, so int16 lines or shorter delays). CPU: the same budget as the slots; the
  CPU meter (Updater 33) shows it all.
- **Screen:** `cf_edit_draw` (the wrapper of the stock patch/edit renderer, c013c050 / c0135b08) draws the RIG
  screens instead of calling the stock renderer when the patch is a rig patch. Selected slot c011abf4,
  page cells c011acf0 (docs/EDIT_SCREEN_TRACE_2026-10-23.md).
- **Controls:** the MainApp dispatcher hook we already own (`controller_dispatch`, c0134df0) sees every event:
  footswitches 0..4, panel buttons 5..24 (press/release pairs), knobs 25..28 with signed deltas
  (recon/15). In a rig patch it routes them to the RIG screens; otherwise stock.
- **Storage:** "this is a rig patch" + rig settings (blocks on/off, amp/rack/mixer knobs) in a custom PTCF
  chunk ("CFRG"), kept by hooking pack c0130e04 and unpack c013150c (docs/helpers/CF_STORAGE_SONNET_2026-10-23.md).

## Screens (main screen of a rig patch)
1. **RIG overview:** patch name + CPU %; the chain `[loop1]>[loop2]>...>[AMP]` with on/off shown inverted;
   below it the split: DRY centre level, WET rack units. Knobs/arrows move the cursor; a button toggles the
   block; another opens its page.
2. **Block page:** header "RIG>FUZZ (MUFF)  ON"; 4 knobs = 4 columns (the G1X has 4 knobs). For a loop
   (stock slot) it shows that slot's stock parameters; for AMP / RACK / MIX our parameters.
3. **W/D/W mixer:** Wet L, Dry, Wet R, Width.

## Build order (each step its own TEST updater; owner flashes)
1. **Rig flag + RIG overview display only** (no DSP, no storage yet: a fixed test flag, e.g. patch name
   starting with "RIG"). Needs: per-slot on/off and effect name lookups (open: find them live with CF Probe,
   as the page/slot cells were).
2. **Post-slot W/D/W mixer + one rack delay** in the audio payload (CF Delay kernel), fixed settings; CPU
   meter check.
3. **Controls on the RIG screens** (dispatcher routing; knob edits of mixer/rack).
4. **AMP block** (CF WattL) and the dry/wet split after it.
5. **Storage** (CFRG chunk, pack/unpack hooks) so rig patches keep their settings.
6. Chorus / pitch rack units, footswitch modes, volume pedal.

## Open questions
- Effect name and on/off state per slot in RAM (live trace next session).
- Which panel button opens a block page vs toggles it (owner preference).
- Rig patch marker before storage exists: patch-name prefix is the cheapest.

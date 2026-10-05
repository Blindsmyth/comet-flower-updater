# zd2tools

Open-source tooling for Zoom `.ZD2` patch files (effect modules), used by the Zoom G1 Four, G1X Four, B1 Four, and A1 Four series multi-effects pedals.

Goal: design and run **new DSP effects** on the G1X Four. A ZD2's `DATA` block is
compiled TI C6000 code, and the community has built custom ZD2 effects for the MS
Plus pedals ([stomphacks](https://github.com/thammer/stomphacks)). This project
works toward bringing that to the G1 Four family.

Status and next steps: **[HANDOFF_2026-10-05.md](HANDOFF_2026-10-05.md)**.

## Features
- **Inspect**: header, target, CRC check, INFO/dspload, blocks, and the embedded
  effect ELF (entry, relocations, parameter table, image list).
- **Audit**: `zd2 audit DIR` gives one line per effect, for comparing pedal families.
- **Spec**: `FORMAT.md`; G1X Four vs MS Plus ABI notes in `recon/02_g1x4_abi_comparison.md`.

## Roadmap
1. [x] Toolchain building stomphacks DIY effects on Windows (`docs/TOOLCHAIN.md`)
2. [x] Code-ABI comparison G1X Four vs MS Plus (matches; container differs)
3. [x] Read-only pedal backup (`tools/backup_g1.py`), audit of all 87 effects (`recon/03`)
4. [x] G1 profile: `zd2 g1-retarget` + `tools/build_g1.sh`; first test effect `effects/g1gain`
5. [x] G1-aware installer: `tools/pedal_g1.py` (writetest / uninstall-stock / install)
6. [x] First hardware test: G1 Gain runs on a G1X Four, 2026-10-04 (`recon/04_hardware_log.md`)
7. [ ] Real effects

## Installation
```bash
pip install .
```

## Usage
```bash
zd2 inspect samples/NYC_MUFF.ZD2
```

## Format Status
Reverse-engineered, partial. See [FORMAT.md](FORMAT.md) for details.

## Disclaimer
This project is unaffiliated with Zoom Corporation. All trademarks belong to their respective owners. The format is reverse-engineered for interoperability.

## Credits
- [mungewell/zoom-zt2](https://github.com/mungewell/zoom-zt2) - ZD2 container grammar and MIDI effect install.
- [thammer/stomphacks](https://github.com/thammer/stomphacks) - effect ABI and the DIY build pipeline.

## License
MIT

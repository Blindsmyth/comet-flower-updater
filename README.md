# zd2tools

Open-source tooling for Zoom `.ZD2` patch files (effect modules), used by the Zoom G1 Four, G1X Four, B1 Four, and A1 Four series multi-effects pedals.

## Features
- **Inspect**: View header, metadata, and tagged blocks of `.ZD2` files.
- **Spec**: Documented format specification in `FORMAT.md`.

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
- [mungewell/zoom-zt2](https://github.com/mungewell/zoom-zt2) - Foundation for understanding the ZDL format.

## License
MIT

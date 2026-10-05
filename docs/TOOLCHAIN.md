# Toolchain setup (Windows)

Building custom effects uses [thammer/stomphacks](https://github.com/thammer/stomphacks)
(MIT). It compiles a C kernel with TI's C6000 compiler and packs it into a
ZD2. It is hardware-proven on the MS Plus series, not yet on the G1 Four (see
`recon/02_g1x4_abi_comparison.md`).

## Layout

The stomphacks build scripts break on paths with spaces, so the toolchain
lives outside this project:

```
C:\Users\z\ti\ti-cgt-c6000_8.5.0.LTS\   TI CGT 8.5.0 (free, signed TI installer)
C:\Users\z\zoomlab\stomphacks\          clone of thammer/stomphacks, with its own .venv
C:\Users\z\zoomlab\stomphacks\zoom-zt2\ clone of mungewell/zoom-zt2 (required at this path)
```

## Install from scratch

```bash
# TI compiler (unattended, no admin)
ti_cgt_c6000_8.5.0.LTS_windows-x64_installer.exe --mode unattended --prefix C:\Users\z\ti

mkdir -p /c/Users/z/zoomlab && cd /c/Users/z/zoomlab
git clone https://github.com/thammer/stomphacks
git clone https://github.com/mungewell/zoom-zt2 stomphacks/zoom-zt2
cd stomphacks && python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt
```

## Build the reference effect

```bash
cd /c/Users/z/zoomlab/stomphacks
export ZOOM_TI_CGT="C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS"
.venv/Scripts/python.exe tools/zd2_make_effect.py effects/gain/manifest.json
# -> effects/gain/build/DIYGAIN.ZD2 + REPORT.md (all checks must pass)
```

This output targets the **MS Plus** (target bit 0x80, colour icon). It is not
yet suitable for the G1X Four. Do not upload it to the G1X Four.

## Inspect / compare

```bash
.venv/Scripts/zd2 inspect file.ZD2   # this project's CLI
.venv/Scripts/zd2 audit some_dir/    # one line per effect, for finding invariants
```

## Local change to stomphacks

`tools/build_zd2_from_asm.sh` link step gets `${ZD2_EXTRA_LNK_FLAGS:-}` after
`--retain="$ENTRY"`. It is empty unless set, so upstream behaviour is unchanged.
`tools/build_g1.sh` sets it to `--export=Dll_<Name>`, because every stock G1
effect exports its entry symbol and stomphacks builds do not.

## Building for the G1X Four

```bash
bash tools/build_g1.sh g1gain GAIN    # effects/g1gain -> build/G1GAIN.ZD2
```

This builds with stomphacks, then runs `zd2 g1-retarget`: target 0x02,
G1 header bytes, a 1-bpp 24x30 icon and the group INFO text.

## Local change 2: state size limit

`tools/zd2_make_effect.py`: `STATE_BYTES_MAX = int(os.environ.get("ZD2_STATE_BYTES_MAX", 192))`.
The default stays at stomphacks' 192 (MS Plus proof). `tools/build_g1.sh` sets 392, the
contiguous state stock G1 drives use without declaring it (NYC Muff 4 + 388; recon/06).

## Shared DSP headers

`effects/common/*.h` (ts808_core.h, ts808_sd.h, ts808_exact.h) are copied into each
effect's build folder by `tools/build_g1.sh`. The host benches include them from there.

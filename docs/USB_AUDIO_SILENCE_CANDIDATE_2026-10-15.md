# USB audio silence-stream candidate — 2026-10-15 (OFFLINE, DO_NOT_FLASH)

This is ROADMAP phase C steps 1–2, built offline. It wires the existing prototype
(`firmware/usb_audio_proto/usb_audio.c`: descriptors, SOF tick, SET_INTERFACE)
into the stock USB stack. The device should then enumerate as USB-MIDI plus a UAC1
stereo 16-bit 44.1 kHz input that streams silence. **No host or pedal has seen
it.** It is not packaged, and `make_fs_restore_updater.py` does not accept it.

```powershell
.venv/Scripts/python.exe tools/make_usb_audio_fw.py --base build/fw/res1_493412.bin
# or layered on a controller candidate:
.venv/Scripts/python.exe tools/make_usb_audio_fw.py --base <controller candidate .bin>
```

Payload: one AIS section load at `c01a8000` (2,436 bytes, 32 KiB reserved). It sits
inside the free SDRAM gap and is clear of the controller's `c01a0000..c01a3fff`.
Glue code: `firmware/usb_audio/ua_glue.c`, `ua_thunks.asm`, `ua.cmd`.

## Patches (each stock word checked before writing, then decoded)

| Site | Stock | New | Purpose (recon/20 §2.6) |
|---|---|---|---|
| 7 × `CALLP c0160ec0` (`c0135014/5168/5258/5568/5694/57e4`, `c0152514`) | stock descriptor builder | `usb_audio_descriptor_veneer` | 192-byte config, 4 interfaces. **Replaces P1–P3.** The stock builder only writes its own array (all of its stores go through A4/A6 → A5; there are no globals), so substituting the builder needs no pointer-array relocation. |
| `c0145158 CALLP c0152410` | usbmidi_open | `ua_usbmidi_open` | P5: after a successful open, `c015afa0(6, IF2 record)`, then `(6, IF3 record)`. IF3 is skipped if IF2 fails. |
| `c015c674 [!A0] BNOP c015c6ac,5` | the gate inside `c015c66c` | `CALLP.S2 ua_map_thunk` | P5 map writer. The call site `c015c760` is a 16-bit CALLP and cannot be retargeted, so the gate is overwritten. The thunk returns to `c015c768`, the only caller's continuation (`c015c66c` has one reference), and clobbers only A0/A4/A5 (plus B3), a subset of the stock set. Slot 0 → IF0, IF1, EP3, EP 0x84 (stock); slot 1 → IF2; slot 2 → IF3. |
| `c016f770/774 MVK/MVKH 0x11818e80` | empty SOF hook | `usb_audio_sof_tick` | P10: Hwi context, one silence packet per SOF while alt 1 is set. |

The IF3 SETUP callback handles only standard SET_INTERFACE (bRequest 11). It runs
`usb_audio_set_alt`, records `alt[3]` at `0xc011a1b0` where stock GET_INTERFACE
(`c0134e68`) reads it, and ACKs with the MIDI callback's exact `c015af48` argument
set (`c0151f5a..f74`). Every other request, and every IF2 request, returns
`0xffff8a5b` and falls through to the stock handlers.

## Verified offline (`tests/test_usb_audio_candidate.py`, `tools/test_usb_audio_proto.py`)

- **Byte changes.** Only the 11 patch words change in stock sections. Retargets keep each stock word's unit, creg and p-bit.
- **Payload.** The handler records hold the glue function addresses, and the thunk uses only A0/A4/A5/B0/B3.
- **Layering.** Building on the controller lifecycle candidate works: the hook sets are disjoint, and the controller hooks are kept.
- **Stock facts pinned.** Single caller and continuation, the gate register state, the SOF veneer, the ACK sequence, GET_INTERFACE's alt array, and exactly 7 builder calls.
- **Descriptor fragments.** All 13 stock MIDI fragments and the device descriptor in the prototype match the stock ROM bytes.
- **Prototype behaviour** (host harness): descriptor length and clipping, the alt state machine, SOF 44/45 pacing, and no spin on a busy FIFO.

## Hardware-only unknowns (recon/20 §4, still open)

1. The direct EP1 FIFO and TXCSR addresses (`0x01e00424` / `0x01e00512`) come from the datasheet only.
2. PIO ISO TXCSR semantics (0x6001), the highest risk. Whether `c015af48`'s A4=128 ACK convention fits IF3 (copied from MIDI) is likely, not proven.
3. Worst-case SOF Hwi timing.
4. Host class binding (Windows `usbaudio.sys`, macOS, Linux). Pending: a strict
   offline UAC1 descriptor validator (`tools/uac1_validate.py`, in progress).
5. `ua_usbmidi_open` covers only the `c0145158` open path. If MIDI is re-opened
   elsewhere without IF2/IF3, the audio interfaces fall back to stock handling;
   stock SET_INTERFACE would then configure EP1 for CPPI DMA. MIDI itself is unaffected.

Gate: ROADMAP B1 (controller-mode pedal test) comes first, then an owner
enumeration test of this image.

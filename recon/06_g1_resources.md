# 06 — G1X Four effect resources: state, memory requests, budget

Date: 2026-10-05. Static scan of all 87 backed-up stock effects (dis6x).
Script: inline in session; method below so it can be re-run.

## Per-instance state actually used (init memsets of zero)
A constant tracker over each `Fx_*_init` records the size argument (A6) of
every firmware-service call whose fill value (B4) is 0, which makes it a memset.
82 of 87 decoded.

| Class | Examples (bytes zeroed at init) |
|---|---|
| Drives | NYC Muff 392 (4 + 388), Gold Drive 408, BG Throttle 396, RC Boost 364, TB MK1.5 488 |
| Reverb / delay | Plate 444, HD Hall 532, Ice Delay 380, Spring 636, TapeEcho3 636 |
| "1U" amps | ORG120 1312, HW100 1208, XtasyBlue 1028, Recti ORG 992, BG MK1 964 |
| Common small | 232 B (9 effects), 68 B (6), 144/160 B (4 each) |

The DIY limit used so far (stomphacks, MS Plus) is 184 B + 4 B guard.
**Plain G1 effects use up to ~490 B without declaring anything** (see below).

## Entry-struct fields (`Dll_<Name>` writes into the caller's struct)
| Fields written | Count | Who |
|---|---|---|
| [0] count, [1] param table, [3] image list | 50 | plain effects (drives, comps, cabs, mods) |
| + [6] | 10 | mod delays, phaser, filters, reverse delay |
| + [8] | 8 | "1U" amps (ORG120 0x3bb8 = 15288, HW100 0x2e4c = 11852) |
| + [5] | 8 | reverbs (Hall 0x8d8 = 2264) |
| + [5] + [6] | 6 | delays (Delay [6] = 260) |
| + [6] + [8] | 2 | FD DLXR, FD TWNR |
| + [7] | 2 | pitch (HPS 100) |
| + [2] | 1 | LPROLL3S (a pointer into .const) |

Reading: [5], [6] and [7] are working-memory requests (reverb, delay line, pitch
buffer). [8] is a large request that only the heavy amps make. Units are not
yet decoded. The stomphacks `dll_fields` manifest key can write these
(experimental). **Plain drives need none of them, so a drive-class DIY effect
can use ~400 B of state like Zoom's own.**

## Declared dspload of stock effects (zd2 inspect, 2026-10-05)
The heaviest stock effects already take most of a patch on their own:
BG MK1 89.41, XtasyBlue 88.18, ORG120 84.08, MS800 79.98, MS1959 78.74,
FD TWNR / FD DLXR 77.51, Ice Delay 73.00, Sweet Drive 70.75. A "solo" DIY
effect at ~85-90 therefore follows Zoom's own precedent. The values are not
on a simple fixed grid, so they do not reveal the cycle unit.

## Open: measured on hardware next
- Patch load budget (sum of declared dspload before "Process Overflow").
- Real CPU cycles per 16-sample block.
- Sample rate / block size confirmation (reference tone, tuner).
- Units of fields [5]–[8].

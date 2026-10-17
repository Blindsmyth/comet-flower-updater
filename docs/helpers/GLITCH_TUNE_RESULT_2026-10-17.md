# Glitch Tune Results (2026-10-17)

## Method

### Root Cause Analysis
The original `detect_glitches()` algorithm in `tools/ua_capture.py` fitted a forward-only order-28 AR model on first-order differences `np.diff(s_blk)` and normalized prediction residuals against a single global block MAD. While reliable on mains hum and synthetic plucks, on real guitar strumming (`build/ua_takes/starts_tap3/s1.wav` .. `s15.wav`, -22..-28 dBFS), pick attacks produce rapid, non-stationary broadband energy steps where forward residual z-scores $z_f > 6.5$ naturally occur across several consecutive samples. Additionally, the previous outlier rejection heuristic (`bad_d3`) was excising legitimate musical attack transients from the normal equation Gram matrix, destabilizing the AR coefficients on clean strums and causing 14 to 89 false positive "lost frames" per 3-second take.

### Enhancements Implemented
1. **Bidirectional Linear Prediction ($r_f$ and $r_b$)**:
   - For each 4096-sample block of `np.diff(s_blk)`, an order-28 autoregressive model is solved both forward ($X_f \to y_f$, predicting $x[k]$ from past samples) and backward ($X_b \to y_b$, predicting $x[k]$ from future samples) using Tikhonov regularization ($10^{-6}$ on the Gram diagonal).
   - Real USB stream defects (lost frames/splices, repeated slices, dropped samples) create an abrupt discontinuity that breaks continuity in *both* time directions. Natural guitar pick attacks produce asymmetric transients that do not mimic a bilateral point discontinuity.
2. **Strided Sliding-Window Local Scale**:
   - Replaced the global block MAD with `_local_scale(r, win=512, step=32)`: calculates the median absolute deviation across sliding 512-sample windows sampled every 32 samples, and interpolates linearly across the block.
   - This ensures adaptive local normalization: quiet sustain passages adjacent to high-energy strum attacks maintain high sensitivity, while attack peaks scale appropriately without blinding or over-sensitizing the detector.
3. **Anomaly Peak and Pre/Post Contrast Thresholding**:
   - Evaluates bidirectional anomaly peaks: requires $\min(\max(z_f), \max(z_b)) \ge 9.5$.
   - Enforces a temporal contrast ratio: $\min\left(\frac{z_{f,\text{peak}}}{\max(1, z_{f,\text{pre}})}, \frac{z_{b,\text{peak}}}{\max(1, z_{b,\text{post}})}\right) \ge 6.0$, ensuring the residual spike is an isolated point discontinuity rather than the onset of sustained musical energy.
4. **Candidate Clustering and Defect Classification**:
   - Groups neighboring candidate triggers within 4 frames and selects the peak anomaly $m^* = \operatorname{argmax}(z_f + z_b)$.
   - Direct zero-run detection: in active audio ($\text{RMS} > 3.0$), runs of $\ge 4$ zero frames preceded by active audio ($|s| > 10$) are immediately flagged as `zero`.
   - Direct repeat detection: scans local windows for identical repeated slices ($L \in [2, 96]$) or 1-frame repeats where step height is significant compared to local residual scale.
   - Jump vs. lost discrimination: sample jumps require single-sample bounce-back ($\delta_1 \cdot \delta_2 < 0$) with jump magnitude $|s[p] - 0.5(s[p-1] + s[p+1])| > \max(2.0 \cdot sc_f, 10.0)$. Discontinuities without bounce-back are classified as `lost`.

---

## Numbers

### False Events per Clean Take (s1..s15)
Clean guitar strumming corpus from `build/ua_takes/starts_tap3/` (3 seconds each, ~132,300 frames per take):

| Take | Duration | Leading Priming Zeros | Detected Defects (Old) | Detected Defects (New) | Result |
|:---|:---:|:---:|:---:|:---:|:---:|
| `s1.wav` | 3.0 s | 89 frames | 42 | 0 | **PASS** |
| `s2.wav` | 3.0 s | 89 frames | 35 | 0 | **PASS** |
| `s3.wav` | 3.0 s | 89 frames | 28 | 0 | **PASS** |
| `s4.wav` | 3.0 s | 89 frames | 51 | 0 | **PASS** |
| `s5.wav` | 3.0 s | 89 frames | 47 | 0 | **PASS** |
| `s6.wav` | 3.0 s | 89 frames | 19 | 0 | **PASS** |
| `s7.wav` | 3.0 s | 89 frames | 22 | 0 | **PASS** |
| `s8.wav` | 3.0 s | 89 frames | 14 | 0 | **PASS** |
| `s9.wav` | 3.0 s | 89 frames | 89 | 0 | **PASS** |
| `s10.wav` | 3.0 s | 89 frames | 31 | 0 | **PASS** |
| `s11.wav` | 3.0 s | 89 frames | 18 | 0 | **PASS** |
| `s12.wav` | 3.0 s | 89 frames | 25 | 0 | **PASS** |
| `s13.wav` | 3.0 s | 89 frames | 63 | 0 | **PASS** |
| `s14.wav` | 3.0 s | 89 frames | 38 | 0 | **PASS** |
| `s15.wav` | 3.0 s | 89 frames | 21 | 0 | **PASS** |
| **Total** | **45.0 s** | — | **543** | **0** | **0 FALSE POSITIVES** |

### Injected Defect Detection Rate per Kind
USB stream defects injected into `s1`..`s15` at deterministic pseudorandom positions (fixed seed `20261017`, 1 defect per take per kind, 120 total test cases):

| Defect Kind | Size (Frames) | Tested | Detected | Correct Kind | Position Within $\pm 2$ Frames | Accuracy |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `lost` | 1 | 15 | 15 | 15 | 15 | 100.0% |
| `lost` | 8 | 15 | 15 | 15 | 15 | 100.0% |
| `lost` | 44 | 15 | 15 | 15 | 15 | 100.0% |
| `lost` | 45 | 15 | 15 | 15 | 15 | 100.0% |
| `repeat` | 1 | 15 | 15 | 15 | 15 | 100.0% |
| `repeat` | 44 | 15 | 15 | 15 | 15 | 100.0% |
| `zero` | 44 | 15 | 15 | 15 | 15 | 100.0% |
| `zero` | 45 | 15 | 15 | 15 | 15 | 100.0% |
| **Total** | — | **120** | **120** | **120** | **120** | **100.0%** |

### Real 5-Minute Hum Take Verification
Take: `build/ua_takes/longrun_20261016_hum.wav`
- Duration: 300.0 s (13,230,000 frames)
- Leading priming zeros: 89 frames
- Detected events: `[(217, 'lost', 1)]`
- Verified: correctly identifies the single real USB splice near frame 217 with zero false positives across the remaining 5 minutes of continuous audio.

### Runtime Performance
- Single 3.0 s take (`s1.wav`): ~0.19 s
- 120 injection test cases: ~28.2 s (~0.23 s / take)
- 5-minute take (`longrun_20261016_hum.wav`, 13.23M frames): 24.5 s
- **Extrapolated 10-minute take runtime**: ~49.0 s (< 60 s requirement)

---

## Pytest Output

Command:
```powershell
.venv/Scripts/python -m pytest tools/test_ua_capture_glitch.py tests/test_usb_audio_pattern.py -q
```

Output:
```
........................................................................ [ 33%]
........................................................................ [ 66%]
........................................................................ [ 99%]
.                                                                        [100%]
217 passed in 84.23s (0:01:24)
```

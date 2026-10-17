# USB Audio Optimization Report (Argon, 2026-10-16)

## Summary

- **Root Cause of False Clicks (B1, confirmed)**: In `build/ua_takes/take_20261016_172545.wav` (10 s idle take, -34.3 dBFS hum), the old 2nd-difference click detector (`|diff2| > 8 * median(|diff2|) + 50`) flagged 16 false events: 1 at the end of the 89-frame leading zero priming run (frame 87) and 15 on smooth 2.9–4.4 kHz rectifier/switching harmonic bursts riding on the 60/180 Hz mains hum.
- **Linear-Prediction Glitch Detector (B1, confirmed)**: Implemented `detect_glitches(data, order=28, block=4096)` in `tools/ua_capture.py`. Leading zero runs ($\ge 4$ frames at frame 0) are stripped and reported separately as priming. Each 4096-frame block fits an order-28 linear predictor on first differences $\Delta s[n]$ via regularized normal equations (pre-masking extreme 4th-difference rows so defects never corrupt the block $L_2$ fit), normalizes residual $r$ and residual jump $\Delta r$ by $O(N)$-partition MAD, merges nearby flags, and classifies events into `lost`, `repeat`, `zero`, and `jump`.
- **Test Suite (B2, confirmed)**: Added `tools/test_ua_capture_glitch.py` (70 test cases across clean synthetic hum, decaying guitar pluck chain, $\pm 1$ LSB silence, real wav takes, priming, single/multi-frame lost gaps, repeats, zero insertions, sample jumps, and multi-defect streams). All injected defects are located within $\pm 2$ frames (0-frame error in practice) with 0 false events on clean takes.
- **Integration & 10-Min Scalability (B3, confirmed)**: Wired `detect_glitches` into `analyse_audio` in `tools/ua_capture.py` while keeping `analyse_pattern` and level/clipping lines unchanged. Added per-type lines (count + first 10 positions) and `"N defects in M min"` summary. Processes a 10-minute stereo take (26.46 M frames) in **18.92 s** with $O(\text{block})$ bounded memory.
- **Verification**: `.venv/Scripts/python -m pytest tools/test_ua_capture_glitch.py tools/test_usb_audio_proto.py -q` -> **80 passed, 469 subtests passed in 20.49s**.

## B1. Defect Detector Design & Analysis

### 1. Root Cause of False Clicks in `take_20261016_172545.wav` (Confirmed)
- **Observation**: The legacy detector in `tools/ua_capture.py` (`|diff(s, 2)| > 8 * median(|diff(s, 2)|) + 50`) reported 16 false "clicks" on `build/ua_takes/take_20261016_172545.wav` (10 s idle take, 441,000 stereo frames, -34.3 dBFS mains hum) and 20 false "clicks" on `build/ua_takes/take_20261016_170441.wav`.
- **Evidence**:
  1. **Priming end transition (frame 89)**: Both real takes begin with an 89-frame all-zero run (`frames 0..88`) while the USB audio stream primes, followed by the first live audio sample at frame 89 (`1140` LSB in `take_20261016_172545.wav`, `-111` LSB in `take_20261016_170441.wav`), producing `|diff2| = 1140` at frame 87.
  2. **Smooth high-harmonic mains bursts**: Spectral analysis of `take_20261016_172545.wav` shows 60 Hz (706.7 LSB) and 180 Hz (471.8 LSB) mains hum alongside rectifier/switching harmonics around 2.9–3.4 kHz (e.g., frame `300955`, where the waveform smoothly oscillates `[-387, -338, -101, 288, 683, 872, 697, 169, -504]` with period ~10 samples = 4.4 kHz). Because the global median `|diff2|` is dominated by the 60/180 Hz hum (`median = 19` LSB, threshold `202`), periodic 3–4.4 kHz harmonic peaks (`|diff2|` up to `511` LSB) exceed the static second-difference threshold despite being completely smooth and predictable.

### 2. Block Linear Prediction & Residual Jump Detector (Confirmed)
- **Priming Separation**: Leading all-zero frames (`L == 0` and `R == 0` from frame 0, when $\ge 4$ frames) are scanned in 4096-frame chunks and stripped before linear prediction, then reported separately as stream priming (`89` frames on `take_20261016_172545.wav` and `take_20261016_170441.wav`), while preserving original global frame indices for all subsequent events.
- **Pre-Emphasized Autoregressive Model (`order = 28`, `block = 4096`)**:
  - Within each 4096-frame block (with `order` lookback frames prepended from the previous block so block boundaries have zero blind spots), we form the first difference $\Delta s[n] = s[n] - s[n-1]$ (where $s = L$ if $L=R$ else $0.6 L + 0.4 R$) and fit a causal linear predictor of order $P = 28$ via normal equations $(X^T X + 10^{-6} I)\hat{a} = X^T y$.
  - **Why pre-emphasis ($\Delta s$)**: Fitting AR($P$) on $\Delta s[n]$ is equivalent to an order-$(P+1)$ linear predictor on $s[n]$ with unit DC gain ($\sum a_k = 1$). Without pre-emphasis, a 60 Hz fundamental (700 LSB) dominates the $L_2$ loss over higher harmonics, desensitizing the predictor to 1-frame velocity discontinuities; on $\Delta s[n]$, all harmonics are weighted by slope ($\omega A$).
  - **Outlier Pre-Masking Before OLS**: A large defect (e.g. a 44-frame splice or zero insertion) inside a 4096-frame block would otherwise corrupt the $L_2$ fit $\hat{a}$ and inflate the block MAD across the entire block. Before solving $X^T X$, rows within $P$ lags of extreme local 4th-difference spikes ($|\Delta^3(\Delta s)| > 25 \cdot \hat{\sigma}_{\Delta^3}$) are masked from the normal-equation fit so $\hat{a}$ is always fitted on clean waveform segments.
  - **Dual Robust Scaling (Residual & Residual First-Difference)**:
    From the signed prediction residual $r[n] = y[n] - X[n]\hat{a}$ and its step change $\Delta r[n] = r[n] - r[n-1]$, we compute block MAD scales $\hat{\sigma}_r = \max(1.4826 \cdot \text{MAD}(r), 0.7)$ and $\hat{\sigma}_{\Delta r} = \max(1.4826 \cdot \text{MAD}(\Delta r), 0.9)$ using $O(N)$ `np.partition`, and normalized scores $z_r = |r - \text{med}(r)|/\hat{\sigma}_r$, $z_{\Delta r} = |\Delta r - \text{med}(\Delta r)|/\hat{\sigma}_{\Delta r}$.
    Across all 5 clean reference takes (`take_20261016_172545.wav`, `take_20261016_170441.wav`, synthetic hum, synthetic guitar pluck chain, and $\pm 1$ LSB silence), $\max z_{\Delta r} \le 5.51$, whereas even a 1-frame dropout or 1-frame repeat yields $z_{\Delta r} \ge 15..250+$.

### 3. Event Merging & Defect Classification (`lost`, `repeat`, `zero`, `jump`)
When an outlier cluster is triggered, its onset is walked back to the first anomalous frame $p$ (accurate to $\pm 1$ frame) and classified into one of the four physical USB stream defect types:
1. **`zero` (inserted zero frames / zero runs)**: Triggered when $L=R=0$ starts in $[p-2, p+2]$ in an active block ($\text{RMS} > 3$ LSB) and either persists for $\ge 4$ frames or contradicts a non-zero linear extrapolation ($> \max(4\hat{\sigma}_r, 6)$ LSB), or in $\pm 1$ LSB dither silence when an all-zero run persists for $\ge 16$ frames. The recovery transient at $p + L_{\text{zero}}$ is absorbed into the single event `(p, "zero", L_zero)`.
2. **`repeat` (repeated frames)**: Triggered either by a slice replay of lag $L \in [2, 96]$ where $s[\text{rp} : \text{rp}+m] = s[\text{rp}-L : \text{rp}-L+m]$ ($m \ge 2$, walked back to the exact first repeated frame) or a held sample $s[\text{rp}] = s[\text{rp}-1]$ at the anomaly onset where pre- and post-hold slopes match normal signal slope (plus $\ge 16$-frame exact slice repeats in $\pm 1$ LSB silence). Recovery transients up to $\text{rp} + m + P + 2$ are absorbed into `(rp, "repeat", m)`.
3. **`jump` (sample jump / corrupt spike) vs `lost` (spliced-out gap of $1..45+$ frames)**: In near-silence ($\text{RMS} \le 3$ LSB) or when single-sample linear interpolation across $p$ cancels the step error ($\text{step\_err} > 3 \max(\text{interp\_err}, 2\hat{\sigma}_r)$), the defect is classified as `"jump"`; otherwise, when the post-$p$ waveform continues smoothly along a shifted trajectory, it is classified as `"lost"`.

## B2. Synthetic & Real-Take Glitch Test Suite (`tools/test_ua_capture_glitch.py`)

- Created `tools/test_ua_capture_glitch.py` using only `pytest` and `numpy` (no audio device access).
- Covers:
  1. **Zero false events on clean takes**:
     - Synthetic 60 Hz hum + harmonics (180, 300, 540, 900, 1500, 2700 Hz) + Gaussian noise.
     - Synthetic guitar-like decaying pluck chain (4 notes, 12 harmonics with frequency-dependent exponential decay and smooth raised-cosine squared pick attack).
     - Synthetic silence with $\pm 1$ LSB noise.
     - Leading zero priming (89 frames) reported separately with `events == []`.
     - Real recorded `build/ua_takes/take_20261016_172545.wav` (`priming == 89`, `events == []`, `0 defects in 0.17 min`).
  2. **Injected defect localization ($\le \pm 2$ frames) & classification**:
     - Parametrized across signals (`hum`, `pluck`, `silence`), defect lengths (`1, 6..12, 44..45` frames), and positions (`24000..145000`) for all four defect types (`lost`, `repeat`, `zero`, `jump`), plus a combined multi-defect take containing priming and all four defect types simultaneously.
- Additional 180-case multi-position stress test (`build/scratch/argon_usbopt/stress_test2.py`) passed **180/180 (0 failures)**.

## B3. `tools/ua_capture.py` Integration & Verification

- Wired `detect_glitches` into `analyse_audio(data)` in `tools/ua_capture.py`:
  - Pattern-take path (`is_pattern`, `analyse_pattern`, `diag_report`, `variant_report`) is completely unchanged.
  - Level and clipping lines (`L: rms ...`, `R: rms ...`) are preserved identically and computed in 262,144-frame chunks via `_channel_level` so memory stays bounded.
  - Prints `leading zero (priming) frames: <N>`, one line per event type (`lost frames`, `repeated frames`, `inserted zero runs`, `sample jumps`) with count, first 10 positions, and spacing, followed by `<N> defects in <M> min`.
- **Real WAV Analysis Output (`--wav` only)**:
  - `build/ua_takes/take_20261016_172545.wav`:
    ```
    audio take: 441000 frames (10.00 s)
    L: rms 635 (-34.3 dBFS), peak 2346, clipped frames 0
    R: rms 635 (-34.3 dBFS), peak 2346, clipped frames 0
    leading zero (priming) frames: 89
    lost frames: 0, positions []
    repeated frames: 0, positions []
    inserted zero runs: 0, positions []
    sample jumps: 0, positions []
    0 defects in 0.17 min
    ```
  - `build/ua_takes/take_20261016_170441.wav`: `leading zero (priming) frames: 89`, `0 defects in 0.17 min`.
  - `build/ua_takes/take_20261016_140553.wav` (early pre-fix take with real packet drops): `leading zero (priming) frames: 45`, `lost frames: 407`, `repeated frames: 49`, `inserted zero runs: 2`, `458 defects in 0.17 min`.
- **10-Minute Take Benchmark (`build/scratch/argon_usbopt/test_fast_bounded.py`)**:
  - 26,460,000 stereo frames (10.00 min at 44.1 kHz) analysed in **18.92 s** (well under the 60 s limit) with $O(\text{block})$ bounded memory.
- **Pytest Verification**:
  - Command: `.venv/Scripts/python -m pytest tools/test_ua_capture_glitch.py tools/test_usb_audio_proto.py -q`
  - Result: `80 passed, 469 subtests passed in 20.49s`

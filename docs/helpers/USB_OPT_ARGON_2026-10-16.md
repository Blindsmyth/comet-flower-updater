# USB Audio Optimization Report (Argon, 2026-10-16)

## Summary

*(To be completed when B1-B3 are done)*

## B1. Defect Detector Design & Analysis

### 1. Root Cause of False Clicks in `take_20261016_172545.wav` (Confirmed)
- **Observation**: The legacy detector in `tools/ua_capture.py` (`|diff(s, 2)| > 8 * median(|diff(s, 2)|) + 50`) reported 16 false "clicks" on `build/ua_takes/take_20261016_172545.wav` (10 s idle take, 441,000 stereo frames, -34.3 dBFS mains hum) and 20 false "clicks" on `build/ua_takes/take_20261016_170441.wav`.
- **Evidence**:
  1. **Priming end transition (frame 89)**: Both real takes begin with an 89-frame all-zero run (`frames 0..88`) while the USB audio stream primes, followed by the first live audio sample at frame 89 (`1140` LSB in `take_20261016_172545.wav`, `-111` LSB in `take_20261016_170441.wav`), producing `|diff2| = 1140` at frame 87.
  2. **Smooth high-harmonic mains bursts**: Spectral analysis of `take_20261016_172545.wav` shows 60 Hz (706.7 LSB) and 180 Hz (471.8 LSB) mains hum alongside rectifier/switching harmonics around 2.9–3.4 kHz (e.g., frame `300955`, where the waveform smoothly oscillates `[-387, -338, -101, 288, 683, 872, 697, 169, -504]` with period ~10 samples = 4.4 kHz). Because the global median `|diff2|` is dominated by the 60/180 Hz hum (`median = 19` LSB, threshold `202`), periodic 3–4.4 kHz harmonic peaks (`|diff2|` up to `511` LSB) exceed the static second-difference threshold despite being completely smooth and predictable.

### 2. Block Linear Prediction & Residual Jump Detector (Confirmed)
- **Priming Separation**: Leading all-zero frames (`L == 0` and `R == 0` from frame 0, when $\ge 4$ frames) are scanned in 4096-frame chunks and stripped before linear prediction, then reported separately as stream priming (`89` frames on `take_20261016_172545.wav` and `take_20261016_170441.wav`), while preserving original global frame indices for all subsequent events.
- **Pre-Emphasized Autoregressive Model (`order = 24..28`, `block = 4096`)**:
  - Within each 4096-frame block (with `order` lookback frames prepended from the previous block so block boundaries have zero blind spots), we form the first difference $\Delta s[n] = s[n] - s[n-1]$ (where $s = L$ if $L=R$ else $0.6 L + 0.4 R$) and fit a causal linear predictor of order $P = 28$ via normal equations $(X^T X + 10^{-6} I)\hat{a} = X^T y$.
  - **Why pre-emphasis ($\Delta s$)**: Fitting AR($P$) on $\Delta s[n]$ is equivalent to an order-$(P+1)$ linear predictor on $s[n]$ with unit DC gain ($\sum a_k = 1$). Without pre-emphasis, a 60 Hz fundamental (700 LSB) dominates the $L_2$ loss over higher harmonics, desensitizing the predictor to 1-frame velocity discontinuities; on $\Delta s[n]$, all harmonics are weighted by slope ($\omega A$).
  - **Outlier Pre-Masking Before OLS**: A large defect (e.g. a 44-frame splice or zero insertion) inside a 4096-frame block would otherwise corrupt the $L_2$ fit $\hat{a}$ and inflate the block MAD across the entire block. Before solving $X^T X$, rows within $P$ lags of extreme local 4th-difference spikes ($|\Delta^3(\Delta s)| > 25 \cdot \hat{\sigma}_{\Delta^3}$) are masked from the normal-equation fit so $\hat{a}$ is always fitted on clean waveform segments.
  - **Dual Robust Scaling (Residual & Residual First-Difference)**:
    From the signed prediction residual $r[n] = y[n] - X[n]\hat{a}$ and its step change $\Delta r[n] = r[n] - r[n-1]$, we compute block MAD scales $\hat{\sigma}_r = \max(1.4826 \cdot \text{MAD}(r), 0.7)$ and $\hat{\sigma}_{\Delta r} = \max(1.4826 \cdot \text{MAD}(\Delta r), 0.9)$, and normalized scores $z_r = |r - \text{med}(r)|/\hat{\sigma}_r$, $z_{\Delta r} = |\Delta r - \text{med}(\Delta r)|/\hat{\sigma}_{\Delta r}$.
    Across all 5 clean reference takes (`take_20261016_172545.wav`, `take_20261016_170441.wav`, synthetic hum, synthetic guitar pluck chain, and $\pm 1$ LSB silence), $\max z_{\Delta r} \le 5.51$, whereas even a 1-frame dropout or 1-frame repeat yields $z_{\Delta r} \ge 15..250+$.

### 3. Event Merging & Defect Classification (`lost`, `repeat`, `zero`, `jump`)
When an outlier cluster is triggered, its onset is walked back to the first anomalous frame $p$ (accurate to $\pm 1$ frame) and classified into one of the four physical USB stream defect types:
1. **`zero` (inserted zero frames / zero runs)**: Triggered when $L=R=0$ starts in $[p-2, p+2]$ in an active block ($\text{RMS} > 3$ LSB) and either persists for $\ge 4$ frames or contradicts a non-zero linear extrapolation ($> \max(4\hat{\sigma}_r, 6)$ LSB), or when an all-zero run of $\ge 16$ frames occurs in any non-zero block ($\text{RMS} > 0.2$ LSB). The recovery transient at $p + L_{\text{zero}}$ is absorbed into the single event `(p, "zero", L_zero)`.
2. **`repeat` (repeated frames)**: Triggered either by a slice replay of lag $L \in [2, 96]$ where $s[\text{rp} : \text{rp}+m] = s[\text{rp}-L : \text{rp}-L+m]$ ($m \ge 2$, walked back to the exact first repeated frame) or a held sample $s[\text{rp}] = s[\text{rp}-1]$ at the anomaly onset where pre- and post-hold slopes match normal signal slope. Recovery transients up to $\text{rp} + m + P + 2$ are absorbed into `(rp, "repeat", m)`.
3. **`jump` (sample jump / corrupt spike) vs `lost` (spliced-out gap of $1..45+$ frames)**: In near-silence ($\text{RMS} \le 3$ LSB) or when single-sample linear interpolation across $p$ cancels the step error ($\text{step\_err} > 3 \max(\text{interp\_err}, 2\hat{\sigma}_r)$), the defect is classified as `"jump"`; otherwise, when the post-$p$ waveform continues smoothly along a shifted trajectory, it is classified as `"lost"`.

## B2. Synthetic & Real-Take Glitch Test Suite (`tools/test_ua_capture_glitch.py`)

## B3. `tools/ua_capture.py` Integration & Verification

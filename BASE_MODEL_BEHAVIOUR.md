# Base Model Behaviour

Model: `accounts/fireworks/models/minimax-m3`
Environment: drift anomaly, severity=0.8, seed=1
Pass: 400s, max elevation 45°

---

## What the model gets right

- Holds to establish a baseline before acting — good diagnostic instinct
- Correctly identifies drift as the cause of SNR decline
- Applies small targeted corrections rather than snapping immediately
- Maintains lock through most of the pass (vs. constant unlock in the broken environment)
- Reasoning is coherent step-to-step

## What the model gets wrong

### 1. Direction confusion
The model contradicts itself on correction direction within the same episode:
- Step 8: nudges azimuth **negative** (az error +1.18° — correct)
- Step 9: nudges azimuth **positive** because it thinks it overcorrected — but az error is still +1.74° and growing

The model loses track of the fundamental relationship: **positive az error → always nudge negative**. It second-guesses itself based on noisy SNR readings instead of trusting the pointing error directly.

### 2. Holds too long early
Steps 0 and 1 are both holds even though SNR is already declining and az error is visible. One hold is enough to establish a baseline — two is wasteful early in the pass.

### 3. Switches axes prematurely
Step 7 switches to elevation correction while azimuth error is still the dominant cause. This splits attention and allows az drift to worsen.

### 4. Medium nudges too aggressive
Step 8 escalates to medium nudge (+0.5°) when az error is 1.18° and small nudges were working. Overshoots and causes SNR instability.

---

## What RFT should teach

- **Direction is deterministic**: positive error → negative nudge, always. Don't override this based on noisy SNR.
- **Fix one axis at a time**: address the dominant error first, then the secondary.
- **Stay patient on corrections**: small nudges compound. Don't escalate to medium until small nudges clearly aren't converging.
- **One baseline hold is enough**: act sooner when the trend is already clear.

---

## Baseline scores

### Pre-fix environment (broken physics)
| Metric | Value |
|---|---|
| Score | 0.335 |
| Lock fraction | 36.8% |
| Efficiency cost | 0.032 |
| Total slew | 51.5° |

### Post-fix environment (corrected physics)
Fixes applied: TRACKING_LEAK 0.1→0.02, BEAMWIDTH 1.5°→3.0°, drift_rate 0.05→0.02, nudge sign bug fixed.

| Metric | Value |
|---|---|
| Score | 0.583 |
| Lock fraction | 59.8% |
| Efficiency cost | 0.014 |
| Total slew | 22.8° |
| First unlock | t=300s (out of 400s) |

## Additional failure modes (from post-fix run)

### 5. Medium nudges not converging
Steps 18-19: two consecutive `nudge_az_neg_medium` actions while az_error grows +1.94° → +2.10° → +2.66°. The drift rate is outpacing the medium nudge magnitude. RFT should learn to snap earlier rather than chasing with nudges when error exceeds ~2°.

### 6. Unnecessary holds mid-pass
Steps 16-17 both hold while az_error accumulates from +1.28° to +1.94°. 30 seconds of signal degrading while the model waits for confirmation it doesn't need.

### 7. Premature handoff request
Step 26 requests handoff with 10s remaining and link locked. Unnecessary — costs a penalty. The model should learn that handoff is only valid as an emergency action, not a pass-ending routine.

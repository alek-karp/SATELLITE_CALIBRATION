# Agent Action Space

24 discrete actions the agent can take at each timestep.

---

## Pointing Corrections (12 actions)

The antenna has two axes: azimuth (left/right) and elevation (up/down).
Three step sizes per axis per direction — small for fine-tuning, large for recovery.

| Action | Axis | Direction | Step |
|---|---|---|---|
| `nudge_az_pos_small` | Azimuth | Right | +0.1° |
| `nudge_az_neg_small` | Azimuth | Left | -0.1° |
| `nudge_az_pos_medium` | Azimuth | Right | +0.5° |
| `nudge_az_neg_medium` | Azimuth | Left | -0.5° |
| `nudge_az_pos_large` | Azimuth | Right | +2.0° |
| `nudge_az_neg_large` | Azimuth | Left | -2.0° |
| `nudge_el_pos_small` | Elevation | Up | +0.1° |
| `nudge_el_neg_small` | Elevation | Down | -0.1° |
| `nudge_el_pos_medium` | Elevation | Up | +0.5° |
| `nudge_el_neg_medium` | Elevation | Down | -0.5° |
| `nudge_el_pos_large` | Elevation | Up | +2.0° |
| `nudge_el_neg_large` | Elevation | Down | -2.0° |

**When to use:**
- Small nudges: fine correction when error < 0.5°
- Medium nudges: main correction tool during drift anomaly
- Large nudges: fast recovery after full signal loss

**Design tension:** Small nudges are precise but too slow when drift is large.
Large nudges are fast but overshoot when error is already small. The agent
must learn which step size matches which situation.

---

## Receiver Tuning (9 actions)

Controls the electronics that receive and decode the signal.

| Action | Effect | Use case |
|---|---|---|
| `shift_freq_pos_fine` | +10 Hz carrier offset | Fine Doppler correction |
| `shift_freq_neg_fine` | -10 Hz carrier offset | Fine Doppler correction |
| `shift_freq_pos_med` | +100 Hz carrier offset | Medium frequency correction |
| `shift_freq_neg_med` | -100 Hz carrier offset | Medium frequency correction |
| `shift_freq_pos_coarse` | +1000 Hz carrier offset | Escape RFI band |
| `shift_freq_neg_coarse` | -1000 Hz carrier offset | Escape RFI band |
| `cycle_polarization` | Switch H → V → RHCP → LHCP → H | Fix polarization mismatch |
| `narrow_bandwidth` | Halve receiver bandwidth | Reduce noise floor |
| `widen_bandwidth` | Double receiver bandwidth | Recover signal margin |

**When to use:**
- Frequency shifts: when SNR drops suddenly without pointing error (RFI signature)
- `cycle_polarization`: when SNR drops ~3 dB symmetrically (polarization rotation signature)
- `narrow_bandwidth`: when noise temperature spikes (hardware fault signature)
- `widen_bandwidth`: after narrowing too aggressively, to regain margin

---

## Meta Actions (3 actions)

| Action | Effect | Cost | When valid |
|---|---|---|---|
| `snap_to_ephemeris` | Instantly reset antenna to calculated orbital position | 5° slew penalty | Any time |
| `hold` | No movement — take a clean measurement | None | Any time |
| `request_handoff` | Transfer pass to next ground station, end episode | Partial reward only | Last 20% of pass |

**`snap_to_ephemeris`** is the nuclear option. Fixes pointing immediately but:
- Costs a large slew penalty
- Only helps if the problem is pointing (useless for RFI or polarization)
- Agent must learn to use it only when pointing error is large AND anomaly is drift

**`hold`** is the diagnostic action. Stopping all movement gives a clean SNR
measurement with no slew noise. A smart agent should hold before committing
to a correction — especially when the anomaly type is ambiguous.

**`request_handoff`** gracefully exits the episode by passing the satellite
to another ground station. Gives partial reward. Valid only in the last 20%
of the pass — premature requests are penalized.

---

## Action Selection Challenge

The core difficulty: at anomaly onset, all five anomaly types produce a
similar SNR drop signature. The agent must choose actions that serve as
*probes* before committing to a fix:

```
SNR drops at t=210
  → hold (measure cleanly)
  → observe: az_error growing? → drift
  → observe: az_error flat, noise_temp up? → hardware fault
  → observe: az_error flat, noise_temp flat? → RFI or polarization
    → cycle_polarization (test hypothesis)
    → if SNR recovers → polarization was the cause
    → if not → shift_freq (try RFI hypothesis)
```

This multi-step diagnostic sequence is what classical algorithms cannot do,
and what RL must learn to discover.

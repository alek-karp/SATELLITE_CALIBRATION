# Reward Function

> **This documents the live HUD reward** — `GroundStationConsole.score()` in
> `env.py`, which is what `hud eval` reports and what `agent/rft_server.py`
> optimizes. The per-step `+1.0 / −10.0 / −slew` signal inside
> `sim/satellite_env.py.step()` is **legacy** (the old Gymnasium/PPO reward); the
> console ignores it entirely and recomputes the score below from telemetry.

## The live reward

A pass is scored once, at the end, in `[0, 1]`:

```
score = clamp( base − efficiency_cost − contextual_penalty , 0, 1 )
```

### Base — fraction of the pass with usable signal

```python
base = steps_above / pass_duration
```

`steps_above` counts sim-seconds where the **true** (clean) SNR exceeds
`SNR_THRESHOLD` (10 dB). It keys off the clean physics value, not the noisy
observed value the agent sees in telemetry, so the score is **deterministic for
a given seed** — measurement noise straddling the threshold must not jitter the
reward (see `fix(reward): score off clean snr`).

### Efficiency cost — penalize thrash (capped at 0.20)

```python
slew   = 0.25 * (total_slew_deg   / pass_duration)   # antenna movement
thrash = 0.15 * (actuator_uses    / pass_duration)   # freq / pol / bandwidth changes
efficiency_cost = min(0.20, slew + thrash)
```

Expressed per pass-second so pass length doesn't change the calibration. This is
why a thrashing policy underperforms a passive one: every needless slew or
receiver change is pure cost.

### Contextual penalty — acting against the operational brief

Deterministic deductions, opt-in per task via the `rules` dict (see
`WHY_AGENT.md`). Each fires on the agent's action log:

| rule key | magnitude | fires when |
|---|---|---|
| `no_freq_hop` | task-set | any `shift_freq_*` action (advisory said ride out the RFI) |
| `no_large_slew` | task-set | any `*_large` nudge or `snap_to_ephemeris` (log warned the servo sticks) |
| `no_handoff` | task-set | `request_handoff` requested (coordination said none available) |
| `continuous_lock` | task-set | lock dropped at any point (`steps_locked < steps_taken`) |

These are pure functions of the action log and episode spec — no LLM judge, as
verifiable as the base.

## Observed reward landscape (deterministic, seed-fixed)

Measured floor (do-nothing) and skilled ceiling (heuristic tracker), console score:

| task | do-nothing | heuristic | gradient |
|---|---|---|---|
| drift-medium | 0.27 | 0.81 | large |
| drift-easy | 0.47 | 0.93 | large |
| servo-sticky | 0.18 | 0.80 | large |
| drift-hard | 0.00 | 0.42 | large (hard) |
| polarization-medium | 0.72 | 0.83+ | moderate (pol-aware policy higher) |
| clean-pass | 0.88 | 0.94 | small (trivial anchor) |
| rfi / multipath / hardware | 0.24–0.72 | ≈ flat | **little/none — no working mitigation lever** |

The drift family carries the real skill gradient. The RFI/multipath/hardware
anomalies currently lack a working mitigation in the physics model; see the
open-issues note in the project plan.

## What this reward does NOT measure

Speed of recovery, which action caused improvement (credit assignment is the
agent's problem), correct diagnosis as such (only the SNR outcome), bandwidth
efficiency, power. Deliberate simplifications.

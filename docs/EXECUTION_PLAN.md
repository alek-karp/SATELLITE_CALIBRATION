# Execution Plan

How to ship the Ground Station Calibration environment + Gemma agent during the
remaining hackathon window. Goal: make it feel like a real autonomous ground-station
operator, while keeping the build finishable before judging.

**Timing reality:** Hacking started Sat June 20, 12:30 PM. Judging starts Sun 1:30 PM.
The environment is already built and validated (see `episode_test.png`). Remaining
work is the **agent**, the **operational-context layer**, and the **demo**.

---

## Core Demo

Show a Gemma agent in a live pass as the signal degrades from an injected anomaly.
The agent reads the numerical state *and* a natural-language operational brief,
optionally calls `request_context()` to gather more, diagnoses the cause, and recovers
the link — where a Kalman-filter baseline, blind to the brief, makes the wrong call.
Each attempt shows improvement. The headline number: **% of pass with signal locked,
baseline → agent → RFT-tuned agent.**

---

## What We Are Building

- A **Gemma tool-use agent** wired into `SatelliteEnv` via the existing action space
- An **operational-context layer**: per-episode NL briefs + `request_context()` tool
  + deterministic contextual penalties (see `WHY_AGENT.md`)
- A **classical baseline** (the existing heuristic, framed as the "Kalman-style"
  comparison) to make the agent's win legible
- A **demo visualization**: the SNR/pointing/reward arc we already have, extended to
  baseline-vs-agent and an improvement story

## What We Are NOT Building

No real RF hardware. No full ionospheric/tropospheric model. No custom orbital
propagator (Skyfield does it). No real ground-station integration. No training a
model from scratch — Gemma is pretrained; RFT on top is a stretch goal.

---

## Pre-Built Already ✅

- `env/physics.py` — link budget + FSPL, realistic 5–35 dB SNR range
- `env/anomalies.py` — five anomaly types with distinct signatures
- `env/episode_generator.py` — real TLEs (CelesTrak) + procedural anomalies
- `env/satellite_env.py` — Gymnasium env, 24 actions, automatic reward
- `test_specific_episode.py` — deterministic episode, heuristic vs random, validated

The reward signal is confirmed working: heuristic ~+450, random ~-2500.

---

## Episode Design (author 3, same structure)

| Episode | Anomaly | Context twist | Tests |
|---|---|---|---|
| 1 | Pointing drift | Clean brief, no twist | Agent matches heuristic baseline |
| 2 | RFI + drift | Spectrum advisory: "RFI self-clears, don't chase it" | Agent beats baseline by reading context |
| 3 | Unknown/unmodeled fade | Operator log hints at a fix | Zero-shot reasoning the filter bank can't do |

All three reuse the same env. Only the anomaly and context block change.

---

## Agent Interface

```python
# Gemma (via Fireworks) gets, each step:
#   - numerical observation (15-dim, rendered as labeled fields)
#   - operational_context block (episode-level, in the system prompt)
# and emits one of:
#   - an action from the 24-action space
#   - request_context(source)  -> NL report, costs a timestep
```

Use a small Gemma during development for speed; the largest you can RFT for the
final demo. Keep the tool loop synchronous and dead simple.

---

## Priority Order for the Remaining Window

| When | Task |
|---|---|
| Now → 4:30 PM Sat | Operational-context layer: add `operational_context` to episode spec, `request_context()` tool, contextual penalties |
| 4:30 → 6:30 PM Sat | Wire Gemma (Fireworks API) tool-use loop into the env; Episode 1 runs end-to-end |
| 6:30 → 8:00 PM Sat | Dinner; author Episodes 2 & 3 (data, not code) |
| 8:00 → 11:00 PM Sat | Agent beats baseline on Episode 2; capture baseline-vs-agent numbers |
| 11:00 PM → 1:00 AM | Stretch: RFT Gemma on episodes via Fireworks; build improvement-arc plot |
| Sun 8:30 → 11:00 AM | Polish demo, finalize the headline number, presentation |
| Sun 11:00 → 1:30 PM | Buffer, rehearse the 90-second pitch |

---

## Demo Narrative

The environment's physics credibility is the strongest asset: "SNR comes from a real
link budget — free-space path loss, beam pattern, Doppler. If the agent mispoints,
the equation shows it. The agent cannot fake signal."

The agent's win must be legible. Make the contrast explicit:

```
Episode 2 — RFI + drift, advisory says "RFI self-clears, don't chase it"
  Baseline (filter):  hops frequency chasing the RFI, burns slew budget → 61% locked
  Gemma agent:        reads advisory, rides out RFI, fixes drift only    → 94% locked
```

Put the headline in big text: **Signal locked: 61% → 94%.**

---

## Pitch Line

Ground Station Calibration Environment is an RL environment for autonomous satellite
operations. It trains agents to diagnose and recover degrading satellite links under
real orbital physics — Skyfield ephemeris, a full link budget, five anomaly modes —
scored automatically on signal maintained, lock continuity, and slew efficiency, with
a Gemma agent that reads operational context no classical estimator can.

# Pitch: Ground Station Calibration Environment

## The Problem Is Not "Satellites Are Hard to Track"

Routine tracking is already automated — ephemeris plus a control loop points the dish.

The real problem is:

**By 2040, there are too many satellites, with too little margin, for human operators
to babysit each pass — and when a link degrades mid-pass, the agent still has to
diagnose *why* and recover *before the window closes*, often with seconds to spare.**

---

## The 2040 Trajectory

- **Today:** Human operators monitor passes, respond to anomalies, coordinate handoffs
  across ground station networks. Routine pointing is automated; judgment is not.
- **Next:** AI assists operators — flags anomalies, suggests corrections.
- **2040:** Megaconstellations and deep-space missions are operated autonomously.
  A ground-station agent acquires the signal, diagnoses interference vs. drift vs.
  hardware fault, recovers the link, and decides whether to hold or hand off — all
  before a human finishes reading the first alarm.

The market is already here and growing:

- **Planet Labs** operates 200+ Earth-imaging satellites
- **Starlink** has thousands, with more launching weekly
- **NASA's Deep Space Network** runs missions across light-minutes of delay, where
  no real-time human loop is even possible

Every one of these is under economic pressure to reduce operator headcount per pass.

---

## The Hard Part

Not detecting that SNR dropped — that's trivial. The hard part:

- **Diagnosis under ambiguity.** Drift, RFI, polarization rotation, multipath, and
  hardware faults all look alike in the first seconds of degradation.
- **Sequential decisions under a closing window.** Hold and measure, or act now?
  With 400 seconds left you can diagnose carefully. With 30, you snap and pray.
- **Acting on context a number can't carry.** "This pass is downlinking wildfire
  imagery — continuous lock or nothing." "This servo sticks when it's cold."
  That information is linguistic, and it changes what the correct action is.

A classical estimator handles the clean case. The real world is not the clean case.

---

## What We Built

**An RL environment for autonomous ground-station operation.** An agent acquires,
tracks, diagnoses, and recovers a satellite link under realistic physical constraints,
scored automatically on signal maintained, lock continuity, and slew efficiency.

- Real orbital mechanics — live TLEs from CelesTrak, propagated with Skyfield
- A physically-grounded link budget — free-space path loss, antenna beam pattern,
  Doppler, polarization, noise temperature
- Five anomaly types injected procedurally, with an operational-context layer in
  natural language that only a language agent can act on
- A **Gemma** tool-use agent — open weights, so it can be reinforcement-fine-tuned
  directly on the environment's reward (Fireworks AI), aligning with the RFT theme

The reward is fully automatic and verifiable: SNR and lock come straight from the
physics model. No human judgment, no LLM-as-judge.

---

## Why It's Agent-Native, Not Just RL

A bank of Kalman filters can diagnose a *known* anomaly on a *clean* signal. Our
environment adds what they cannot read — mission briefs, operator logs, spectrum
advisories, handoff-availability messages — and a `request_context()` tool that turns
recovery into a sequential information-gathering problem. See `WHY_AGENT.md`.

---

## The One-Liner

**We're building the training ground for the agents that will keep the world's
satellites connected — diagnosing and recovering degraded links autonomously,
under real orbital physics, scored on a signal you cannot fake.**

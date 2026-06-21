# Why an Agent — Not a Classical Estimator

## The Gap in the Base Design

The environment as built is a valid RL problem. But before claiming an LLM agent
belongs here, we have to survive the hardest critique a frontier-lab judge will raise:

> "Diagnosing which of N fault modes is active and responding to it is a *solved
> problem*. Use an **Interacting Multiple Model (IMM)** filter — a bank of Kalman
> filters, one per anomaly hypothesis, with Bayesian model-probability weighting.
> Or train a supervised classifier on the SNR/pointing time-series. Why a language
> model?"

This critique is correct on the **base numerical problem**. IMM / Multiple-Model
Adaptive Estimation is the textbook solution for "estimate state while identifying
which of several known regimes the system is in." On a clean signal with a fixed,
known set of anomalies, a filter bank is competitive with — possibly better than —
any learned policy. Our own heuristic already hit 98% lock on drift.

`WHY_RL.md` argues against a PID controller. That is the easy critique.
This document answers the hard one.

The twist that closes the gap is the same one the grid project discovered:
**operational context that only a language-capable agent can read.**

---

## What Operational Context Is

A real ground station is never operated against a clean numerical state. The
operator has information that is linguistic, unstructured, and decisive:

- **Mission briefs** — what this pass is for, and how much it matters
- **Operator / maintenance logs** — hardware quirks that change which actions are safe
- **Spectrum advisories (NOTAMs)** — known interference sources, in prose
- **Cross-station coordination** — handoff negotiation messages from other sites
- **Novel anomalies** — failure modes not in any filter bank's hypothesis set

A Kalman filter reads `snr`, `az_error`, `noise_temp`. It cannot read:

> "Pass priority HIGH — downlinking time-critical wildfire imagery, partial data
> is worthless, we need a clean continuous lock or nothing."

> "Az servo on this dish sticks intermittently below 10°C ambient. Prefer frequency
> and polarization fixes over large azimuth slews this morning."

> "Radar at the adjacent site sweeps our band every ~40s. Expect periodic RFI;
> do not chase it with frequency hops, ride it out."

The numerical state tells the agent what is **physically possible**.
The operational context tells the agent what is **actually correct**.

---

## The Operational Context Layer

Each episode carries a structured context block alongside the numerical state:

```python
episode = {
    # Numerical — a Kalman filter can read this
    "satellite": "NOAA-19",
    "anomalies": ["rfi", "drift"],

    # Operational context — only the agent can read this
    "operational_context": {
        "mission_brief":
            "HIGH priority. Downlinking wildfire thermal imagery. Partial data "
            "is unusable — maintain continuous lock above 15 dB or request handoff.",
        "operator_logs": [
            "Dish 3 az servo sticks below 10C. Avoid large azimuth slews; "
            "prefer freq/polarization corrections this pass.",
            "Receiver front-end recalibrated yesterday, noise floor nominal."
        ],
        "spectrum_advisory":
            "Adjacent S-band radar sweeps our passband ~every 40s. Periodic RFI "
            "expected. Do NOT frequency-hop to chase it — it self-clears.",
        "handoff_status":
            "Next station (Svalbard) is weathered out. No handoff available "
            "this pass. You must hold the link yourself."
    }
}
```

The same SNR drop now demands a *different* correct action depending on the prose.
An RFI dip that a filter bank would "fix" with a frequency hop is, per the advisory,
something the agent should *ride out* — and chasing it wastes the slew budget the
mission brief says it cannot afford.

---

## The request_context() Tool

The agent has one tool the filter bank does not:

```python
request_context(source: str) -> str   # "operator" | "adjacent_station" | "spectrum"
```

It returns a natural-language report and **costs one timestep**:

```
request_context("adjacent_station")
> "Svalbard here — we're socked in, 40kt winds, can't take your handoff.
>  You're on your own for this pass. Good luck."

request_context("operator")
> "Confirmed az servo is sticky this morning. If you're seeing pointing drift,
>  use small nudges only — a large slew may jam it. Last time it jammed we lost
>  the whole pass."
```

This creates a genuine sequential information-gathering problem: decide whether you
need more context before committing, and which source to query — knowing each query
spends time the pass window does not have. A filter bank has no notion of "ask first."

---

## Novel Anomalies — The Zero-Shot Case

A filter bank can only identify anomalies in its hypothesis set. Add a sixth failure
mode it was never built for — a slow thermal-gradient defocus, a new interference
pattern — and IMM silently misclassifies it as the nearest known mode and applies
the wrong fix.

A language agent that has read the operator log —

> "We've been seeing a weird slow fade on warm afternoons that isn't drift and
>  isn't RFI. Cause unknown. Narrowing bandwidth seemed to help last week."

— can reason about a failure mode **no one encoded**. That is the capability ceiling
classical estimation cannot reach, and it is the heart of the hackathon's premise:
*you can improve models at anything you can verify.*

---

## Agent vs. Estimator — The Comparison

| Situation | IMM / Kalman bank | Gemma agent |
|---|---|---|
| Known anomaly, clean signal | Optimal — wins | Competitive |
| RFI flagged "self-clears" in advisory | Hops frequency (wrong) | Rides it out (correct) |
| Az servo flagged sticky in logs | Large slew, risks jam | Uses freq/pol fixes |
| Mission says "continuous lock or nothing" | Maximizes avg SNR | Trades for continuity, else handoff |
| Handoff unavailable (weather, in prose) | No concept of handoff | Commits to holding link |
| Sixth, unmodeled anomaly | Misclassifies to nearest known | Reasons from log, adapts |

The estimator optimizes the objective it can see. The agent optimizes the objective
that actually matters — given context that requires language understanding to process.

---

## Why Gemma Specifically

- **Open weights → reinforcement-fine-tunable.** This is the whole point of the
  hackathon (RFT workflows). You can RFT Gemma directly on this environment's reward.
  A closed model you cannot. The trained policy *is* the deliverable.
- **Tool-use capable.** Gemma reads numerical state + context and emits actions and
  `request_context()` calls through a clean tool interface.
- **Sponsor alignment.** Gemma is Google DeepMind's open family; Fireworks AI hosts
  and fine-tunes it. Both are sponsors. The stack is the sponsors' stack.
- **Right altitude.** Small enough to RFT in a weekend, capable enough to parse a
  mission brief and reason about a servo log.

---

## Why the Reward Stays Fully Automatic

The context changes what the correct action *is* — but not how reward is *computed*.
SNR, lock, and slew are still numerical, from the physics model. The context adds
deterministic penalties encoded per episode:

```python
CONTEXTUAL_PENALTIES = {
    "lock_dropped_on_high_priority_pass": -25,   # mission brief said continuous
    "large_slew_on_flagged_sticky_servo": -12,   # operator log warned against it
    "freq_hop_against_self_clearing_rfi": -8,    # spectrum advisory said ride it
    "handoff_requested_when_unavailable":  -10,   # coordination said none available
}
```

These are deterministic checks against the agent's action log and the episode's
context spec. No human judgment. No LLM-as-judge. Designed once per episode,
applied automatically — exactly as verifiable as the base reward.

---

## Implementation Cost

The context layer sits on top of the working `SatelliteEnv`:

1. Add `operational_context` dict to the episode spec — **data authoring, not code**
2. Inject context into the agent's initial prompt — **one block of text**
3. Add `request_context(source)` tool with pre-written reports per episode — **~25 lines**
4. Add `CONTEXTUAL_PENALTIES` checks to the reward — **~20 lines**

Build the base agent loop first. Add this layer only after one episode runs end-to-end.
It is what converts "a nice RL env a Kalman filter could also solve" into
"an environment that requires an agent."

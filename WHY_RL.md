# Why Classical Algorithms Can't Solve This

## What Classical Algorithms CAN Do

| Algorithm | What it handles |
|---|---|
| PID controller | Nominal tracking — follows ephemeris perfectly |
| Kalman filter | Tracks pointing error with noise smoothing |
| Lookup table | "If drift detected → nudge az" |
| Heuristic agent | Single known anomaly type with clear signature |

Our heuristic agent proved this: 98% lock time on a drift anomaly, because
we hard-coded the rule. That's the ceiling for classical approaches.

---

## Where They Break Down

### 1. Ambiguous Diagnosis

When SNR drops, the cause could be any of five things:
- Pointing drift
- RFI burst
- Polarization rotation
- Multipath fading
- Hardware fault

All five look similar in the first 5–10 seconds of degradation. A PID controller
only knows how to turn a knob — it has no model of *why* the signal dropped.
The heuristic handles drift because we hard-coded that rule. It has no rule for
"drift + RFI simultaneously."

### 2. Sequential Decision Making Under Uncertainty

The right response to an unknown anomaly is:
```
hold → measure → form hypothesis → act → measure → confirm or revise
```

That's 4–5 steps of reasoning before committing to a fix. No classical algorithm
does this. PID reacts immediately. Lookup tables have no memory. Neither can say
"let me check if narrowing bandwidth helps before I start slewing."

### 3. Multiple Simultaneous Anomalies

If drift + RFI hit at the same time, the optimal strategy is:
1. Fix frequency first (fast, recovers margin immediately)
2. Then correct pointing (slower, requires physical antenna movement)

The ordering matters. The correct order depends on relative severity of each
anomaly. A PID has no concept of priority. A lookup table explodes combinatorially:

```
5 anomaly types × 5 severity levels × combinations = thousands of rules
```

And that's before accounting for interactions between anomaly types.

### 4. Time Horizon Awareness

- With 400 seconds left: take time to diagnose carefully, try things
- With 30 seconds left: snap to ephemeris and accept the slew cost

PID has no concept of remaining pass time. An RL policy trained with
`time_remaining` in the observation learns this tradeoff implicitly — it
discovers that risky fast actions are worth it late in the pass.

---

## The Honest Caveat

For a *single known anomaly type* with *clean observations*, a well-tuned
classical algorithm wins. The heuristic we built proved that.

The RL case is justified when:
- Anomaly type is unknown at onset
- Multiple anomalies are active simultaneously
- Observations are noisy (diagnosis is uncertain)
- Time-pressure tradeoffs require planning

That is the regime classical methods fail — and the regime the real world
operates in. Planet Labs, DSN operators, and Starlink ground teams all face
exactly this problem at scale.

---

## What RL Learns That Rules Cannot Encode

A trained PPO policy implicitly learns:

- **Anomaly fingerprints** — drift has a different SNR signature than RFI
- **Action ordering** — fix frequency before pointing in mixed anomalies
- **Diagnostic patience** — hold and measure before committing to a correction
- **Time-aware risk tolerance** — aggressive snaps are worth it near pass end
- **Recovery sequencing** — after lock loss, re-acquire before fine-tuning

None of these can be written as a simple rule. All of them emerge from reward
maximization over thousands of episodes.

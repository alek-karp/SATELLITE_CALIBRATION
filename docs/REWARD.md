# Reward Function

## Current Implementation

```python
# Every timestep:
if snr >= SNR_THRESHOLD:                          # 10 dB
    reward += 1.0                                 # signal maintained
elif snr > SNR_LOCK_MIN:                          # 5–10 dB band
    reward += (snr - 5) / (10 - 5)               # shaped ramp [0, 1)
if not locked:                                    # SNR < 5 dB
    reward -= 10.0                                # lock lost
reward -= slew * 0.1                              # antenna movement cost
reward -= actuator_cost                           # 0.05 per freq/pol/bandwidth change
reward += handoff_penalty                         # -5.0 if premature, else 0

# Special cases:
# valid request_handoff (last 20%): reward = total_reward_so_far * 0.3, episode ends
```

> Reward is **per-step (dense)**, not final-outcome. The agent gets feedback
> every second of the pass. Only the valid-handoff bonus is terminal.

---

## What Each Term Rewards

### +1.0 per timestep — Signal above threshold

**What:** SNR > 10 dB, measured every second for 600 seconds.

**Why 10 dB:** This is the minimum usable signal for data reception on a
typical LEO downlink. Below this, bit error rate becomes too high for reliable
communication. It's the industry standard threshold.

**Why +1.0:** Accumulates to a maximum of +600 over a perfect pass.
Simple, dense, and gives the agent a reward signal at every single step —
no sparse reward problem.

**What it incentivizes:** Stay above threshold continuously. Not just recover
eventually — maintain signal throughout the pass window.

---

### -10.0 per timestep — Lock lost

**What:** SNR drops below 5 dB. The receiver loses phase lock entirely.
Recovering from lock loss is harder than maintaining it — the agent must
re-acquire from scratch.

**Why -10.0:** Ten times the positive reward for maintaining signal.
This asymmetry teaches the agent that prevention is far better than recovery.
A single second of lock loss costs as much as 10 seconds of good signal.

**Why a separate lock threshold (5 dB) vs. signal threshold (10 dB):**
Creates a 5 dB buffer zone. Falling from 10 dB to 8 dB is bad but not
catastrophic — only full lock loss triggers the severe -10.0.

**Shaped ramp in the 5–10 dB band:** Instead of a flat zero between lock and
threshold, reward ramps linearly from 0 (at 5 dB) to 1.0 (at 10 dB). This
removes the "dead zone" where recovery actions produced no reward signal, so
the agent gets a dense gradient telling it whether it is getting warmer or
colder while climbing back toward threshold.

---

### -0.05 per use — Freq / polarization / bandwidth change

**What:** Any `shift_freq`, `cycle_polarization`, `narrow/widen_bandwidth`
action costs a flat 0.05.

**Why:** Antenna movement was already penalized via slew, but these channels
were free — so the agent could thrash frequency/polarization/bandwidth at no
cost. A small flat cost discourages spamming them while staying cheap enough
to use when a correction genuinely helps.

---

### Tracking leak — every episode is a real task

**What:** Each step, 10% of the satellite's ephemeris motion leaks in as
pointing error the agent must actively correct (imperfect nominal tracking).

**Why:** Without it, episodes with no anomaly had nothing to solve. The leak
guarantees a continuous tracking task in every episode; anomalies stack on
top. With a 1.5° beamwidth, uncorrected drift reaches the signal cliff in
~40 steps, so the agent must track but can recover.

---

### -0.1 × slew — Movement cost

**What:** Every degree of antenna movement costs 0.1 reward points.
- `nudge_az_small` (0.1°): costs 0.01
- `nudge_az_medium` (0.5°): costs 0.05
- `nudge_az_large` (2.0°): costs 0.20
- `snap_to_ephemeris` (5.0°): costs 0.50

**Why:** Without this, the agent would thrash — constantly moving the antenna
even when signal is already good. Real antennas have mechanical wear, power
consumption, and servo load. Unnecessary movement is waste.

**Why 0.1 ratio:** Small enough that the agent will still move when needed
(a 2° correction costs 0.20 but recovers +1.0/step), but large enough to
discourage jitter. The agent learns to move purposefully, not randomly.

**What it incentivizes:** Hold when signal is good. Use small nudges for
fine corrections. Reserve large nudges and snap for genuine emergencies.

---

### -5.0 — Premature handoff request

**What:** Requesting handoff before 80% of the pass is complete.

**Why:** Handoff is a last resort. Abandoning a pass early wastes the
ground station asset. The penalty teaches the agent to persevere through
anomalies rather than give up.

---

### ×0.3 multiplier — Valid handoff

**What:** If the agent requests handoff in the last 20% of a pass, the
episode ends early and the agent receives 30% of its accumulated reward.

**Why not 100%?** Early termination should always be slightly suboptimal
compared to completing the pass. The multiplier ensures the agent prefers
to stay and finish, but isn't catastrophically penalized for a legitimate
strategic handoff near pass end.

---

## Reward Ranges

| Scenario | Expected reward |
|---|---|
| Perfect pass (100% above threshold, minimal slew) | ~+580 |
| Good pass (tracking heuristic, with anomalies) | +400 to +580 |
| Average pass (RL agent, mixed anomalies) | +100 to +400 |
| Random agent | ~-3500 |
| Hold-only (no tracking) | ~-4400 |

The gap between random (~-3500) and heuristic (~+580) is ~4000 points.
That is the learning gradient PPO optimizes over. Note that "do nothing"
(hold-only) is *worse* than random, because the tracking leak makes passive
holding drift off-target — there is no free lunch.

---

## Ratio Justification

```
Signal maintained : Lock lost : Slew
     +1.0         :   -10.0   :  -0.1/°
```

**10:1 penalty ratio (lock lost vs. signal maintained):**
Calibrated so that one second of lock loss requires 10 seconds of good
signal to break even. This creates strong pressure to stay above lock
threshold rather than yo-yo across it.

**0.1 slew ratio:**
The breakeven point for a 2° nudge is 0.2 seconds of signal. Any correction
that restores signal for more than 0.2 steps is net positive. This means
the agent will always correct when it expects the fix to hold, but won't
thrash when the signal is already good.

**No explicit anomaly detection reward:**
Intentional. Rewarding "correctly identified the anomaly" would require
ground truth labels at training time. Instead, the agent is only rewarded
for outcomes (SNR maintained). It must learn diagnostic skill implicitly
as a means to that end — which is more robust and generalizes better.

---

## What This Reward Does NOT Measure

- Speed of recovery (only outcome, not time-to-recover)
- Which action caused the improvement (credit assignment is the agent's problem)
- Correct diagnosis (only correct outcome matters)
- Bandwidth efficiency (not modeled)
- Power consumption (simplified away)

These are deliberate simplifications for the prototype. A production version
would add a recovery speed bonus and an efficiency term.

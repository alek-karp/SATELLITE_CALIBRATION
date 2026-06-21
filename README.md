# Ground Station Calibration — RL Environment

An RL environment for autonomous satellite ground-station operation. An agent
acquires, tracks, diagnoses, and recovers a degrading satellite link under realistic
orbital physics, scored automatically on signal maintained, lock continuity, and slew
efficiency.

Built for the HUD Frontier/RSI RL Environments Hackathon. Agent: **Gemma** (open
weights, reinforcement-fine-tunable on the environment reward via Fireworks AI).

---

## Documents

| Doc | What's in it |
|---|---|
| [PITCH.md](PITCH.md) | The problem, the 2040 vision, the market, the one-liner |
| [ENVIRONMENT.md](ENVIRONMENT.md) | Full environment design: state, episode arc, generation, curriculum, physics |
| [ACTIONS.md](ACTIONS.md) | All 24 agent actions, use cases, the diagnostic challenge |
| [REWARD.md](REWARD.md) | Reward function, every term, the ratios and why |
| [WHY_RL.md](WHY_RL.md) | Why a PID controller / lookup table can't do this |
| [WHY_AGENT.md](WHY_AGENT.md) | Why an LLM agent beats a Kalman-filter bank — the operational-context twist |
| [EXECUTION_PLAN.md](EXECUTION_PLAN.md) | Hour-by-hour build plan for the remaining hackathon window |

Read order for a new reader: **PITCH → ENVIRONMENT → WHY_RL → WHY_AGENT → REWARD → ACTIONS → EXECUTION_PLAN.**

---

## Code

```
sim/                     Satellite ground-station simulation package
  physics.py             Link budget + free-space path loss → SNR
  anomalies.py           Five anomaly types + injection
  episode_generator.py   Real TLEs (CelesTrak) + Skyfield arcs + procedural anomalies
  satellite_env.py       Gymnasium environment, 24 actions, automatic reward
env.py                   HUD v6 environment: sim wrapped as agent tools + task templates
tasks.py                 Concrete task rows for `hud eval` / `hud sync tasks`
tests/                   Pytest suite (offline env, scoring, tools, served capability)
scripts/                 Standalone scripts (run with `uv run python scripts/<name>.py`)
  manual_rollout.py      Smoke test across easy/medium/hard
  inspect_episode.py     Deterministic episode, heuristic vs random, validation plot
  demo_baseline_vs_agent.py  Headline demo: context-aware vs context-blind operator
docs/                    Design docs and generated plot assets
  assets/episode_test.png             Validation result (heuristic 98% lock vs random 49%)
  assets/demo_baseline_vs_agent.png   Demo result (signal above threshold: baseline 38% → agent 100%)
```

## HUD v6 (RL environment)

```bash
uv sync                                       # install deps into a local venv
hud set HUD_API_KEY=your-key-here             # get one at hud.ai/project/api-keys
hud eval tasks.py claude --task-ids drift-medium --group 3   # run a local eval
uv run python env.py                          # no-model smoke: boot a task, print reward
uv run pytest tests/                          # offline unit tests
```

## Quickstart

```bash
pip3 install skyfield gymnasium numpy matplotlib stable-baselines3
python3 test_env.py                # random rollout across difficulties
python3 test_specific_episode.py   # deterministic episode + validation plot
```

---

## Status

- ✅ Environment built and validated — realistic SNR, real orbital arcs, 5 anomalies
- ✅ Reward signal confirmed — heuristic ~+450 vs random ~-2500 (a ~3000-pt gradient)
- ⏳ Gemma tool-use agent — in progress (see EXECUTION_PLAN.md)
- ⏳ Operational-context layer — in progress (see WHY_AGENT.md)
- ⏳ RFT on Gemma via Fireworks — stretch goal

---

## The Core Claim

You can improve a model at anything you can verify. Here, the thing worth teaching is
keeping a satellite link alive — diagnosing interference from drift from hardware fault
and recovering before the pass window closes — under physics you cannot fake and
operational context only a language agent can read.

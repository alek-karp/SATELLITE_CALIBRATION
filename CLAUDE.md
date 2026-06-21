@AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # install deps into .venv (Python 3.11–3.12 required)
uv run pytest tests/             # run the test suite (asyncio_mode=auto)
uv run python env.py             # no-model smoke test: boots a task and prints reward
uv run python scripts/manual_rollout.py        # smoke test across easy/medium/hard
uv run python scripts/inspect_episode.py       # heuristic vs random, generates plot
uv run python scripts/demo_baseline_vs_agent.py  # context-aware vs context-blind demo
uv run hud eval tasks.py Qwen/Qwen3-8B --task-ids drift-medium --group 3   # run agent via HUD gateway (requires HUD_API_KEY)
uv run hud eval tasks.py claude --task-ids drift-medium --group 3   # frontier-model anchor for comparison
uv run agent/gemma_agent.py --anomaly drift --seed 1   # legacy standalone Fireworks loop (requires FIREWORKS_API_KEY)
```

## Architecture

This is a **HUD v6 RL environment** for autonomous satellite ground-station operation.

### Layer stack

```
tasks.py          Task definitions (10 tasks) — imported by `hud eval`
env.py            HUD v6 environment: wraps sim/ as agent-facing MCP tools
sim/              Gymnasium simulation package
  satellite_env.py    Gym env, 24 discrete actions, step loop, reward signal
  physics.py          Link budget + free-space path loss → SNR
  anomalies.py        5 anomaly types (drift, rfi, polarization, multipath, hardware)
  episode_generator.py  Real TLEs via CelesTrak/Skyfield + procedural anomaly injection
agent/
  gemma_agent.py   Legacy standalone Fireworks loop driving GroundStationConsole (pre-HUD)
  rft_server.py    Fireworks RFT training server (legacy; HUD path uses trainable models)
```

### Key data flow

1. `hold_the_link` (env.py `@env.template`) builds a deterministic `EpisodePlan` and wraps it in a `GroundStationConsole`.
2. The console is exposed to agents via a `FastMCP` server started in `@env.initialize`. Three tools: `get_telemetry`, `take_action`, `request_context`.
3. `take_action` maps action name → `SatelliteEnv.step()` → SNR computed by `physics.compute_snr()` → reward.
4. Score (0–1) = `steps_above_threshold / pass_duration` − efficiency_cost − contextual_penalties.

### Reward structure

- **Base**: fraction of pass steps where SNR > 10 dB (usable threshold).
- **Shaped band**: partial credit in 5–10 dB range so the gradient is dense during recovery.
- **Efficiency cost** (capped at 0.20): penalizes excess antenna slew (0.25 × deg/pass-s) and receiver thrash (0.15 × changes/pass-s).
- **Contextual penalties**: deterministic deductions for ignoring natural-language operational context (e.g., freq-hopping when an advisory says ride it out). Tasks opt in via the `rules` dict.

### Operational-context twist

Some tasks include a `context` dict (mission brief, spectrum advisory, operator log) and a `rules` dict. The agent must call `request_context(source)` to fetch reports (costs ~5 sim-seconds each), then act on them. The `rules` dict is the deterministic grader checking compliance. This is the core research claim: an LLM agent can read and act on operational context that a numeric controller cannot.

## Commit format

```
prefix(area): message
```
- Single line only. No body.
- `prefix`: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- `area`: `reward`, `env`, `physics`, `anomalies`, `episode`, `agent`, `tasks`

# AGENTS.md

## Run logs

Agent episode logs are saved to `data/runs/` as JSON files.

Filename format: `<timestamp>_<anomaly>_seed<N>.json`

Each file contains:
- `score` — full score breakdown (base_lock_fraction, efficiency_cost, total_slew_deg, etc.)
- `decisions` — full decision log with action, reasoning, and telemetry at each step

Use these to track baseline vs post-RFT performance and debug agent behaviour.

---

## HUD workflow

Use the local HUD environment-builder skill for HUD-specific implementation or
setup questions:

`/Users/alekkarp/.agents/skills/hud-environment-builder/SKILL.md`

HUD is a project dependency, not a globally available CLI on this machine. Run
HUD commands through `uv run` unless the virtualenv is already activated.

Local eval:

```bash
uv run hud eval tasks.py claude --task-ids drift-medium --group 3
```

Full Qwen/HUD Gateway eval:

```bash
uv run hud eval tasks.py Qwen/Qwen3-8B \
  --gateway \
  --all \
  --group 3 \
  --max-steps 60 \
  --max-concurrent 5 \
  --auto-respond \
  -y
```

Evaluate a trained HUD model fork with the same settings:

```bash
uv run hud eval tasks.py satellite-qwen3-8b \
  --gateway \
  --all \
  --group 3 \
  --max-steps 60 \
  --max-concurrent 5 \
  --auto-respond \
  -y
```

Use `--auto-respond` consistently for Qwen/tool-use comparisons. Without it,
Qwen may return text instead of an OpenAI-compatible tool call, HUD treats the
run as complete, and traces can jump from `setup` straight to `evaluate` with no
`get_telemetry` / `take_action` steps. Compare base vs trained runs only when
both use the same auto-respond setting.

Keep local `--max-concurrent` capped. The default can be 30, which may exhaust
local MCP/socket resources during `--all --group 3` runs. Start with 5 and raise
gradually only if the machine stays stable.

Platform deploy/sync:

```bash
uv run hud deploy .
uv run hud sync tasks satellite-calibration tasks.py
```

The environment owns the deterministic score in `env.py`; HUD packages, runs,
tracks, and records evals.

---

## File naming

Use uppercase filenames for Markdown documents, e.g. `TASKS.md`, `README.md`,
and `AGENTS.md`.

---

## Commit format

```
prefix(area): message
```

- Single line only. No body, no description.
- `prefix`: one of `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- `area`: the part of the repo touched, e.g. `reward`, `env`, `physics`, `anomalies`, `episode`.
- `message`: short, imperative, lowercase.

Examples:

```
fix(reward): apply premature handoff penalty
feat(env): add tracking leak so every episode is a task
docs(reward): document shaped reward band
```

# AGENTS.md

## Run logs

Agent episode logs are saved to `data/runs/` as JSON files.

Filename format: `<timestamp>_<anomaly>_seed<N>.json`

Each file contains:
- `score` — full score breakdown (base_lock_fraction, efficiency_cost, total_slew_deg, etc.)
- `decisions` — full decision log with action, reasoning, and telemetry at each step

Use these to track baseline vs post-RFT performance and debug agent behaviour.

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

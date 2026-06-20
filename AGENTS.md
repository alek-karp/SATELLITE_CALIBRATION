# AGENTS.md

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

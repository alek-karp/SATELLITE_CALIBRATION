# Baseline Scores

Anchor: **Claude (Sonnet 4.6)** via `hud eval ... --group 3 --max-steps 60 --remote`.
Each task run 3× on its fixed seed; mean shown. These are the reference the
post-RFT Gemma checkpoints get compared against.

Date: 2026-06-20

## Single-anomaly (matrix #1)

| Task | Rollouts | Mean | Notes |
|---|---|---|---|
| drift-medium | 0.691, 0.753, 0.815 | 0.75 | healthy |
| rfi-medium | 0.591, 0.626, 0.565 | 0.59 | healthy |
| polarization-medium | 0.760, 0.770, 0.754 | 0.76 | healthy |
| multipath-medium | 0.817, 0.837, 0.836 | 0.83 | healthy |
| hardware-medium | 0.245, 0.245, 0.245 | 0.25 | ⚠ flat — no within-group spread, likely do-nothing floor. Exclude from RFT taskset / investigate. |

## Curriculum + context (matrix #2)

| Task | Rollouts | Mean | Notes |
|---|---|---|---|
| clean-pass | 0.941, 0.870, 0.953 | 0.92 | healthy; possibly too easy for RFT |
| drift-easy | 0.860, 0.948, 0.947 | 0.92 | healthy; possibly too easy for RFT |
| drift-hard | 0.517, 0.524, 0.530 | 0.52 | beats ~0.42 skilled-tracker target — solvable |
| rfi-advisory | 0.272, 0.197, 0.213 | 0.23 | context task; low = ignoring advisory or penalties harsh. Investigate. |
| servo-sticky | 0.601, 0.618, 0.556 | 0.59 | context task; partial compliance |

## Open items

- **hardware-medium**: flat 0.245 ×3 → no gradient. Exclude from RFT taskset until fixed.
- **rfi-advisory**: trace-check whether Claude ignores the no-freq-hop advisory.
- **Weak-model anchor (Gemma) pending** — needed to confirm RFT headroom (Claude high + weak model low).

## Columns to add later

| | Claude (above) | pre-RFT Gemma | post-RFT Gemma |
|---|---|---|---|
| fill in | done | — | — |

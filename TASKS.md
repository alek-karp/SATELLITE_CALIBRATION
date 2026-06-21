# Tasks

## Baseline collection

1. Sync local tasks to the deployed HUD environment:

   ```bash
   uv run hud sync tasks satellite-calibration tasks.py
   ```

2. Run the first baseline matrix: five anomaly tasks, three rollouts each.

   ```bash
   uv run hud eval satellite-calibration claude \
     --task-ids drift-medium,rfi-medium,polarization-medium,multipath-medium,hardware-medium \
     --group 3 \
     --max-steps 60 \
     --remote
   ```

3. Run the second baseline matrix: curriculum and context tasks, three rollouts
   each.

   Tasks 6, 7, and 8 are:

   - `clean-pass`
   - `drift-easy`
   - `drift-hard`

   Include the two operational-context tasks in the same batch:

   ```bash
   uv run hud eval satellite-calibration claude \
     --task-ids clean-pass,drift-easy,drift-hard,rfi-advisory,servo-sticky \
     --group 3 \
     --max-steps 60 \
     --remote
   ```

4. Record per-task results:

   - mean reward
   - min/max reward
   - standard deviation
   - common failure modes from traces
   - whether rewards saturate near 0 or 1

5. Inspect traces:

   ```bash
   uv run hud jobs
   uv run hud trace <trace-id>
   ```

6. Patch any obvious task or environment issues before training:

   - agent cannot discover or use tools
   - prompt ambiguity
   - reward too harsh or too easy
   - task ends before enough decisions happen
   - agent gets rewarded for bad behavior
   - context tasks do not force useful `request_context` behavior

## Anchor evals

Run at least one weak/cheap model and one strong model against the same tasks.
Use the results to confirm the taskset has useful reward spread across capability
levels.

## Fireworks/Gemma baseline

Run the current Gemma agent locally for comparable decision logs:

```bash
uv run agent/gemma_agent.py --anomaly drift --seed 1
uv run agent/gemma_agent.py --anomaly rfi --seed 2
uv run agent/gemma_agent.py --anomaly polarization --seed 3
uv run agent/gemma_agent.py --anomaly multipath --seed 4
uv run agent/gemma_agent.py --anomaly hardware --seed 5
```

Saved logs go to `data/runs/`.

## Pre-RFT gate

Before training:

- confirm within-group reward spread
- confirm traces show multi-step tool use
- confirm no obvious reward hacking path
- freeze `env.py` scoring
- decide the fixed evaluation taskset and seeds

If the reward changes after training starts, fork a fresh model or roll back to a
checkpoint from before the objective change.

## RFT path

1. Host `agent/rft_server.py` publicly.
2. Register it with Fireworks Eval Protocol.
3. Run GRPO/RFT against randomized episodes.
4. Periodically evaluate checkpoints through the HUD taskset.
5. Compare post-RFT checkpoints against the baseline matrix.

# Satellite Calibration Episode Demo

Standalone browser demo for playing through a hardcoded ground-station episode.

## What it shows

- A satellite moving through orbit
- Earth with a surface-mounted receiver antenna
- A live beam between antenna and satellite
- Telemetry for SNR, lock, pointing error, tuning state, reward, and score
- Buttons for the 24 environment actions from `ACTIONS.md`

## How to play

- Press `Run` to let the episode advance automatically, or `Step` to advance one tick.
- Choose the action the agent should take on the next tick.
- Keep SNR above 10 dB and preserve lock through acquisition, anomaly recovery, tracking, and final handoff.
- `request_handoff` is only accepted during the final 20% of the pass.

## Run

Open `index.html` in a browser.

If your browser blocks module imports from local files, run a tiny static server:

```bash
python3 -m http.server 8000
```

Then visit `http://localhost:8000/web_agent_scene/`.

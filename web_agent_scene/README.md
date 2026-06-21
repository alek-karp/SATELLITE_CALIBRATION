# Satellite Calibration Episode Demo

Standalone browser demo for watching a hardcoded ground-station episode play through end to end.

## What it shows

- A satellite moving through orbit
- Earth with a surface-mounted receiver antenna
- A live beam between antenna and satellite
- Telemetry for SNR, lock, pointing error, tuning state, reward, and score
- A scripted agent that performs acquisition, anomaly recovery, tracking, and handoff

## Demo arc

- The episode starts automatically.
- The scripted agent slews onto the pass, corrects polarization rotation, recovers from pointing drift, and requests final handoff.
- The HUD shows the current action and telemetry as the pass runs.

## Run

Open `index.html` in a browser.

If your browser blocks module imports from local files, run a tiny static server:

```bash
python3 -m http.server 8000
```

Then visit `http://localhost:8000/web_agent_scene/`.

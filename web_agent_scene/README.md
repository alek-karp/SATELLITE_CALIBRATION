# Satellite Agent 3D Action Scene

Standalone browser demo for visualizing the ground-station agent in 3D.

## What it shows

- A satellite moving through orbit
- Earth with a surface-mounted receiver antenna
- A live beam between antenna and satellite
- Buttons for the 24 environment actions from `ACTIONS.md`

## Run

Open `index.html` in a browser.

If your browser blocks module imports from local files, run a tiny static server:

```bash
python3 -m http.server 8000
```

Then visit `http://localhost:8000/web_agent_scene/`.

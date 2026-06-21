"""Gemma agent via Fireworks AI for the satellite ground-station environment.

At each decision step the agent:
  1. Reads telemetry from the GroundStationConsole.
  2. Sends it to Gemma (Fireworks AI) with a tool definition for take_action.
  3. Parses Gemma's tool call and executes the action.
  4. Repeats until the pass is complete.

Usage:
    export FIREWORKS_API_KEY="fw_..."
    uv run agent/gemma_agent.py [--anomaly drift] [--seed 1] [--model gemma3-27b-it]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fireworks.client import Fireworks

from env import (
    ACTIONS,
    GroundStationConsole,
    POL_NAMES,
    STEP_SECONDS,
    _ACTION_REFERENCE,
    _build_episode,
)
from sim import SNR_THRESHOLD

DEFAULT_MODEL = "accounts/fireworks/models/minimax-m3"

ACTIONS_LIST = "\n".join(f"  - {a}" for a in ACTIONS)

SYSTEM_PROMPT = f"""\
You are an expert satellite ground station operator. A satellite is passing
overhead and you must keep the downlink signal alive until the pass ends.

At each step you will receive the current telemetry. Respond with a JSON object
(no markdown, no extra text) with exactly these fields:
  {{"action": "<action_name>", "reasoning": "<one sentence why>"}}

Valid actions:
{ACTIONS_LIST}

Strategy:
- If SNR is dropping, diagnose the cause before acting.
- Use 'hold' to get a clean baseline reading first.
- Prefer targeted corrections (frequency shift for RFI, nudge for pointing drift).
- Avoid unnecessary antenna movement — it wastes time and causes wear.
- If time is short (< 60 s remaining), snap to ephemeris to recover quickly.
"""


def _build_context_summary(log: list[dict], console: GroundStationConsole) -> str:
    """Compress episode history into a fixed-size summary (~150 tokens).

    Gives the model memory of what it tried and what worked, without
    growing the context window with every step.
    """
    ep = console.gym._episode
    remaining = max(0, ep.pass_duration - console.gym._t)
    snr_history = console.gym._snr_history

    trend = ""
    if len(snr_history) >= 3:
        delta = snr_history[-1] - snr_history[-3]
        trend = f"↑{delta:+.1f}" if delta > 0 else f"↓{delta:+.1f}"

    lines = [f"Step {len(log)}/{ep.pass_duration // STEP_SECONDS} | {remaining}s remaining | SNR trend: {trend}"]

    if log:
        recent = log[-4:]
        lines.append("Recent actions (oldest→newest):")
        for r in recent:
            snr_after = r["telemetry_after"].split("\n")[1] if "\n" in r["telemetry_after"] else ""
            lines.append(f"  {r['action']}: {snr_after.strip()}")

    return "\n".join(lines)


def run_episode(
    console: GroundStationConsole,
    model: str = DEFAULT_MODEL,
    max_decisions: int = 60,
    verbose: bool = True,
) -> list[dict]:
    """Drive one satellite pass with the model making decisions.

    Returns a list of decision records:
      {"action": str, "reasoning": str, "telemetry_after": str}
    """
    client = Fireworks(api_key=os.environ["FIREWORKS_API_KEY"])
    log: list[dict] = []

    for step in range(max_decisions):
        if console.done:
            break

        telemetry = console.telemetry()
        summary = _build_context_summary(log, console)

        # Fixed context: system + summary + current telemetry (~300 tokens max)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{summary}\n\nCurrent telemetry:\n{telemetry}"},
        ]

        time.sleep(10)  # stay under rate limit
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )

        raw = response.choices[0].message.content or ""

        # Parse JSON — strip markdown fences if present
        try:
            json_str = raw.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            args = json.loads(json_str)
            action = args.get("action", "hold")
            reasoning = args.get("reasoning", "")
        except (json.JSONDecodeError, ValueError):
            action, reasoning = "hold", f"parse error: {raw[:80]}"

        if action not in ACTIONS:
            action = "hold"

        console.act(action, STEP_SECONDS)
        telemetry_after = console.telemetry()

        record = {"step": step, "action": action, "reasoning": reasoning, "telemetry_after": telemetry_after}
        log.append(record)

        if verbose:
            snr_line = telemetry_after.split("\n")[1] if "\n" in telemetry_after else telemetry_after
            print(f"[{step:2d}] {action:<30s}  {reasoning}")
            print(f"      → {snr_line}")

    console.finish()
    return log


def main():
    parser = argparse.ArgumentParser(description="Run Gemma agent on a satellite pass")
    parser.add_argument("--anomaly", default="drift",
                        choices=["drift", "rfi", "polarization", "multipath", "hardware", "none"])
    parser.add_argument("--severity", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if "FIREWORKS_API_KEY" not in os.environ:
        print("Error: FIREWORKS_API_KEY environment variable not set.")
        sys.exit(1)

    episode = _build_episode(
        satellite="NOAA-19",
        anomaly=args.anomaly,
        severity=args.severity,
        onset=150,
        duration=200,
        max_elevation=45.0,
        pass_steps=400,
        init_az_error=0.3,
        init_el_error=0.1,
        init_freq_offset=50.0,
        noise_level=120.0,
        seed=args.seed,
    )
    console = GroundStationConsole(episode)

    print(f"\n=== Gemma Agent  |  model: {args.model} ===")
    print(f"Satellite: {episode.satellite_name}  |  Anomaly: {args.anomaly} (severity={args.severity})")
    print(f"Pass: {episode.pass_duration}s  |  Max elevation: {episode.max_elevation:.0f}°\n")

    log = run_episode(console, model=args.model, verbose=not args.quiet)

    breakdown = console.score_breakdown()
    print(f"\n=== Results ===")
    print(f"Score:          {breakdown['score']:.3f}")
    print(f"Lock fraction:  {breakdown['base_lock_fraction']:.1%}")
    print(f"Efficiency cost:{breakdown['efficiency_cost']:.3f}")
    print(f"Total slew:     {breakdown['total_slew_deg']:.1f}°")
    print(f"Actuator uses:  {breakdown['actuator_uses']}")
    print(f"Decisions made: {len(log)}")

    # Save run to data/runs/
    runs_dir = Path(__file__).parent.parent / "data" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = runs_dir / f"{timestamp}_{args.anomaly}_seed{args.seed}.json"
    out_path.write_text(json.dumps({
        "timestamp": timestamp,
        "model": args.model,
        "anomaly": args.anomaly,
        "severity": args.severity,
        "seed": args.seed,
        "score": breakdown,
        "decisions": log,
    }, indent=2))
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()

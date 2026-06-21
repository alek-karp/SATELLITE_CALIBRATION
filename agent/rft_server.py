"""Fireworks RFT remote rollout server for satellite ground-station environment.

Fireworks calls POST /init with a model URL and initial prompt.
We run a full satellite pass episode, score it, and report the score
back via FireworksTracingHttpHandler so GRPO can use it as a reward.

Deploy publicly (e.g. ngrok, Modal, Railway), upload agent/eval_test.py,
and create the RFT job with --evaluator. There is no --remote-server-url flag;
the evaluator points to this server through EP_REMOTE_ROLLOUT_PROCESSOR_BASE_URL.

Run locally:
    uv run agent/rft_server.py
"""

import asyncio
import json
import logging
import os
import sys

from fastapi import FastAPI
from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eval_protocol import FireworksTracingHttpHandler, InitRequest, RolloutIdFilter, Status

from env import (
    ACTIONS,
    GroundStationConsole,
    STEP_SECONDS,
    _ACTION_REFERENCE,
    _build_episode,
)
from sim import SNR_THRESHOLD

import numpy as np
import uvicorn

# ---------------------------------------------------------------------------
# Logging: route through Fireworks tracing so scores reach the RFT loop
# ---------------------------------------------------------------------------
root_logger = logging.getLogger()
root_logger.handlers.clear()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(logging.StreamHandler(sys.stdout))
root_logger.addHandler(FireworksTracingHttpHandler())

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="satellite-rft-server")

SYSTEM_PROMPT = f"""\
You are an expert satellite ground station operator. A satellite is passing
overhead. Keep the downlink signal alive until the pass ends.

At each step you receive telemetry. Respond with a JSON object only:
  {{"action": "<action_name>", "reasoning": "<one sentence why>"}}

Valid actions:
{_ACTION_REFERENCE}

Strategy:
- Use 'hold' first to get a clean baseline reading.
- Prefer targeted fixes: frequency shift for RFI, nudge for pointing drift.
- Avoid unnecessary antenna movement.
- If time < 60s remaining, snap to ephemeris for fast recovery.
"""

ANOMALY_TYPES = ["drift", "rfi", "polarization", "multipath", "hardware"]


def _random_episode() -> GroundStationConsole:
    rng = np.random
    anomaly = rng.choice(ANOMALY_TYPES)
    episode = _build_episode(
        satellite="NOAA-19",
        anomaly=anomaly,
        severity=float(rng.uniform(0.4, 1.0)),
        onset=int(rng.randint(100, 300)),
        duration=int(rng.randint(80, 200)),
        max_elevation=float(rng.uniform(25.0, 70.0)),
        pass_steps=400,
        init_az_error=float(rng.uniform(0.1, 0.8)),
        init_el_error=float(rng.uniform(0.05, 0.4)),
        init_freq_offset=float(rng.uniform(-200, 200)),
        noise_level=float(rng.uniform(80.0, 200.0)),
        seed=int(rng.randint(0, 100000)),
    )
    return GroundStationConsole(episode)


async def _run_rollout(req: InitRequest, api_key: str) -> None:
    """Run one satellite episode using the model Fireworks provides, report score."""
    logger = logging.getLogger(f"satellite_rft.{req.metadata.rollout_id}")
    logger.addFilter(RolloutIdFilter(req.metadata.rollout_id))

    try:
        model = req.completion_params.get("model", "")
        base_url = req.model_base_url or "https://api.fireworks.ai/inference/v1"
        client = OpenAI(base_url=base_url, api_key=api_key)

        console = _random_episode()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        logger.info(f"Starting episode | model={model} | pass={console.gym._episode.pass_duration}s")

        for step in range(60):
            if console.done:
                break

            telemetry = console.telemetry()
            messages.append({"role": "user", "content": f"Telemetry:\n{telemetry}"})

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=128,
                    temperature=0.7,
                    extra_headers={
                        "x-multi-turn-session-id": req.metadata.rollout_id,
                        "x-session-affinity": req.metadata.rollout_id,
                    },
                )
                raw = response.choices[0].message.content or ""
            except Exception as e:
                logger.warning(f"Model call failed at step {step}: {e}")
                raw = ""

            # Parse JSON action
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
                action, reasoning = "hold", "parse error"

            if action not in ACTIONS:
                action = "hold"

            console.act(action, STEP_SECONDS)
            telemetry_after = console.telemetry()

            logger.info(f"step={step} action={action} | {reasoning}")
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Result:\n{telemetry_after}"})

        console.finish()
        score = console.score()
        breakdown = console.score_breakdown()

        logger.info(
            f"Episode complete | score={score:.3f} | lock={breakdown['base_lock_fraction']:.1%} "
            f"| slew={breakdown['total_slew_deg']:.1f}° | actuator_uses={breakdown['actuator_uses']}",
            extra={"status": Status.rollout_finished(extra_info={"score": score})},
        )

    except Exception as e:
        logger.error(
            f"Rollout failed: {e}",
            extra={"status": Status.rollout_internal_error(str(e))},
        )


@app.post("/init")
async def init(req: InitRequest):
    logger = logging.getLogger(f"satellite_rft.{req.metadata.rollout_id}")
    logger.addFilter(RolloutIdFilter(req.metadata.rollout_id))

    api_key = req.api_key or os.environ.get("FIREWORKS_API_KEY", "")
    if not api_key:
        return {"error": "no API key"}, 401

    asyncio.create_task(_run_rollout(req, api_key))
    return {"status": "accepted", "rollout_id": req.metadata.rollout_id}


@app.get("/health")
def health():
    return {"status": "ok", "env": "satellite-ground-station"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

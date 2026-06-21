"""
Export a recorded episode as playback data for the 3D web visualization.

Runs a deterministic, multi-anomaly episode through the *real* SatelliteEnv
with a telemetry-driven recovery policy, then dumps every step's structured
state to web_agent_scene/playback.json. The browser scene (app.js) replays
that file frame-by-frame instead of running its built-in scripted simulation.

Usage:
    uv run python scripts/export_playback.py
    uv run python scripts/export_playback.py --seed 7 --out web_agent_scene/playback.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))

import numpy as np
from satellite_env import SatelliteEnv, ACTIONS
from anomalies import AnomalyState
from episode_generator import EpisodePlan

PASS_DURATION = 240  # frames — keeps the web replay a comfortable length


def build_episode() -> EpisodePlan:
    """A deterministic pass with the five-anomaly arc the scene narrates."""
    t = np.linspace(0, np.pi, PASS_DURATION)
    el_arc = 54.0 * np.sin(t)
    az_arc = 180.0 + 80.0 * (t / np.pi - 0.5)  # sweeps 140° → 220°

    anomalies = [
        AnomalyState(kind="polarization", onset_time=50, duration=26,
                     severity=0.9, true_polarization=2),
        AnomalyState(kind="drift", onset_time=86, duration=32, severity=0.8,
                     drift_rate_az=0.075, drift_rate_el=-0.045),
        # RFI / hardware magnitudes are tuned so the narrow-bandwidth remedy
        # visibly rescues the link (the env's randomly-sampled RFI can be far
        # harsher); this is a curated showcase pass, like the scene's own demo.
        AnomalyState(kind="rfi", onset_time=126, duration=28, severity=0.9,
                     rfi_power_w=1.0e-14),
        AnomalyState(kind="multipath", onset_time=164, duration=28,
                     severity=0.85, multipath_phase=0.7),
        AnomalyState(kind="hardware", onset_time=196, duration=28,
                     severity=0.75, hardware_noise_delta_k=250.0),
    ]

    return EpisodePlan(
        satellite_name="NOAA-19",
        ephemeris_az=az_arc,
        ephemeris_el=el_arc,
        pass_duration=PASS_DURATION,
        max_elevation=54.0,
        initial_az_error=0.2,
        initial_el_error=0.1,
        initial_freq_offset=50.0,
        noise_level=120.0,
        anomalies=anomalies,
    )


def oracle_action(s, t, episode):
    """Scripted recovery policy for the demo. Like the scene's own built-in
    agent (chooseScriptedAction in app.js), it reads the active anomaly schedule
    and applies the matched remedy through the real env physics:

      drift        → pointing nudges        polarization → match polarization
      rfi/hardware → narrow bandwidth        multipath    → ride it out (hold)

    Pointing is always trimmed (the mount's tracking loop leaks error every step).
    """
    az, el = s["az_error"], s["el_error"]
    pol, bw = s["pol_mode"], s["bandwidth_factor"]
    progress = t / episode.pass_duration
    active = [a for a in episode.anomalies
              if a.onset_time <= t < a.onset_time + a.duration]
    pol_an = next((a for a in active if a.kind == "polarization"), None)
    broadband = any(a.kind in ("rfi", "hardware") for a in active)

    if progress >= 0.82:
        return ACTIONS.index("request_handoff")
    if t == 0:
        return ACTIONS.index("snap_to_ephemeris")

    # Polarization: rotate onto the true mode during the fault, restore after.
    target_pol = pol_an.true_polarization if pol_an else 0
    if pol != target_pol:
        return ACTIONS.index("cycle_polarization")

    # RFI / hardware noise: narrow the receiver to reject broadband noise.
    if broadband and bw > 0.5:
        return ACTIONS.index("narrow_bandwidth")
    if not broadband and bw < 1.0:
        return ACTIONS.index("widen_bandwidth")

    # Pointing: correct the dominant axis (drift + tracking leak).
    axis = "az" if abs(az) >= abs(el) else "el"
    err = az if axis == "az" else el
    mag = abs(err)
    sign = "neg" if err > 0 else "pos"
    if mag > 1.2:
        return ACTIONS.index(f"nudge_{axis}_{sign}_large")
    if mag > 0.35:
        return ACTIONS.index(f"nudge_{axis}_{sign}_medium")
    if mag > 0.12:
        return ACTIONS.index(f"nudge_{axis}_{sign}_small")

    return ACTIONS.index("hold")  # nominal tracking / ride out multipath


def anomalies_for_web(anomalies):
    """Map env AnomalyState objects to the field names app.js expects."""
    out = []
    for a in anomalies:
        entry = {"kind": a.kind, "onset": a.onset_time, "duration": a.duration,
                 "severity": a.severity}
        if a.kind == "drift":
            entry["azRate"] = a.drift_rate_az
            entry["elRate"] = a.drift_rate_el
        elif a.kind == "polarization":
            entry["truePolarization"] = a.true_polarization
        elif a.kind == "multipath":
            entry["phase"] = a.multipath_phase
        out.append(entry)
    return out


def run(seed: int):
    np.random.seed(seed)
    episode = build_episode()

    env = SatelliteEnv(difficulty="medium")
    env.reset()
    env._episode = episode
    env._t = 0
    env._snr_history = []
    env._total_reward = 0.0
    env._state = {
        "az_error": episode.initial_az_error,
        "el_error": episode.initial_el_error,
        "freq_offset": episode.initial_freq_offset,
        "pol_mode": 0,
        "true_polarization": 0,
        "base_true_polarization": 0,
        "interference_power": 0.0,
        "noise_temp": episode.noise_level,
        "atmospheric_loss_db": 0.5,
        "bandwidth_factor": 1.0,
        "slew_rate": 0.0,
        "locked": True,
    }
    frames = []
    done = False
    while not done:
        action = oracle_action(env._state, env._t, episode)
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        s = env._state
        frames.append({
            "t": info["timestep"] - 1,
            "action": ACTIONS[action],
            "azError": round(float(info["az_error"]), 4),
            "elError": round(float(info["el_error"]), 4),
            "freqOffset": round(float(info["freq_offset"]), 1),
            "polMode": int(info["pol_mode"]),
            "bandwidthFactor": round(float(s["bandwidth_factor"]), 4),
            "noiseTemp": round(float(s["noise_temp"]), 1),
            "snr": round(float(info["snr_db"]), 2),
            "locked": bool(info["locked"]),
            "reward": round(float(reward), 4),
            "totalReward": round(float(info["total_reward"]), 3),
        })

    score = frames[-1]["totalReward"] if frames else 0.0
    locked_pct = 100 * sum(f["locked"] for f in frames) / len(frames)
    above_pct = 100 * sum(f["snr"] > 10 for f in frames) / len(frames)

    payload = {
        "meta": {
            "satellite": episode.satellite_name,
            "seed": seed,
            "passDuration": len(frames),
            "maxElevation": episode.max_elevation,
            "score": round(float(score), 3),
            "anomalies": anomalies_for_web(episode.anomalies),
        },
        "frames": frames,
    }
    return payload, locked_pct, above_pct


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--out",
        default=os.path.join(ROOT, "web_agent_scene", "playback.json"),
    )
    args = parser.parse_args()

    payload, locked_pct, above_pct = run(args.seed)
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    m = payload["meta"]
    print(f"Exported {len(payload['frames'])} frames → {args.out}")
    print(f"  Satellite:       {m['satellite']}  (seed {m['seed']})")
    print(f"  Final score:     {m['score']}")
    print(f"  Signal locked:   {locked_pct:.0f}%")
    print(f"  SNR > threshold: {above_pct:.0f}%")
    print(f"  Anomalies:       {', '.join(a['kind'] for a in m['anomalies'])}")
    print("\nOpen web_agent_scene/index.html (or serve it) to watch the replay.")


if __name__ == "__main__":
    main()

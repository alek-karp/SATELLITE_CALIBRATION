"""Demo: context-blind baseline vs context-aware agent on the same pass.

Runs scripted policies through the real ``GroundStationConsole`` (the same
interface the LLM agent drives via tools) on a single deterministic episode,
then plots the SNR / pointing / reward arcs and prints the headline
"% of pass above threshold" for each policy.

The story (see WHY_AGENT.md): the link degrades mid-pass from a slow pointing
drift. The two operators see the *same* SNR dip but reach different conclusions.
The context-blind baseline misdiagnoses it as interference and chases frequency —
which, in this link model, does nothing — so it never re-centers the beam and the
drift carries the signal off the dish. The context-aware operator correctly reads
it as pointing drift and nudges the beam back. Same physics, same automatic
reward; the only difference is reaching the right diagnosis.

Run:  uv run python demo_baseline_vs_agent.py
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from env import ACTIONS, SNR_THRESHOLD, GroundStationConsole, _build_episode

# --- scenario: a slow pointing drift injected mid-pass ------------------------
SCENARIO = dict(
    satellite="NOAA-19 (sim)",
    anomaly="drift",
    severity=0.9,
    onset=180,
    duration=320,
    max_elevation=60.0,
    pass_steps=600,
    init_az_error=0.3,
    init_el_error=0.1,
    init_freq_offset=50.0,
    noise_level=120.0,
    seed=7,
)


def _telemetry(c: GroundStationConsole) -> dict:
    g, s = c.gym, c.gym._state
    snr = g._snr_history[-1] if g._snr_history else 20.0
    prev = g._snr_history[-2] if len(g._snr_history) > 1 else snr
    return {
        "snr": snr,
        "trend": snr - prev,
        "locked": s["locked"],
        "az_err": s["az_error"],
        "el_err": s["el_error"],
        "freq": s["freq_offset"],
    }


# --- policies (each returns an action name given current telemetry) -----------
def policy_idle(_t: dict) -> str:
    return "hold"


def _fix_pointing(t: dict) -> str | None:
    """Shared pointing correction: nudge the larger axis error back toward zero.

    In this sim ``nudge_*_pos`` *decreases* the corresponding error, so a positive
    error is corrected with ``pos`` and a negative error with ``neg``.
    """
    if abs(t["az_err"]) > abs(t["el_err"]) and abs(t["az_err"]) > 0.15:
        return "nudge_az_pos_medium" if t["az_err"] > 0 else "nudge_az_neg_medium"
    if abs(t["el_err"]) > 0.15:
        return "nudge_el_pos_medium" if t["el_err"] > 0 else "nudge_el_neg_medium"
    if abs(t["az_err"]) > 0.05:
        return "nudge_az_pos_small" if t["az_err"] > 0 else "nudge_az_neg_small"
    return None


def policy_context_blind(t: dict) -> str:
    """Misdiagnoses the SNR dip as interference and chases frequency.

    Never re-centers the beam, so the injected pointing drift goes uncorrected.
    """
    if t["trend"] < -0.3 or t["snr"] < SNR_THRESHOLD:
        return "shift_freq_pos_coarse" if t["freq"] <= 0 else "shift_freq_neg_coarse"
    return "hold"


def policy_context_aware(t: dict) -> str:
    """Correctly reads the dip as pointing drift and nudges the beam back."""
    fix = _fix_pointing(t)
    if fix is not None:
        return fix
    return "hold"


def run(policy, label):
    c = GroundStationConsole(_build_episode(**SCENARIO))
    log = {"snr": [], "az": [], "el": [], "reward": [], "locked": []}
    while not c.done:
        action = policy(_telemetry(c))
        c.act(action, duration=1)
        st = c.gym._state
        log["snr"].append(c.gym._snr_history[-1])
        log["az"].append(st["az_error"])
        log["el"].append(st["el_error"])
        log["reward"].append(c.gym._total_reward)
        log["locked"].append(st["locked"])
    n = len(log["snr"])
    above = 100 * sum(s > SNR_THRESHOLD for s in log["snr"]) / n
    locked = 100 * sum(log["locked"]) / n
    print(
        f"{label:24s}  above-threshold: {above:5.1f}%   locked: {locked:5.1f}%   "
        f"reward: {log['reward'][-1]:+.0f}"
    )
    return log, above


def main():
    print(f"Scenario: {SCENARIO['satellite']}  pointing drift @ t={SCENARIO['onset']}s "
          f"(through t={SCENARIO['onset'] + SCENARIO['duration']}s)\n")

    blind, blind_pct = run(policy_context_blind, "Context-blind baseline")
    aware, aware_pct = run(policy_context_aware, "Context-aware agent")
    run(policy_idle, "Idle (reference)")  # printed for reference, not plotted

    onset, end = SCENARIO["onset"], SCENARIO["onset"] + SCENARIO["duration"]
    steps = range(len(aware["snr"]))

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    fig.suptitle(
        f"Ground-station calibration — context-blind vs context-aware\n"
        f"Signal above threshold:  baseline {blind_pct:.0f}%  →  agent {aware_pct:.0f}%",
        fontsize=13, fontweight="bold",
    )

    ax = axes[0]
    ax.plot(steps, aware["snr"], color="#2ecc71", lw=1.4, label="Context-aware agent")
    ax.plot(steps, blind["snr"], color="#e74c3c", lw=1.2, label="Context-blind baseline")
    ax.axhline(SNR_THRESHOLD, color="orange", ls="--", lw=1, label=f"Threshold ({SNR_THRESHOLD:.0f} dB)")
    ax.axvspan(onset, end, color="purple", alpha=0.08, label="Pointing drift active")
    ax.set_ylabel("SNR (dB)")
    ax.set_ylim(-40, 70)
    ax.legend(fontsize=8, loc="upper right", ncol=2)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(steps, np.abs(aware["az"]), color="#2ecc71", lw=1.4, label="|az error| agent")
    ax.plot(steps, np.abs(blind["az"]), color="#e74c3c", lw=1.2, label="|az error| baseline")
    ax.axhline(1.5, color="orange", ls="--", lw=0.8, alpha=0.6, label="Beamwidth edge")
    ax.axvspan(onset, end, color="purple", alpha=0.08)
    ax.set_ylabel("Pointing error (°)")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.plot(steps, aware["reward"], color="#2ecc71", lw=1.4, label="Context-aware agent")
    ax.plot(steps, blind["reward"], color="#e74c3c", lw=1.2, label="Context-blind baseline")
    ax.axvspan(onset, end, color="purple", alpha=0.08)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_ylabel("Cumulative reward")
    ax.set_xlabel("Timestep (s)")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = os.path.join(os.path.dirname(__file__), "demo_baseline_vs_agent.png")
    plt.savefig(out, dpi=140, bbox_inches="tight")
    print(f"\nPlot saved -> {out}")


if __name__ == "__main__":
    main()

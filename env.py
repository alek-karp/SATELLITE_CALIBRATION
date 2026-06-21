"""HUD v6 environment — autonomous satellite ground-station operation.

This wraps the Gymnasium satellite simulation in ``sim/`` as a HUD v6
environment, following the structure of the ``hud-blank`` template:

  * an in-process MCP **capability** (``ground_station``) exposes the agent-facing
    console tools — ``get_telemetry``, ``take_action``, ``request_context`` —
    served by a FastMCP server started in ``@env.initialize``.
  * ``@env.template`` tasks ("hold-the-link") boot a deterministic satellite pass,
    yield the mission prompt, let the agent drive the console through its tools,
    then yield a reward equal to the fraction of the pass kept above the usable
    SNR threshold ("% pass with signal locked").

The reward is fully automatic and physics-derived: the agent cannot fake signal —
if it mispoints, mistunes, or chases the wrong anomaly, the link budget shows it.
"""

import asyncio
import contextlib
import socket
import textwrap

import numpy as np

from hud import Environment
from hud.capabilities import Capability

from sim import (
    ACTIONS,
    SNR_THRESHOLD,
    AnomalyState,
    EpisodePlan,
    SatelliteEnv,
)

env = Environment(name="satellite-calibration")

# --- console tuning ---------------------------------------------------------
STEP_SECONDS = 15          # sim seconds advanced per take_action (action + hold)
CONTEXT_COST = 5           # sim seconds spent fetching an operational-context report
HOLD_IDX = ACTIONS.index("hold")
POL_NAMES = ["H", "V", "RHCP", "LHCP"]

# --- efficiency scoring -----------------------------------------------------
# The base score is "fraction of the pass above the usable SNR threshold". On
# top of that we charge for *how* the link was held: needless antenna slew and
# receiver thrash. Both are expressed as a fraction of the [0, 1] score, scaled
# by usage-per-pass-second so pass length doesn't change the calibration.
SLEW_COST_WEIGHT = 0.25     # score lost per (degree slewed / pass second)
ACTUATOR_COST_WEIGHT = 0.15  # score lost per (freq/pol/bw change / pass second)
EFFICIENCY_COST_CAP = 0.20   # efficiency never removes more than this much score

# --- contextual penalties ---------------------------------------------------
# Deterministic checks run against the agent's action log and the episode's
# `rules` spec (see WHY_AGENT.md). The natural-language context tells the agent
# what is correct; these rules verify it acted on it. Values are score
# fractions (subtracted from the [0, 1] reward). A task opts in by passing the
# matching key in its `rules` dict; the magnitude is the value.
CONTEXT_RULES = {
    "no_freq_hop": "freq_hop_against_advisory",      # advisory: RFI self-clears, ride it
    "no_large_slew": "large_slew_on_sticky_servo",   # operator log: servo sticks, small nudges only
    "no_handoff": "handoff_when_unavailable",         # coordination: no station can take handoff
    "continuous_lock": "lock_dropped_on_high_priority",  # mission brief: continuous lock or nothing
}


# ===========================================================================
# Ground-station console: drives the Gymnasium sim, tracks lock statistics
# ===========================================================================
class GroundStationConsole:
    """A live satellite pass the agent operates through the MCP tools.

    Wraps ``SatelliteEnv`` with a coarse time step (the agent decides every
    ``STEP_SECONDS`` of sim time, holding its last action in between) and tracks
    how much of the pass stayed above the usable SNR threshold.
    """

    def __init__(
        self,
        episode: EpisodePlan,
        context: dict | None = None,
        rules: dict | None = None,
    ):
        self.gym = SatelliteEnv()
        self.gym._episode = episode
        self.gym._t = 0
        self.gym._snr_history = []
        self.gym._total_reward = 0.0
        self.gym._state = {
            "az_error": episode.initial_az_error,
            "el_error": episode.initial_el_error,
            "freq_offset": episode.initial_freq_offset,
            "pol_mode": 0,
            "true_polarization": 0,
            "interference_power": 0.0,
            "noise_temp": episode.noise_level,
            "atmospheric_loss_db": 0.5,
            "bandwidth_factor": 1.0,
            "slew_rate": 0.0,
            "locked": True,
        }
        self.context = context or {}
        self.rules = rules or {}
        self.done = False
        self.steps_taken = 0
        self.steps_above = 0
        self.steps_locked = 0
        # Efficiency + contextual-penalty bookkeeping.
        self.total_slew = 0.0          # cumulative degrees of antenna movement
        self.actuator_uses = 0         # freq / pol / bandwidth changes
        self.handoff_requested = False
        self.decisions: list[str] = []  # decision actions (excludes auto-holds)

    def _step(self, action_idx: int) -> None:
        if self.done:
            return
        _, _, terminated, truncated, info = self.gym.step(action_idx)
        self.steps_taken += 1
        # `slew_rate` is set by the gym for whatever action just ran (0 on holds).
        self.total_slew += abs(self.gym._state.get("slew_rate", 0.0))
        # Score off the clean physics SNR, not the noisy observed value, so the
        # reward is deterministic for a given seed.
        if info["snr_db_true"] > SNR_THRESHOLD:
            self.steps_above += 1
        if info["locked"]:
            self.steps_locked += 1
        if terminated or truncated:
            self.done = True

    def act(self, action_name: str, duration: int = STEP_SECONDS) -> None:
        """Apply one action, then hold for the rest of the time chunk."""
        self.decisions.append(action_name)
        if action_name.startswith(("shift_freq", "cycle_polarization")) or \
                action_name in ("narrow_bandwidth", "widen_bandwidth"):
            self.actuator_uses += 1
        if action_name == "request_handoff":
            self.handoff_requested = True
        self._step(ACTIONS.index(action_name))
        for _ in range(max(0, duration - 1)):
            if self.done:
                break
            self._step(HOLD_IDX)

    def finish(self) -> None:
        """Fly out the remainder of the pass holding the current configuration."""
        guard = 0
        while not self.done and guard < self.gym._episode.pass_duration + 1:
            self._step(HOLD_IDX)
            guard += 1

    def efficiency_cost(self) -> float:
        """Score lost to needless antenna slew and receiver thrash (capped)."""
        total = self.gym._episode.pass_duration
        if not total:
            return 0.0
        slew = SLEW_COST_WEIGHT * (self.total_slew / total)
        thrash = ACTUATOR_COST_WEIGHT * (self.actuator_uses / total)
        return min(EFFICIENCY_COST_CAP, slew + thrash)

    def contextual_penalty(self) -> tuple[float, dict[str, float]]:
        """Deterministic penalties for ignoring operational context.

        Checked against the episode's ``rules`` spec and the agent's action log.
        Returns the total penalty and a per-violation breakdown.
        """
        breakdown: dict[str, float] = {}
        acts = self.decisions

        def fire(key: str, triggered: bool) -> None:
            mag = self.rules.get(key)
            if mag and triggered:
                breakdown[CONTEXT_RULES[key]] = float(mag)

        fire("no_freq_hop", any(a.startswith("shift_freq") for a in acts))
        fire(
            "no_large_slew",
            any(a.endswith("_large") or a == "snap_to_ephemeris" for a in acts),
        )
        fire("no_handoff", self.handoff_requested)
        fire("continuous_lock", self.steps_locked < self.steps_taken)
        return sum(breakdown.values()), breakdown

    def score(self) -> float:
        """Composite reward in [0, 1].

        Base = fraction of the pass kept above the usable SNR threshold, minus
        slew/actuator efficiency cost, minus deterministic contextual penalties
        for ignoring the operational brief (see WHY_AGENT.md). Clamped to [0, 1].
        """
        total = self.gym._episode.pass_duration
        base = self.steps_above / total if total else 0.0
        penalty, _ = self.contextual_penalty()
        return float(max(0.0, min(1.0, base - self.efficiency_cost() - penalty)))

    def score_breakdown(self) -> dict:
        """Per-term score breakdown for demos / debugging."""
        total = self.gym._episode.pass_duration
        base = self.steps_above / total if total else 0.0
        penalty, violations = self.contextual_penalty()
        return {
            "base_lock_fraction": round(base, 4),
            "efficiency_cost": round(self.efficiency_cost(), 4),
            "contextual_penalty": round(penalty, 4),
            "violations": violations,
            "total_slew_deg": round(self.total_slew, 2),
            "actuator_uses": self.actuator_uses,
            "score": round(self.score(), 4),
        }

    def telemetry(self) -> str:
        g, s, ep = self.gym, self.gym._state, self.gym._episode
        snr = g._snr_history[-1] if g._snr_history else 20.0
        snr_prev = g._snr_history[-2] if len(g._snr_history) > 1 else snr
        remaining = max(0, ep.pass_duration - g._t)
        lines = [
            f"t = {g._t}/{ep.pass_duration} s   (time remaining: {remaining} s)",
            f"SNR: {snr:.1f} dB   trend: {snr - snr_prev:+.1f} dB   "
            f"link: {'LOCKED' if s['locked'] else 'UNLOCKED'}",
            f"pointing error vs ephemeris: az {s['az_error']:+.2f}°  el {s['el_error']:+.2f}°",
            f"freq offset: {s['freq_offset']:+.0f} Hz   "
            f"polarization: {POL_NAMES[s['pol_mode']]}",
            f"noise temp: {s['noise_temp']:.0f} K   bandwidth: x{s['bandwidth_factor']:.2f}",
        ]
        if self.done:
            lines.append("PASS COMPLETE — further actions have no effect.")
        return "\n".join(lines)


# ===========================================================================
# Deterministic episode construction
# ===========================================================================
def _make_anomaly(
    kind: str, onset: int, duration: int, severity: float, rng: np.random.RandomState
) -> AnomalyState:
    a = AnomalyState(kind=kind, onset_time=onset, duration=duration, severity=severity)
    if kind == "drift":
        a.drift_rate_az = severity * 0.05 * rng.choice([-1, 1])
        a.drift_rate_el = severity * 0.03 * rng.choice([-1, 1])
    elif kind == "rfi":
        a.rfi_power_w = severity * 1e-10
    elif kind == "polarization":
        a.true_polarization = int(rng.choice([1, 2, 3]))
    elif kind == "multipath":
        a.multipath_phase = float(rng.uniform(0, 2 * np.pi))
    elif kind == "hardware":
        a.hardware_noise_delta_k = severity * 500.0
    return a


def _build_episode(
    *,
    satellite: str,
    anomaly: str,
    severity: float,
    onset: int,
    duration: int,
    max_elevation: float,
    pass_steps: int,
    init_az_error: float,
    init_el_error: float,
    init_freq_offset: float,
    noise_level: float,
    seed: int,
) -> EpisodePlan:
    """Build a reproducible synthetic pass with at most one anomaly."""
    rng = np.random.RandomState(seed)
    t = np.linspace(0, np.pi, pass_steps)
    el_arc = (max_elevation * np.sin(t)).astype(float)
    az_arc = ((180.0 + 80.0 * (t / np.pi - 0.5)) % 360).astype(float)

    anomalies: list[AnomalyState] = []
    if anomaly and anomaly.lower() != "none":
        anomalies.append(_make_anomaly(anomaly.lower(), onset, duration, severity, rng))

    return EpisodePlan(
        satellite_name=satellite,
        ephemeris_az=az_arc,
        ephemeris_el=el_arc,
        pass_duration=pass_steps,
        max_elevation=float(max_elevation),
        initial_az_error=float(init_az_error),
        initial_el_error=float(init_el_error),
        initial_freq_offset=float(init_freq_offset),
        noise_level=float(noise_level),
        anomalies=anomalies,
    )


# ===========================================================================
# Agent-facing tools (registered on the in-process MCP server)
# ===========================================================================
# HUD runs one container per evaluation, so a single module-global console is
# safe (no in-process parallelism between tasks).
_console: GroundStationConsole | None = None


async def get_telemetry() -> str:
    """Read the current ground-station telemetry without acting."""
    if _console is None:
        return "No active pass."
    return _console.telemetry()


async def take_action(action: str, duration: int = STEP_SECONDS) -> str:
    """Command the antenna/receiver, then hold for the rest of the time chunk.

    ``action`` is one of the station's control actions; ``duration`` is the
    number of sim seconds this decision spans (the action is applied once, then
    the configuration is held). Returns the resulting telemetry.
    """
    if _console is None:
        return "No active pass."
    if _console.done:
        return "Pass already complete.\n" + _console.telemetry()
    if action not in ACTIONS:
        return f"Unknown action '{action}'. Valid actions: {', '.join(ACTIONS)}"
    _console.act(action, duration)
    return _console.telemetry()


async def request_context(source: str) -> str:
    """Request an operational-context report (mission brief, operator log, etc.).

    Costs sim time. Sources are episode-specific; query with no match to see the
    available list.
    """
    if _console is None:
        return "No active pass."
    report = _console.context.get(source)
    if report is None:
        available = ", ".join(_console.context) or "none configured for this pass"
        return f"No report from '{source}'. Available sources: {available}"
    if not _console.done:
        _console.act("hold", duration=CONTEXT_COST)
    return report


# ===========================================================================
# In-process MCP capability: serve the console tools to the agent
# ===========================================================================
_MCP_PORT: int = 0
_MCP_SERVER_TASK: "asyncio.Task | None" = None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _listening(host: str, port: int, timeout: float = 10.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            socket.create_connection((host, port), timeout=0.2).close()
            return
        except OSError:
            await asyncio.sleep(0.1)
    raise RuntimeError(f"ground_station MCP server never came up on {host}:{port}")


@env.initialize
async def _up() -> None:
    from fastmcp import FastMCP

    global _MCP_PORT, _MCP_SERVER_TASK
    if _MCP_SERVER_TASK is None:
        server = FastMCP(name="ground_station")
        server.tool(get_telemetry)
        server.tool(take_action)
        server.tool(request_context)
        _MCP_PORT = _free_port()
        _MCP_SERVER_TASK = asyncio.create_task(
            server.run_async(
                transport="http", host="127.0.0.1", port=_MCP_PORT, show_banner=False
            )
        )
        await _listening("127.0.0.1", _MCP_PORT)
    env.add_capability(
        Capability.mcp(name="ground_station", url=f"http://127.0.0.1:{_MCP_PORT}/mcp")
    )


@env.shutdown
async def _down() -> None:
    global _MCP_SERVER_TASK, _console
    if _MCP_SERVER_TASK is not None:
        _MCP_SERVER_TASK.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _MCP_SERVER_TASK
        _MCP_SERVER_TASK = None
    _console = None


# ===========================================================================
# Prompt
# ===========================================================================
_ACTION_REFERENCE = textwrap.dedent(
    """\
    Pointing (correct drift / re-center the beam):
      nudge_az_pos_small/neg_small (±0.1°), _pos_medium/_neg_medium (±0.5°), _pos_large/_neg_large (±2.0°)
      nudge_el_pos_small/neg_small (±0.1°), _pos_medium/_neg_medium (±0.5°), _pos_large/_neg_large (±2.0°)
      snap_to_ephemeris (reset pointing, large slew cost)
    Receiver (RFI / Doppler / polarization / hardware):
      shift_freq_pos_fine/neg_fine (±10 Hz), _pos_med/_neg_med (±100 Hz), _pos_coarse/_neg_coarse (±1 kHz)
      cycle_polarization (H→V→RHCP→LHCP), narrow_bandwidth, widen_bandwidth
    Meta:
      hold (measure cleanly, no movement), request_handoff (last 20% of pass only)"""
)


def _build_prompt(console: GroundStationConsole, target_lock_pct: float) -> str:
    ep = console.gym._episode
    context_note = (
        f"\nOperational context is available — call request_context(source) "
        f"(sources: {', '.join(console.context)}). Each report costs ~{CONTEXT_COST}s.\n"
        if console.context
        else ""
    )
    return textwrap.dedent(
        f"""\
        You are the operator of a satellite ground station. A satellite is passing
        overhead and you must keep the downlink alive until the pass window closes.

        Satellite: {ep.satellite_name}
        Pass length: {ep.pass_duration} s   |   Max elevation: {ep.max_elevation:.0f}°
        Usable signal threshold: {SNR_THRESHOLD:.0f} dB SNR

        Something may degrade the link mid-pass (pointing drift, RF interference,
        polarization rotation, multipath fading, or a hardware fault). Diagnose it
        from the telemetry and correct it — without thrashing the antenna.

        Tools:
          get_telemetry()                  read current telemetry
          take_action(action, duration)    apply an action, then hold; duration is
                                           sim seconds (default {STEP_SECONDS})
          request_context(source)          fetch an operational report (costs time)
        {context_note}
        Available actions:
        {_ACTION_REFERENCE}

        Goal: keep SNR above {SNR_THRESHOLD:.0f} dB for as much of the pass as
        possible (target ≥ {target_lock_pct:.0%}). When you have nothing left to
        correct, you may stop; the pass flies out holding your last configuration.

        Current telemetry:
        {console.telemetry()}
        """
    )


# ===========================================================================
# Tasks
# ===========================================================================
@env.template(id="hold-the-link")
async def hold_the_link(
    satellite: str = "SYNTHETIC-LEO-1",
    anomaly: str = "drift",
    severity: float = 0.8,
    onset: int = 200,
    duration: int = 200,
    max_elevation: float = 60.0,
    pass_steps: int = 600,
    init_az_error: float = 0.3,
    init_el_error: float = 0.1,
    init_freq_offset: float = 50.0,
    noise_level: float = 120.0,
    seed: int = 0,
    target_lock_pct: float = 0.85,
    context: dict | None = None,
    rules: dict | None = None,
):
    """Operate a satellite pass through an injected anomaly.

    Reward (0.0–1.0): fraction of the pass kept above the usable SNR threshold,
    minus slew/actuator efficiency cost, minus deterministic contextual
    penalties (``rules``) for ignoring the operational brief. See WHY_AGENT.md.
    """
    global _console
    episode = _build_episode(
        satellite=satellite,
        anomaly=anomaly,
        severity=severity,
        onset=onset,
        duration=duration,
        max_elevation=max_elevation,
        pass_steps=pass_steps,
        init_az_error=init_az_error,
        init_el_error=init_el_error,
        init_freq_offset=init_freq_offset,
        noise_level=noise_level,
        seed=seed,
    )
    _console = GroundStationConsole(episode, context, rules)
    yield _build_prompt(_console, target_lock_pct)
    _console.finish()
    yield _console.score()


if __name__ == "__main__":
    # No-model smoke: boot a short pass, drive a few corrections, print the reward.
    async def _smoke() -> None:
        global _console
        gen = hold_the_link.func(
            anomaly="drift", pass_steps=120, onset=30, duration=60, seed=1
        )
        prompt = await gen.asend(None)
        print(prompt)
        print("\n--- driving heuristic corrections ---")
        for _ in range(10):
            print(await take_action("nudge_az_neg_small", 10))
        try:
            reward = await gen.asend("done")
        except StopAsyncIteration as stop:
            reward = stop.value
        print(f"\nreward (composite): {reward}")
        print(f"breakdown: {_console.score_breakdown()}")

    asyncio.run(_smoke())

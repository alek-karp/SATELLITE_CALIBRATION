"""Offline tests for the satellite-calibration HUD env.

No model, gateway, or live keys are touched. Covers the deterministic episode
builder, the console scoring, the tool surface, the task template, and the
served MCP capability.
"""

# pyright: reportPrivateUsage=false

import env as envmod
from env import (
    GroundStationConsole,
    _build_episode,
    env,
    get_telemetry,
    hold_the_link,
    request_context,
    take_action,
)


def _episode(**overrides):
    base = dict(
        satellite="TEST-SAT",
        anomaly="drift",
        severity=0.8,
        onset=20,
        duration=40,
        max_elevation=60.0,
        pass_steps=80,
        init_az_error=0.3,
        init_el_error=0.1,
        init_freq_offset=50.0,
        noise_level=120.0,
        seed=0,
    )
    base.update(overrides)
    return _build_episode(**base)


class TestEpisodeBuilder:
    def test_shapes_and_determinism(self):
        ep1 = _episode(seed=7)
        ep2 = _episode(seed=7)
        assert len(ep1.ephemeris_az) == 80
        assert len(ep1.ephemeris_el) == 80
        assert ep1.anomalies[0].kind == "drift"
        # Same seed → identical anomaly parameters.
        assert ep1.anomalies[0].drift_rate_az == ep2.anomalies[0].drift_rate_az

    def test_no_anomaly(self):
        ep = _episode(anomaly="none")
        assert ep.anomalies == []


class TestConsole:
    def test_score_in_unit_range(self):
        c = GroundStationConsole(_episode(pass_steps=60))
        c.finish()
        assert c.done
        assert 0.0 <= c.score() <= 1.0
        assert c.steps_taken == 60

    def test_tracked_clean_beats_uncorrected_drift(self):
        # The tracking leak means even a clean pass drifts off-beam if held
        # passively, so the agent must actively track. An actively-tracked
        # clean pass must still beat a strong drift left uncorrected.
        clean = GroundStationConsole(_episode(anomaly="none", noise_level=60.0))
        for _ in range(8):
            clean.act("snap_to_ephemeris", duration=10)
        clean.finish()
        drift = GroundStationConsole(
            _episode(anomaly="drift", severity=1.0, onset=10, duration=70, seed=3)
        )
        drift.finish()
        assert clean.score() > drift.score()

    def test_score_is_deterministic(self):
        a = GroundStationConsole(_episode(seed=5))
        a.finish()
        b = GroundStationConsole(_episode(seed=5))
        b.finish()
        assert a.score() == b.score()


class TestTools:
    async def test_take_action_unknown(self):
        gen = hold_the_link.func(anomaly="none", pass_steps=40, seed=0)
        await gen.asend(None)
        msg = await take_action("frobnicate")
        assert "Unknown action" in msg
        await gen.asend("done")

    async def test_take_action_advances_time(self):
        gen = hold_the_link.func(anomaly="drift", pass_steps=80, seed=1)
        await gen.asend(None)
        before = envmod._console.steps_taken
        await take_action("hold", duration=10)
        assert envmod._console.steps_taken == before + 10
        await gen.asend("done")

    async def test_request_context_returns_report_and_costs_time(self):
        gen = hold_the_link.func(
            anomaly="rfi",
            pass_steps=80,
            seed=2,
            context={"spectrum": "RFI self-clears, ride it out."},
        )
        await gen.asend(None)
        before = envmod._console.steps_taken
        report = await request_context("spectrum")
        assert "self-clears" in report
        assert envmod._console.steps_taken == before + envmod.CONTEXT_COST
        # Unknown source lists what's available and costs nothing.
        no_cost_before = envmod._console.steps_taken
        miss = await request_context("nope")
        assert "Available sources" in miss
        assert envmod._console.steps_taken == no_cost_before
        await gen.asend("done")

    async def test_get_telemetry(self):
        gen = hold_the_link.func(anomaly="none", pass_steps=40, seed=0)
        await gen.asend(None)
        tel = await get_telemetry()
        assert "SNR" in tel and "t =" in tel
        await gen.asend("done")


class TestTemplate:
    async def test_yields_prompt_then_reward(self):
        gen = hold_the_link.func(anomaly="drift", pass_steps=80, seed=1)
        prompt = await gen.asend(None)
        assert "ground station" in prompt.lower()
        reward = await gen.asend("done")
        assert isinstance(reward, float)
        assert 0.0 <= reward <= 1.0

    async def test_correcting_helps_vs_doing_nothing(self):
        # Doing nothing on a strong drift pass.
        gen_idle = hold_the_link.func(
            anomaly="drift", severity=1.0, onset=10, duration=70, pass_steps=90, seed=8
        )
        await gen_idle.asend(None)
        idle_reward = await gen_idle.asend("done")

        # Snapping back to ephemeris repeatedly counters pointing drift.
        gen_fix = hold_the_link.func(
            anomaly="drift", severity=1.0, onset=10, duration=70, pass_steps=90, seed=8
        )
        await gen_fix.asend(None)
        for _ in range(9):
            await take_action("snap_to_ephemeris", duration=10)
        fix_reward = await gen_fix.asend("done")

        assert fix_reward >= idle_reward


class TestServedCapability:
    async def test_ground_station_capability_serves_tools(self):
        from hud.capabilities.mcp import MCPClient

        await env.start()
        try:
            cap = env.capability("ground_station")
            assert cap.protocol.startswith("mcp")
            client = await MCPClient.connect(cap)
            try:
                names = {t.name for t in await client.list_tools()}
                assert {"get_telemetry", "take_action", "request_context"}.issubset(names)
            finally:
                await client.close()
        finally:
            await env.stop()

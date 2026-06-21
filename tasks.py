"""Sample tasks for the satellite-calibration environment.

Run locally:   hud eval tasks.py claude --task-ids drift-medium --group 3
Sync remote:   hud sync tasks satellite-calibration

Calling the ``hold_the_link`` template mints a runnable Task; we set a readable
``.slug`` on each. The vars are underscore-prefixed so ``hud eval`` discovers
each task once (via the ``tasks`` list), not twice.
"""

# env is re-exported so `hud eval tasks.py` can resolve the Environment.
from env import env, hold_the_link  # noqa: F401

# -- one task per anomaly type (medium difficulty) -----------------------------
_drift = hold_the_link(anomaly="drift", severity=0.8, onset=200, duration=220, seed=1)
_drift.slug = "drift-medium"

_rfi = hold_the_link(anomaly="rfi", severity=0.8, onset=180, duration=120, seed=2)
_rfi.slug = "rfi-medium"

# Polarization shift persists to pass end (duration covers onset→600): the agent
# cycles H→V once to re-acquire, and that fix stays correct — a transient shift
# would punish the fix when it reverted. See env._make_anomaly.
_polarization = hold_the_link(
    anomaly="polarization", severity=0.9, onset=160, duration=440, seed=3
)
_polarization.slug = "polarization-medium"

_multipath = hold_the_link(
    anomaly="multipath", severity=0.7, onset=220, duration=140, seed=4
)
_multipath.slug = "multipath-medium"

_hardware = hold_the_link(
    anomaly="hardware", severity=0.6, onset=200, duration=160, seed=5
)
_hardware.slug = "hardware-medium"

# -- curriculum: clean pass (no anomaly) → easy → hard -------------------------
_clean = hold_the_link(
    anomaly="none", init_az_error=0.1, init_el_error=0.05, noise_level=60.0, seed=10
)
_clean.slug = "clean-pass"

_drift_easy = hold_the_link(
    anomaly="drift", severity=0.4, onset=250, duration=150, noise_level=60.0, seed=11
)
_drift_easy.slug = "drift-easy"

# Hard but solvable: do-nothing scores ~0.0, a skilled tracker ~0.42. The earlier
# noise_level=320/max_el=28 combo kept SNR under threshold for every policy (an
# unwinnable "link too weak" pass, not a hard-drift pass), so it taught nothing.
_drift_hard = hold_the_link(
    anomaly="drift",
    severity=1.0,
    onset=120,
    duration=300,
    init_az_error=1.5,
    init_el_error=0.8,
    noise_level=180.0,
    max_elevation=40.0,
    seed=12,
)
_drift_hard.slug = "drift-hard"

# -- operational-context twist: advisory says the RFI self-clears, don't chase -
# The natural-language `context` tells the agent what is correct; the `rules`
# spec is the deterministic grader that verifies it acted on it (WHY_AGENT.md).
_rfi_advisory = hold_the_link(
    anomaly="rfi",
    severity=0.8,
    onset=180,
    duration=120,
    seed=20,
    # RFI costs ~120 locked-out steps; a skilled narrow-the-band recovery tops
    # out near 0.63, so 0.6 is an aspirational-but-reachable target (0.9 was not).
    target_lock_pct=0.6,
    context={
        "mission_brief": (
            "HIGH priority pass. Downlinking time-critical wildfire thermal imagery; "
            "partial data is unusable. Maintain continuous lock or request handoff."
        ),
        "spectrum": (
            "Adjacent S-band radar sweeps our passband ~every 40s. Periodic RFI is "
            "expected and SELF-CLEARS. Do NOT frequency-hop to chase it — riding it "
            "out costs less than burning the slew/tuning budget."
        ),
        "operator": (
            "Front-end recalibrated yesterday, noise floor nominal. Pointing is "
            "trustworthy this pass."
        ),
    },
    rules={
        "no_freq_hop": 0.20,      # spectrum advisory: ride out the self-clearing RFI
        "continuous_lock": 0.15,  # mission brief: continuous lock or nothing
    },
)
_rfi_advisory.slug = "rfi-advisory"

# -- operational-context twist: operator log flags a sticky az servo -----------
# Drift is real, but a large azimuth slew risks jamming the mount. The correct
# play is small nudges (and/or freq/pol fixes), not snap_to_ephemeris.
_servo_sticky = hold_the_link(
    anomaly="drift",
    severity=0.8,
    onset=160,
    duration=240,
    init_az_error=0.6,
    init_el_error=0.2,
    seed=21,
    target_lock_pct=0.85,
    context={
        "mission_brief": (
            "Routine science downlink. Keep the link healthy through the pass."
        ),
        "operator": (
            "Az servo on this dish STICKS in the cold this morning. Avoid large "
            "azimuth slews — a big move may jam it and we lose the whole pass. "
            "Use small nudges only; prefer freq/polarization fixes where possible."
        ),
    },
    rules={
        "no_large_slew": 0.20,    # operator log: large slews risk jamming the servo
    },
)
_servo_sticky.slug = "servo-sticky"

tasks = [
    _drift,
    _rfi,
    _polarization,
    _multipath,
    _hardware,
    _clean,
    _drift_easy,
    _drift_hard,
    _rfi_advisory,
    _servo_sticky,
]

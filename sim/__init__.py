"""Satellite ground-station simulation package.

The physics, anomaly, and episode-generation code that powers the RL
environment. The submodules import each other with bare names and rely on
their own directory being on ``sys.path`` (inserted below), so they can be
imported either as ``sim`` (``from sim import SatelliteEnv``) or directly as
top-level modules (``from satellite_env import SatelliteEnv`` after adding this
folder to the path) — the latter is how the standalone test scripts load them.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from physics import compute_snr  # noqa: E402
from anomalies import (  # noqa: E402
    ANOMALY_TYPES,
    AnomalyState,
    apply_anomaly,
    sample_anomaly,
)
from episode_generator import (  # noqa: E402
    EpisodePlan,
    _synthetic_arc,
    fetch_tles,
    generate_episode,
)
from satellite_env import (  # noqa: E402
    ACTIONS,
    SNR_LOCK_MIN,
    SNR_THRESHOLD,
    SatelliteEnv,
)

__all__ = [
    "ACTIONS",
    "ANOMALY_TYPES",
    "AnomalyState",
    "EpisodePlan",
    "SNR_LOCK_MIN",
    "SNR_THRESHOLD",
    "SatelliteEnv",
    "_synthetic_arc",
    "apply_anomaly",
    "compute_snr",
    "fetch_tles",
    "generate_episode",
    "sample_anomaly",
]

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


ANOMALY_TYPES = ['drift', 'rfi', 'polarization', 'multipath', 'hardware']


@dataclass
class AnomalyState:
    kind: str
    onset_time: int        # timestep when anomaly begins
    duration: int          # timesteps anomaly lasts
    severity: float        # [0.0, 1.0]
    active: bool = False
    resolved: bool = False

    # Internal state per anomaly type
    drift_rate_az: float = 0.0
    drift_rate_el: float = 0.0
    rfi_power_w: float = 0.0
    true_polarization: int = 0   # for polarization anomaly
    multipath_phase: float = 0.0
    hardware_noise_delta_k: float = 0.0


def sample_anomaly(onset_range=(100, 400), severity_range=(0.3, 1.0)) -> AnomalyState:
    kind = np.random.choice(ANOMALY_TYPES)
    onset = int(np.random.uniform(*onset_range))
    severity = float(np.random.uniform(*severity_range))
    duration = int(np.random.uniform(30, 180))

    a = AnomalyState(kind=kind, onset_time=onset, duration=duration, severity=severity)

    if kind == 'drift':
        a.drift_rate_az = severity * 0.05 * np.random.choice([-1, 1])
        a.drift_rate_el = severity * 0.03 * np.random.choice([-1, 1])

    elif kind == 'rfi':
        # interference power that competes with signal noise floor
        a.rfi_power_w = severity * 1e-10

    elif kind == 'polarization':
        # signal arrives on a different polarization than expected
        a.true_polarization = int(np.random.choice([1, 2, 3]))  # not 0 (default H)

    elif kind == 'multipath':
        a.multipath_phase = float(np.random.uniform(0, 2 * np.pi))

    elif kind == 'hardware':
        a.hardware_noise_delta_k = severity * 500.0  # Kelvin increase in noise temp

    return a


def apply_anomaly(anomaly: AnomalyState, t: int, env_state: dict) -> dict:
    """
    Modifies env_state in place based on anomaly type and current timestep.
    Returns the modified env_state dict.
    """
    elapsed = t - anomaly.onset_time

    if not (0 <= elapsed < anomaly.duration):
        return env_state

    if anomaly.kind == 'drift':
        env_state['az_error'] += anomaly.drift_rate_az
        env_state['el_error'] += anomaly.drift_rate_el

    elif anomaly.kind == 'rfi':
        env_state['interference_power'] += anomaly.rfi_power_w

    elif anomaly.kind == 'polarization':
        env_state['true_polarization'] = anomaly.true_polarization

    elif anomaly.kind == 'multipath':
        # Oscillating destructive interference
        phase = anomaly.multipath_phase + elapsed * 0.3
        env_state['atmospheric_loss_db'] += anomaly.severity * 3.0 * (1 + np.sin(phase)) / 2

    elif anomaly.kind == 'hardware':
        env_state['noise_temp'] += anomaly.hardware_noise_delta_k

    return env_state

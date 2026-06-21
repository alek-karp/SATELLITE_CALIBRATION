import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Optional, List
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from physics import compute_snr
from anomalies import apply_anomaly, AnomalyState
from episode_generator import generate_episode, EpisodePlan, fetch_tles

SNR_THRESHOLD = 10.0   # dB — minimum acceptable signal
SNR_LOCK_MIN  = 5.0    # dB — below this, signal lock is lost

TRACKING_LEAK  = 0.02  # fraction of satellite motion that leaks in as pointing error
ACTUATOR_COST  = 0.05  # per-use cost for freq / pol / bandwidth changes (anti-thrash)
HANDOFF_PENALTY = -5.0 # premature handoff request


# Action indices
ACTIONS = [
    'nudge_az_pos_small',   # 0
    'nudge_az_neg_small',   # 1
    'nudge_az_pos_medium',  # 2
    'nudge_az_neg_medium',  # 3
    'nudge_az_pos_large',   # 4
    'nudge_az_neg_large',   # 5
    'nudge_el_pos_small',   # 6
    'nudge_el_neg_small',   # 7
    'nudge_el_pos_medium',  # 8
    'nudge_el_neg_medium',  # 9
    'nudge_el_pos_large',   # 10
    'nudge_el_neg_large',   # 11
    'snap_to_ephemeris',    # 12
    'shift_freq_pos_fine',  # 13
    'shift_freq_neg_fine',  # 14
    'shift_freq_pos_med',   # 15
    'shift_freq_neg_med',   # 16
    'shift_freq_pos_coarse',# 17
    'shift_freq_neg_coarse',# 18
    'cycle_polarization',   # 19
    'narrow_bandwidth',     # 20
    'widen_bandwidth',      # 21
    'hold',                 # 22
    'request_handoff',      # 23
]

AZ_NUDGE  = [0.1, 0.1, 0.5, 0.5, 2.0, 2.0]
EL_NUDGE  = [0.1, 0.1, 0.5, 0.5, 2.0, 2.0]
FREQ_STEP = [10, 10, 100, 100, 1000, 1000]


class SatelliteEnv(gym.Env):
    metadata = {'render_modes': ['human', 'rgb_array']}

    def __init__(self, difficulty='medium', render_mode=None):
        super().__init__()
        self.difficulty = difficulty
        self.render_mode = render_mode
        self._tles = None

        self.action_space = spaces.Discrete(len(ACTIONS))

        # Observation: 14 floats
        # [snr, snr_trend, locked, ber, az_curr, el_curr, az_exp, el_exp,
        #  az_delta, el_delta, slew_rate, freq_offset, pol_mode, noise_temp_norm, time_remaining_norm]
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(15,), dtype=np.float32
        )

        self._episode: Optional[EpisodePlan] = None
        self._t = 0
        self._state = {}
        self._snr_history = []
        self._total_reward = 0.0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if self._tles is None:
            self._tles = fetch_tles()

        self._episode = generate_episode(difficulty=self.difficulty, tles=self._tles)
        ep = self._episode
        self._t = 0
        self._snr_history = []
        self._total_reward = 0.0

        self._state = {
            'az_error': ep.initial_az_error,
            'el_error': ep.initial_el_error,
            'freq_offset': ep.initial_freq_offset,
            'pol_mode': 0,
            'true_polarization': 0,
            'interference_power': 0.0,
            'noise_temp': ep.noise_level,
            'atmospheric_loss_db': 0.5,
            'bandwidth_factor': 1.0,
            'slew_rate': 0.0,
            'locked': True,
        }

        obs = self._get_obs()
        return obs, self._get_info()

    def step(self, action: int):
        ep = self._episode
        t = self._t
        s = self._state

        # Reset per-step transient effects
        s['interference_power'] = 0.0
        s['atmospheric_loss_db'] = 0.5
        true_pol_reset = s.get('base_true_polarization', 0)
        s['true_polarization'] = true_pol_reset

        # Apply all active anomalies
        for anomaly in ep.anomalies:
            s = apply_anomaly(anomaly, t, s)

        # Execute action
        slew = 0.0
        actuator_cost = 0.0
        handoff_penalty = 0.0
        action_name = ACTIONS[action]

        if action_name.startswith('nudge_az'):
            idx = ACTIONS.index(action_name)
            delta = AZ_NUDGE[idx] * (1 if 'pos' in action_name else -1)
            s['az_error'] += delta
            slew = abs(delta)

        elif action_name.startswith('nudge_el'):
            idx = ACTIONS.index(action_name)
            delta = EL_NUDGE[idx - 6] * (1 if 'pos' in action_name else -1)
            s['el_error'] += delta
            slew = abs(delta)

        elif action_name == 'snap_to_ephemeris':
            s['az_error'] = 0.0
            s['el_error'] = 0.0
            slew = 5.0  # large slew cost

        elif action_name.startswith('shift_freq'):
            idx = ACTIONS.index(action_name) - 13
            step = FREQ_STEP[idx] * (1 if 'pos' in action_name else -1)
            s['freq_offset'] = np.clip(s['freq_offset'] + step, -50000, 50000)
            actuator_cost = ACTUATOR_COST

        elif action_name == 'cycle_polarization':
            s['pol_mode'] = (s['pol_mode'] + 1) % 4
            actuator_cost = ACTUATOR_COST

        elif action_name == 'narrow_bandwidth':
            s['bandwidth_factor'] = max(0.1, s['bandwidth_factor'] * 0.5)
            actuator_cost = ACTUATOR_COST

        elif action_name == 'widen_bandwidth':
            s['bandwidth_factor'] = min(4.0, s['bandwidth_factor'] * 2.0)
            actuator_cost = ACTUATOR_COST

        elif action_name == 'hold':
            slew = 0.0  # explicit no-op

        elif action_name == 'request_handoff':
            # Only valid in last 20% of pass — otherwise penalize
            progress = self._t / ep.pass_duration
            if progress > 0.8:
                obs = self._get_obs()
                reward = self._total_reward * 0.3
                return obs, reward, True, False, self._get_info()
            else:
                handoff_penalty = HANDOFF_PENALTY  # premature handoff request

        s['slew_rate'] = slew
        reward = 0.0

        # Compute SNR
        current_elevation = float(ep.ephemeris_el[min(t, ep.pass_duration - 1)])
        snr = compute_snr(
            az_error_deg=s['az_error'],
            el_error_deg=s['el_error'],
            freq_offset_hz=s['freq_offset'],
            pol_mode=s['pol_mode'],
            true_polarization=s['true_polarization'],
            interference_power_w=s['interference_power'],
            noise_temp_k=s['noise_temp'] / s['bandwidth_factor'],
            atmospheric_loss_db=s['atmospheric_loss_db'],
            elevation_deg=current_elevation,
        )

        # Add observation noise. The agent sees (and the telemetry/obs report)
        # this noisy value; the *reward* must key off the clean physics value so
        # the score is reproducible for a given seed — not jittered by unseeded
        # measurement noise straddling the threshold.
        snr_observed = snr + np.random.normal(0, 1.0)
        s['snr_true'] = float(snr)
        s['locked'] = snr > SNR_LOCK_MIN

        self._snr_history.append(snr_observed)

        # Reward
        if snr >= SNR_THRESHOLD:
            reward += 1.0
        elif snr > SNR_LOCK_MIN:
            # Shaped ramp across the 5–10 dB band so the agent gets a dense
            # gradient while recovering, instead of a flat zero "dead zone".
            reward += (snr - SNR_LOCK_MIN) / (SNR_THRESHOLD - SNR_LOCK_MIN)
        if not s['locked']:
            reward -= 10.0
        reward -= slew * 0.1
        reward -= actuator_cost
        reward += handoff_penalty

        self._total_reward += reward
        self._t += 1

        # Update ephemeris tracking (satellite moves each step).
        # The mount's nominal tracking loop is imperfect: a fraction of the
        # satellite's motion leaks in as pointing error the agent must correct.
        # This makes active tracking a real task in every episode, even without
        # an anomaly present.
        if t + 1 < ep.pass_duration:
            # Shortest signed delta so azimuth wrap (359°→1°) doesn't spike.
            az_delta = ((ep.ephemeris_az[t + 1] - ep.ephemeris_az[t] + 180) % 360) - 180
            el_delta = ep.ephemeris_el[t + 1] - ep.ephemeris_el[t]
            s['az_error'] += TRACKING_LEAK * az_delta
            s['el_error'] += TRACKING_LEAK * el_delta

        terminated = self._t >= ep.pass_duration
        obs = self._get_obs()
        return obs, reward, terminated, False, self._get_info()

    def _get_obs(self) -> np.ndarray:
        ep = self._episode
        s = self._state
        t = min(self._t, ep.pass_duration - 1)

        az_exp = ep.ephemeris_az[t]
        el_exp = ep.ephemeris_el[t]

        snr_now = self._snr_history[-1] if self._snr_history else 20.0
        snr_prev = self._snr_history[-2] if len(self._snr_history) > 1 else snr_now
        snr_trend = snr_now - snr_prev

        time_remaining_norm = (ep.pass_duration - t) / ep.pass_duration

        return np.array([
            snr_now / 30.0,                        # normalized SNR
            snr_trend / 5.0,                       # normalized trend
            float(s['locked']),                    # lock status
            0.0,                                   # BER placeholder
            s['az_error'] / 5.0,                   # normalized az error
            s['el_error'] / 5.0,                   # normalized el error
            az_exp / 360.0,                        # expected az
            el_exp / 90.0,                         # expected el
            s['az_error'] / 5.0,                   # az delta (same as error in this model)
            s['el_error'] / 5.0,                   # el delta
            s['slew_rate'] / 5.0,                  # normalized slew
            s['freq_offset'] / 1000.0,             # normalized freq offset
            s['pol_mode'] / 3.0,                   # normalized pol mode
            s['noise_temp'] / 500.0,               # normalized noise temp
            time_remaining_norm,                   # time remaining
        ], dtype=np.float32)

    def _get_info(self) -> dict:
        ep = self._episode
        s = self._state
        t = min(self._t, ep.pass_duration - 1)
        snr_now = self._snr_history[-1] if self._snr_history else 20.0
        return {
            'satellite': ep.satellite_name,
            'timestep': self._t,
            'snr_db': snr_now,                              # noisy (observed)
            'snr_db_true': float(s.get('snr_true', snr_now)),  # clean (for reward)
            'locked': s['locked'],
            'az_error': s['az_error'],
            'el_error': s['el_error'],
            'freq_offset': s['freq_offset'],
            'pol_mode': s['pol_mode'],
            'total_reward': self._total_reward,
            'pass_duration': ep.pass_duration,
            'max_elevation': ep.max_elevation,
            'anomalies': [a.kind for a in ep.anomalies],
        }

    def render(self):
        if self.render_mode == 'human':
            info = self._get_info()
            snr = info['snr_db']
            bar = '█' * int(max(0, snr)) + '░' * max(0, 30 - int(max(0, snr)))
            lock = '🔒' if info['locked'] else '✗'
            print(
                f"t={info['timestep']:4d}/{info['pass_duration']} "
                f"| {lock} SNR={snr:6.1f}dB [{bar[:30]}] "
                f"| az_err={info['az_error']:+.2f}° "
                f"| el_err={info['el_error']:+.2f}° "
                f"| freq={info['freq_offset']:+.0f}Hz "
                f"| R={info['total_reward']:+.1f}"
            )

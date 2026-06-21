"""
Specific episode test — deterministic seed, known anomaly, heuristic agent.
Goal: verify the environment behaves sensibly before training.
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'sim'))

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from satellite_env import SatelliteEnv, ACTIONS
from anomalies import AnomalyState
from episode_generator import EpisodePlan, _synthetic_arc

np.random.seed(42)

# ── Build a fully deterministic episode ──────────────────────────────────────

az_arc, el_arc = _synthetic_arc(600)

# Force a nice 60° max elevation pass
t = np.linspace(0, np.pi, 600)
el_arc = 60.0 * np.sin(t)
az_arc  = 180.0 + 80.0 * (t / np.pi - 0.5)   # sweeps 140°→220°

ANOMALY_ONSET = 200   # timestep
ANOMALY_KIND  = 'drift'  # pointing drift — clearest to visualize

anomaly = AnomalyState(
    kind=ANOMALY_KIND,
    onset_time=ANOMALY_ONSET,
    duration=200,
    severity=0.8,
    drift_rate_az=0.08,   # deg/step — cumulative pointing drift
    drift_rate_el=0.03,
)

episode = EpisodePlan(
    satellite_name='SYNTHETIC-LEO-42',
    ephemeris_az=az_arc,
    ephemeris_el=el_arc,
    pass_duration=600,
    max_elevation=60.0,
    initial_az_error=0.2,
    initial_el_error=0.1,
    initial_freq_offset=50.0,
    noise_level=120.0,
    anomalies=[anomaly],
)

# ── Heuristic agent ───────────────────────────────────────────────────────────

def heuristic_action(obs, prev_snr_trend):
    """
    Simple rule-based agent:
    - If SNR trend is falling fast → diagnose and correct
    - Prefer pointing corrections before freq adjustments
    """
    snr_norm      = obs[0]
    snr_trend     = obs[1]
    locked        = obs[2] > 0.5
    az_error_norm = obs[4]   # positive = antenna pointing right of satellite
    el_error_norm = obs[5]
    freq_offset   = obs[11] * 1000.0  # denormalize

    # If not locked: snap to ephemeris
    if not locked:
        return ACTIONS.index('snap_to_ephemeris')

    # If az error growing: nudge back
    if abs(az_error_norm) > 0.3:
        if az_error_norm > 0:
            return ACTIONS.index('nudge_az_neg_medium')
        else:
            return ACTIONS.index('nudge_az_pos_medium')

    if abs(el_error_norm) > 0.3:
        if el_error_norm > 0:
            return ACTIONS.index('nudge_el_neg_medium')
        else:
            return ACTIONS.index('nudge_el_pos_medium')

    # If SNR falling but pointing looks ok: try freq correction
    if snr_trend < -0.3 and abs(freq_offset) > 200:
        if freq_offset > 0:
            return ACTIONS.index('shift_freq_neg_med')
        else:
            return ACTIONS.index('shift_freq_pos_med')

    # Fine-tune pointing if small error
    if abs(az_error_norm) > 0.05:
        return ACTIONS.index('nudge_az_neg_small' if az_error_norm > 0 else 'nudge_az_pos_small')

    return ACTIONS.index('hold')


# ── Run two agents on the SAME episode ───────────────────────────────────────

def run_episode(use_heuristic: bool, label: str):
    env = SatelliteEnv(difficulty='medium')

    # Inject our deterministic episode directly
    obs, info = env.reset()
    env._episode = episode
    env._t = 0
    env._snr_history = []
    env._total_reward = 0.0
    env._state = {
        'az_error': episode.initial_az_error,
        'el_error': episode.initial_el_error,
        'freq_offset': episode.initial_freq_offset,
        'pol_mode': 0,
        'true_polarization': 0,
        'interference_power': 0.0,
        'noise_temp': episode.noise_level,
        'atmospheric_loss_db': 0.5,
        'bandwidth_factor': 1.0,
        'slew_rate': 0.0,
        'locked': True,
    }
    obs = env._get_obs()

    log = {'snr': [], 'az_err': [], 'el_err': [], 'reward': [], 'action': [], 'locked': []}
    prev_trend = 0.0
    done = False

    while not done:
        if use_heuristic:
            action = heuristic_action(obs, prev_trend)
        else:
            action = env.action_space.sample()

        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        prev_trend = obs[1]

        log['snr'].append(info['snr_db'])
        log['az_err'].append(info['az_error'])
        log['el_err'].append(info['el_error'])
        log['reward'].append(info['total_reward'])
        log['action'].append(ACTIONS[action])
        log['locked'].append(info['locked'])

    steps = len(log['snr'])
    locked_pct = 100 * sum(log['locked']) / steps
    above_pct  = 100 * sum(s > 10 for s in log['snr']) / steps
    print(f"\n{label}")
    print(f"  Steps:              {steps}")
    print(f"  Final reward:       {log['reward'][-1]:.1f}")
    print(f"  Signal locked:      {locked_pct:.0f}%")
    print(f"  SNR > threshold:    {above_pct:.0f}%")
    print(f"  Mean SNR:           {np.mean(log['snr']):.1f} dB")
    return log


print("Running deterministic episode with POINTING DRIFT anomaly at t=200...")
print(f"Satellite: {episode.satellite_name}  |  Pass: {episode.pass_duration}s  |  Max el: {episode.max_elevation}°")

log_heuristic = run_episode(use_heuristic=True,  label="HEURISTIC AGENT")
log_random    = run_episode(use_heuristic=False, label="RANDOM AGENT")

# ── Plot ──────────────────────────────────────────────────────────────────────

fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
fig.suptitle(
    f'Episode: {episode.satellite_name}  |  Anomaly: {ANOMALY_KIND} @ t={ANOMALY_ONSET}s  |  Severity: {anomaly.severity}',
    fontsize=12, fontweight='bold'
)

steps_h = range(len(log_heuristic['snr']))
steps_r = range(len(log_random['snr']))

# Panel 1: SNR
ax1 = axes[0]
ax1.plot(steps_h, log_heuristic['snr'], color='#2ecc71', linewidth=1.2, label='Heuristic agent')
ax1.plot(steps_r, log_random['snr'],    color='#e74c3c', linewidth=1.0, alpha=0.7, label='Random agent')
ax1.axhline(10, color='orange', linestyle='--', linewidth=1, label='SNR threshold (10 dB)')
ax1.axvline(ANOMALY_ONSET, color='purple', linestyle=':', linewidth=1.5, label=f'Anomaly onset (t={ANOMALY_ONSET})')
ax1.axvline(ANOMALY_ONSET + anomaly.duration, color='purple', linestyle=':', linewidth=1.0, alpha=0.4)
ax1.set_ylabel('SNR (dB)')
ax1.set_ylim(-40, 70)
ax1.legend(fontsize=8, loc='upper right')
ax1.grid(True, alpha=0.3)
ax1.fill_between(steps_h, -40, 10, alpha=0.05, color='red')

# Panel 2: Pointing error
ax2 = axes[1]
ax2.plot(steps_h, log_heuristic['az_err'], color='#3498db', linewidth=1.2, label='Az error (heuristic)')
ax2.plot(steps_h, log_heuristic['el_err'], color='#9b59b6', linewidth=1.2, label='El error (heuristic)')
ax2.plot(steps_r, log_random['az_err'],    color='#3498db', linewidth=1.0, alpha=0.4, linestyle='--', label='Az error (random)')
ax2.axvline(ANOMALY_ONSET, color='purple', linestyle=':', linewidth=1.5)
ax2.axhline(0, color='black', linewidth=0.5)
ax2.axhline(1.5, color='orange', linestyle='--', linewidth=0.8, alpha=0.6, label='Beamwidth edge')
ax2.axhline(-1.5, color='orange', linestyle='--', linewidth=0.8, alpha=0.6)
ax2.set_ylabel('Pointing error (°)')
ax2.legend(fontsize=8, loc='upper right')
ax2.grid(True, alpha=0.3)

# Panel 3: Cumulative reward
ax3 = axes[2]
ax3.plot(steps_h, log_heuristic['reward'], color='#2ecc71', linewidth=1.2, label='Heuristic')
ax3.plot(steps_r, log_random['reward'],    color='#e74c3c', linewidth=1.0, alpha=0.7, label='Random')
ax3.axvline(ANOMALY_ONSET, color='purple', linestyle=':', linewidth=1.5)
ax3.axhline(0, color='black', linewidth=0.5)
ax3.set_ylabel('Cumulative reward')
ax3.set_xlabel('Timestep (seconds)')
ax3.legend(fontsize=8)
ax3.grid(True, alpha=0.3)

plt.tight_layout()
out = os.path.join(ROOT, 'docs', 'assets', 'episode_test.png')
plt.savefig(out, dpi=140, bbox_inches='tight')
print(f"\nPlot saved → {out}")
plt.show()

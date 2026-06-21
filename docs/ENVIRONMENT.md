# Satellite Ground Station — RL Environment Design

## Concept

A satellite is crossing overhead. The pass lasts 10 minutes. Something goes wrong
mid-pass. The agent must keep the signal alive until the window closes.

The agent controls a ground station antenna. It observes degrading signal quality
and must diagnose the cause, take corrective action, and recover — all under a
ticking clock.

Classical control (PID) handles nominal tracking. This environment is about
the hard cases: anomaly detection, diagnosis, and recovery under time pressure.
That is where RL wins.

---

## State Space

What the agent observes at each timestep:

```
Signal:
  snr_current           float    Current signal-to-noise ratio (noisy measurement)
  snr_trend             float    SNR slope over last 5 steps
  signal_locked         bool     Whether receiver has lock
  bit_error_rate        float    BER estimate

Pointing:
  azimuth_current       float    Current antenna azimuth (degrees)
  elevation_current     float    Current antenna elevation (degrees)
  azimuth_expected      float    Ephemeris-predicted azimuth
  elevation_expected    float    Ephemeris-predicted elevation
  azimuth_delta         float    Difference: actual vs expected
  elevation_delta       float    Difference: actual vs expected
  slew_rate             float    Current antenna movement speed

Receiver:
  frequency_offset      float    Hz offset from nominal carrier
  polarization_mode     int      0=H, 1=V, 2=RHCP, 3=LHCP
  noise_temperature     float    Receiver noise floor (hardware health proxy)

Context:
  time_remaining        float    Seconds left in pass
  anomaly_hint          float    Optional severity signal (disabled on hard mode)
```

---

## Action Space

Discrete actions the agent can take each timestep:

```
Pointing corrections:
  nudge_az_small        +/- 0.1° azimuth
  nudge_az_medium       +/- 0.5° azimuth
  nudge_az_large        +/- 2.0° azimuth
  nudge_el_small        +/- 0.1° elevation
  nudge_el_medium       +/- 0.5° elevation
  nudge_el_large        +/- 2.0° elevation
  scan_sweep            deliberate azimuth sweep to search for peak SNR
  snap_to_ephemeris     reset pointing to calculated position (costs ~10 seconds)

Receiver tuning:
  shift_freq_fine       +/- 10 Hz
  shift_freq_medium     +/- 100 Hz
  shift_freq_coarse     +/- 1 kHz
  cycle_polarization    step through H → V → RHCP → LHCP → H
  narrow_bandwidth      reduce receiver bandwidth (lower noise, less margin)
  widen_bandwidth       increase receiver bandwidth (more margin, more noise)

Diagnostic:
  hold                  stop all movement, take clean measurement
  request_handoff       transfer pass to next ground station (ends episode early, partial reward)
```

Total: ~20 discrete actions. Can be extended to continuous for az/el deltas.

---

## Anomaly Types

| Anomaly | How it appears to agent | Correct response |
|---|---|---|
| Pointing drift | SNR slowly falls, az/el delta from ephemeris grows | Nudge az/el back toward expected |
| RFI burst | Sudden SNR drop, noise temperature spikes | Shift frequency, narrow bandwidth |
| Polarization rotation | SNR drops ~3dB, symmetric degradation | Cycle polarization mode |
| Multipath fading | Rapid oscillating SNR, not correlated with pointing | Small pointing nudge or hold |
| Hardware fault | Noise temperature rises, SNR degrades globally | Narrow bandwidth or request handoff |

Hard mode: two anomalies can occur simultaneously.

The diagnostic challenge is the core of the environment. The agent sees SNR
dropping and must infer the cause before it can fix it. Each anomaly type has
a distinct signature — but signatures overlap under noise, and the clock is running.

---

## Reward Function

```python
def compute_reward(obs, action, prev_obs):
    reward = 0.0

    # Primary: maintain signal above threshold each timestep
    if obs.snr_current > SNR_THRESHOLD:
        reward += 1.0

    # Bonus: fast recovery after anomaly onset
    if anomaly_active and obs.snr_current > SNR_THRESHOLD:
        recovery_speed = 1.0 / (time_since_anomaly + 1)
        reward += recovery_speed * 2.0

    # Penalty: unnecessary slewing wastes time and causes wear
    reward -= obs.slew_rate * 0.1

    # Large penalty: complete signal loss
    if not obs.signal_locked:
        reward -= 10.0

    return reward
```

---

## Episode Arc

```
t=0         Cold start. Pointing error randomized. Agent acquires lock.
t=0–100     Nominal tracking. SNR is good. Baseline phase.
t=100–400   Anomaly injected at random time. Agent must notice → diagnose → act.
t=400–600   Recovery and maintenance. Hold signal until pass ends.
t=600       Episode ends. Score = cumulative reward (SNR maintained over pass).
```

Each episode is unique. The agent never sees anomaly parameters directly.

---

## Episode Generation

Episodes are generated procedurally from three ingredients. No hand-authoring.

### 1. Real Satellite Trajectories

CelesTrak publishes live TLE data for ~25,000 tracked objects. Feed a TLE into
Skyfield with a ground station location → full azimuth/elevation arc for that pass.

```python
from skyfield.api import load, wgs84, EarthSatellite

ts = load.timescale()
satellite = EarthSatellite(line1, line2, name, ts)
ground_station = wgs84.latlon(37.87, -122.25)

difference = satellite - ground_station
topocentric = difference.at(times)
alt, az, distance = topocentric.altaz()
# alt, az are the ephemeris arc for this episode
```

~25,000 satellites × ~4 passes/day × any ground station = effectively infinite
episode variety, all grounded in real orbital mechanics.

### 2. Anomaly Injection

```python
anomaly_type    = random.choice(['drift', 'RFI', 'polarization', 'multipath', 'hardware'])
onset_time      = random.uniform(100, 400)   # seconds into pass
severity        = random.uniform(0.2, 1.0)
duration        = random.uniform(30, 180)    # seconds

# Hard mode: second anomaly
if difficulty == 'hard':
    anomaly_2 = sample_anomaly(onset_after=onset_time + 30)
```

### 3. Starting Conditions

```python
initial_az_error    = random.normal(0, sigma_az)    # sigma increases with difficulty
initial_el_error    = random.normal(0, sigma_el)
freq_offset         = random.uniform(-500, 500)     # Hz
noise_level         = random.uniform(noise_min, noise_max)
```

### Example Episode

```
Episode #4721
  Satellite:          NOAA-19 (real TLE from CelesTrak)
  Ground station:     Goldstone, CA
  Pass duration:      8m 42s
  Max elevation:      34° (medium difficulty geometry)

  Starting error:     az +1.2°, el -0.4°
  Atmospheric noise:  moderate

  Anomaly 1:  RFI burst    onset=127s  severity=0.7  duration=45s
  Anomaly 2:  Pointing drift  onset=310s  rate=0.3°/min
```

---

## Curriculum

| Stage | Episode filter | What agent learns |
|---|---|---|
| 1 | High-elevation passes, no anomalies | Basic tracking, ephemeris following |
| 2 | Mixed elevation, single anomaly, mild | Anomaly detection |
| 3 | Low-elevation passes, single anomaly, random severity | Diagnosis under noise |
| 4 | Any pass, two simultaneous anomalies | Multi-cause recovery |
| 5 | No ephemeris provided | Search and acquire unknown object |

Train on early stages, evaluate on late stages.

---

## Physics Model (Simplified)

To avoid weeks of simulation work, the physics is intentionally analytic:

```python
def compute_snr(pointing_error_deg, freq_offset_hz, polarization_match,
                interference_power, noise_temp, atmospheric_noise):

    # Antenna gain loss from pointing error (Gaussian beam approximation)
    beamwidth = 1.5  # degrees (typical for small dish)
    gain_loss = exp(-(pointing_error_deg ** 2) / (2 * (beamwidth / 2.35) ** 2))

    # Frequency offset loss (sinc^2 response)
    bandwidth = 1e6  # Hz
    freq_loss = sinc(freq_offset_hz / bandwidth) ** 2

    # Polarization mismatch loss
    pol_loss = polarization_match  # 1.0 if matched, 0.5 if orthogonal

    # Combine
    signal_power = EIRP * gain_loss * freq_loss * pol_loss
    noise_power = noise_temp * BOLTZMANN * bandwidth + atmospheric_noise + interference_power

    return signal_power / noise_power
```

This is physically motivated but not a full RF chain simulation.
Good enough for an RL environment — not a substitute for a real radio telescope.

---

## Tech Stack

| Component | Library |
|---|---|
| Orbital mechanics | `skyfield` |
| Environment wrapper | `gymnasium` |
| RL training | `stable-baselines3` (PPO) or LLM agent via Fireworks AI |
| Visualization | `matplotlib` (live SNR + pointing plot) |
| TLE data | CelesTrak API (free) |
| Sandboxing | Modal or Daytona |

---

## File Structure (planned)

```
SATELLITE_CALIBRATION/
  ENVIRONMENT.md          ← this file
  env/
    satellite_env.py      Gymnasium environment class
    episode_generator.py  TLE fetching + anomaly injection
    physics.py            Analytic SNR model
    anomalies.py          Anomaly types and injection logic
  agent/
    train.py              PPO training loop
    llm_agent.py          LLM-based agent via tool calls
  viz/
    dashboard.py          Live episode visualization
  data/
    tle_cache/            Cached TLE files from CelesTrak
```

---

## What Makes This a Real RL Problem

The agent must:
1. Detect that something has changed (SNR falling)
2. Distinguish between 5 anomaly types from noisy observations
3. Take a sequence of targeted actions to recover
4. Do all of this before the pass window closes

A PID controller handles nominal tracking. It cannot diagnose anomaly type,
cannot choose between frequency shift vs. pointing correction vs. polarization
switch. That multi-step decision under uncertainty is where the policy lives.

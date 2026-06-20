import numpy as np
import urllib.request
import os
from dataclasses import dataclass, field
from typing import List, Tuple
from anomalies import sample_anomaly, AnomalyState

try:
    from skyfield.api import load, wgs84, EarthSatellite
    SKYFIELD_AVAILABLE = True
except ImportError:
    SKYFIELD_AVAILABLE = False

TLE_URL = "https://celestrak.org/SOCRATES/query.php?CODE=ALL&MAX=1000&FORMAT=TLE"
TLE_BACKUP_URL = "https://celestrak.org/pub/TLE/catalog.txt"
TLE_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "tle_cache.txt")

# Goldstone, CA — one of NASA's DSN stations
DEFAULT_GROUND_STATION = (35.4267, -116.8900, 1000.0)  # lat, lon, alt_m


@dataclass
class EpisodePlan:
    satellite_name: str
    ephemeris_az: np.ndarray    # azimuth degrees at each timestep
    ephemeris_el: np.ndarray    # elevation degrees at each timestep
    pass_duration: int          # seconds
    max_elevation: float        # degrees
    initial_az_error: float
    initial_el_error: float
    initial_freq_offset: float
    noise_level: float
    anomalies: List[AnomalyState] = field(default_factory=list)


def fetch_tles(force_refresh=False) -> List[Tuple[str, str, str]]:
    """Returns list of (name, line1, line2) tuples."""
    os.makedirs(os.path.dirname(TLE_CACHE), exist_ok=True)

    if not force_refresh and os.path.exists(TLE_CACHE):
        with open(TLE_CACHE) as f:
            raw = f.read()
    else:
        try:
            with urllib.request.urlopen(TLE_BACKUP_URL, timeout=5) as r:
                raw = r.read().decode()
            with open(TLE_CACHE, 'w') as f:
                f.write(raw)
        except Exception:
            # Fall back to synthetic TLEs for offline use
            return _synthetic_tles()

    tles = []
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    for i in range(0, len(lines) - 2, 3):
        if lines[i+1].startswith('1 ') and lines[i+2].startswith('2 '):
            tles.append((lines[i], lines[i+1], lines[i+2]))
    return tles if tles else _synthetic_tles()


def _synthetic_tles() -> List[Tuple[str, str, str]]:
    """Hardcoded real TLEs for offline use."""
    return [
        (
            "NOAA 19",
            "1 33591U 09005A   24001.50000000  .00000000  00000-0  00000-0 0  9999",
            "2 33591  99.1000 100.0000 0014000 100.0000 260.0000 14.12000000000010",
        ),
        (
            "TERRA",
            "1 25994U 99068A   24001.50000000  .00000000  00000-0  00000-0 0  9999",
            "2 25994  98.2000 120.0000 0001000  90.0000 270.0000 14.57000000000010",
        ),
        (
            "ISS (ZARYA)",
            "1 25544U 98067A   24001.50000000  .00000000  00000-0  00000-0 0  9999",
            "2 25544  51.6400 200.0000 0002000  80.0000 280.0000 15.49000000000010",
        ),
    ]


def compute_pass_arc(name: str, line1: str, line2: str,
                     ground_station=DEFAULT_GROUND_STATION,
                     duration_s: int = 600) -> Tuple[np.ndarray, np.ndarray]:
    """Returns (azimuth_array, elevation_array) over duration_s seconds."""
    if not SKYFIELD_AVAILABLE:
        return _synthetic_arc(duration_s)

    try:
        ts = load.timescale()
        satellite = EarthSatellite(line1, line2, name, ts)
        lat, lon, alt = ground_station
        gs = wgs84.latlon(lat, lon, elevation_m=alt)

        t0 = ts.now()
        times = ts.tt_jd([t0.tt + s / 86400.0 for s in range(duration_s)])

        diff = satellite - gs
        topo = diff.at(times)
        alt_arr, az_arr, _ = topo.altaz()

        return az_arr.degrees, alt_arr.degrees
    except Exception:
        return _synthetic_arc(duration_s)


def _synthetic_arc(duration_s: int) -> Tuple[np.ndarray, np.ndarray]:
    """Generates a plausible synthetic satellite pass arc."""
    t = np.linspace(0, np.pi, duration_s)
    max_el = np.random.uniform(15, 75)
    az_start = np.random.uniform(0, 360)
    az_sweep = np.random.uniform(60, 150) * np.random.choice([-1, 1])

    elevation = max_el * np.sin(t)
    azimuth = az_start + az_sweep * (t / np.pi)
    azimuth = azimuth % 360

    return azimuth, elevation


def generate_episode(
    difficulty: str = 'medium',
    tles: List = None,
    num_anomalies: int = None,
) -> EpisodePlan:
    if tles is None:
        tles = fetch_tles()

    name, l1, l2 = tles[np.random.randint(len(tles))]
    az_arc, el_arc = compute_pass_arc(name, l1, l2)

    # Trim to above-horizon portion only
    above = el_arc > 5.0
    if above.any():
        start = np.argmax(above)
        end = len(above) - np.argmax(above[::-1])
        az_arc = az_arc[start:end]
        el_arc = el_arc[start:end]
    else:
        # Satellite never rises above horizon for this TLE/time — use synthetic arc
        az_arc, el_arc = _synthetic_arc(600)

    # Clamp to reasonable pass length
    max_len = 600
    az_arc = az_arc[:max_len]
    el_arc = el_arc[:max_len]

    duration = len(az_arc)
    max_el = float(el_arc.max())

    # Starting errors scale with difficulty
    sigma = {'easy': 0.3, 'medium': 0.8, 'hard': 2.0}.get(difficulty, 0.8)
    noise = {'easy': 50, 'medium': 150, 'hard': 350}.get(difficulty, 150)

    if num_anomalies is None:
        num_anomalies = {'easy': 0, 'medium': 1, 'hard': 2}.get(difficulty, 1)

    anomalies = []
    for i in range(num_anomalies):
        onset_min = 30 + i * 60
        onset_max = max(onset_min + 30, duration - 100)
        if onset_min >= duration:
            break
        a = sample_anomaly(onset_range=(onset_min, min(onset_max, duration - 50)))
        anomalies.append(a)

    return EpisodePlan(
        satellite_name=name,
        ephemeris_az=az_arc,
        ephemeris_el=el_arc,
        pass_duration=duration,
        max_elevation=max_el,
        initial_az_error=float(np.random.normal(0, sigma)),
        initial_el_error=float(np.random.normal(0, sigma)),
        initial_freq_offset=float(np.random.uniform(-300, 300)),
        noise_level=float(noise),
        anomalies=anomalies,
    )

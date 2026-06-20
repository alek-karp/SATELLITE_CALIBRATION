import numpy as np

BOLTZMANN = 1.38e-23
BANDWIDTH = 1e6        # Hz
EIRP_DBW = 12.0        # dBW — satellite transmit EIRP (small LEO smallsat)
FREQ_HZ = 2.4e9        # S-band carrier
ALTITUDE_KM = 600.0    # nominal LEO altitude
BEAMWIDTH_DEG = 1.5    # Antenna half-power beamwidth
RECEIVE_GAIN_DB = 15.0 # Ground antenna gain (dBi) — modest station


def pointing_gain_loss(az_error_deg: float, el_error_deg: float) -> float:
    """Gaussian beam approximation. Returns linear gain factor [0, 1]."""
    sigma = BEAMWIDTH_DEG / 2.355
    error = np.sqrt(az_error_deg**2 + el_error_deg**2)
    return float(np.exp(-(error**2) / (2 * sigma**2)))


def frequency_loss(freq_offset_hz: float) -> float:
    """Sinc^2 response for frequency offset within bandwidth."""
    x = freq_offset_hz / BANDWIDTH
    if abs(x) < 1e-9:
        return 1.0
    return float((np.sin(np.pi * x) / (np.pi * x)) ** 2)


def polarization_loss(mode: int, true_polarization: int) -> float:
    """
    Returns power factor [0.0, 1.0].
    Matched = 1.0, orthogonal = 0.0, circular vs linear = 0.5.
    modes: 0=H, 1=V, 2=RHCP, 3=LHCP
    """
    if mode == true_polarization:
        return 1.0
    circular = {2, 3}
    linear = {0, 1}
    if mode in circular and true_polarization in circular:
        return 0.0   # opposite circular
    if mode in linear and true_polarization in linear:
        return 0.0   # orthogonal linear
    return 0.5       # circular vs linear


def free_space_path_loss_db(elevation_deg: float) -> float:
    """FSPL in dB. Higher elevation = shorter slant range = less loss."""
    elevation_rad = max(np.radians(elevation_deg), np.radians(5.0))
    # Slant range from ground to LEO satellite
    R_earth = 6371.0  # km
    h = ALTITUDE_KM
    slant_km = np.sqrt((R_earth + h)**2 - (R_earth * np.cos(elevation_rad))**2) - R_earth * np.sin(elevation_rad)
    slant_m = slant_km * 1e3
    fspl = 20 * np.log10(slant_m) + 20 * np.log10(FREQ_HZ) + 20 * np.log10(4 * np.pi / 3e8)
    return float(fspl)


def compute_snr(
    az_error_deg: float,
    el_error_deg: float,
    freq_offset_hz: float,
    pol_mode: int,
    true_polarization: int,
    interference_power_w: float,
    noise_temp_k: float,
    atmospheric_loss_db: float,
    elevation_deg: float = 30.0,
) -> float:
    """Returns SNR in dB. Realistic range: ~5–20 dB for LEO S-band link."""
    g_point = pointing_gain_loss(az_error_deg, el_error_deg)
    g_freq = frequency_loss(freq_offset_hz)
    g_pol = polarization_loss(pol_mode, true_polarization)

    fspl_db = free_space_path_loss_db(elevation_deg)
    atm_loss_db = atmospheric_loss_db
    total_loss_db = fspl_db + atm_loss_db

    # Link budget in dB
    received_power_dbw = EIRP_DBW + RECEIVE_GAIN_DB - total_loss_db
    received_power_w = 10 ** (received_power_dbw / 10)
    received_power_w *= g_point * g_freq * g_pol

    noise_power_w = noise_temp_k * BOLTZMANN * BANDWIDTH + interference_power_w

    if noise_power_w <= 0 or received_power_w <= 0:
        return -30.0
    snr_linear = received_power_w / noise_power_w
    return float(10 * np.log10(max(snr_linear, 1e-12)))

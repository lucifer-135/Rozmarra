"""Models of the CGM sensor and the smartwatch signals (docs/techstack.md, Section 6.3).

These models are assumptions based on published physiology. Results on simulated data
therefore partly reflect these assumptions, and the real-data tests check whether
wearable signals help in real life. Every function works on one patient's timeline, with
one value for each minute. Minute 0 is midnight at the start of the timeline.

Sleep stage codes: 0 is awake in bed, 1 is light sleep, 2 is deep sleep and 3 is REM sleep.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import lfilter

DAY = 1440
AWAKE_METS = 1.2
ASLEEP_METS = 0.95

# Work periods for each occupation: (start minute, end minute, METs). These are assumptions.
OCCUPATION_PERIODS = {
    "Homemaker": [(420, 480, 2.5), (660, 750, 2.5), (1020, 1110, 2.3)],
    "Office worker": [(540, 570, 3.0), (570, 1050, 1.3), (1050, 1080, 3.0)],
    "Schoolteacher": [(480, 840, 1.8)],
    "Shopkeeper": [(600, 1200, 1.9)],
    "Tailor": [(600, 1140, 1.5)],
    "Driver": [(480, 1080, 1.5)],
    "Factory worker": [(480, 1020, 3.0)],
    "Farmer": [(360, 720, 3.5), (900, 1080, 3.5)],
    "Vegetable vendor": [(360, 780, 3.0), (960, 1200, 2.5)],
    "Retired": [(390, 435, 3.3)],
}


def occupation_periods(occupation: str):
    for key, periods in OCCUPATION_PERIODS.items():
        if occupation.startswith(key):
            return periods
    return OCCUPATION_PERIODS["Retired"]


@dataclass
class SignalProfile:
    """The personal settings of the wearable models for one patient."""

    resting_hr: float
    age: int
    hypo_hr_rise: float  # Beats per minute at full effect, after the reductions
    rmssd_base: float  # ms
    cgm_lag_min: int
    cgm_noise_sd: float
    cgm_bias: float


def signal_profile(resting_hr, age, years_with_diabetes, unaware, beta_blocker, rng):
    rise = rng.uniform(15, 20)
    if age > 65:
        rise *= 0.6
    if years_with_diabetes > 15:
        rise *= 0.7
    if unaware:
        rise *= 0.4
    if beta_blocker:
        rise *= 0.4
    return SignalProfile(
        resting_hr=float(resting_hr),
        age=int(age),
        hypo_hr_rise=float(rise),
        rmssd_base=float(np.clip(45 - 0.5 * (age - 30), 12, 60) * rng.uniform(0.8, 1.2)),
        cgm_lag_min=int(rng.integers(5, 11)),
        cgm_noise_sd=float(rng.uniform(6, 10)),
        cgm_bias=float(rng.normal(0, 0.03)),
    )


def sleep_stages(
    windows: list[tuple[int, int]], minutes: int, rng: np.random.Generator
) -> np.ndarray:
    """Sleep stage codes for each minute. Minutes outside sleep have the value -1."""
    stages = np.full(minutes, -1, dtype=int)
    for start, end in windows:
        start, end = max(0, start), min(minutes, end)
        t, cycle = start, 0
        while t < end:
            length = int(rng.normal(90, 10))
            deep = max(0.05, 0.30 - 0.07 * cycle)
            rem = min(0.35, 0.10 + 0.06 * cycle)
            parts = [(1, 0.5 - deep / 2), (2, deep), (1, 0.5 - rem / 2), (3, rem)]
            for code, share in parts:
                span = max(1, int(round(length * max(share, 0.02))))
                stages[t : min(end, t + span)] = code
                t += span
                if t >= end:
                    break
            if t < end and rng.random() < 0.4:
                stages[t : min(end, t + 3)] = 0
                t += 3
            cycle += 1
    return stages


def activity_mets(
    minutes: int,
    occupation: str,
    asleep: np.ndarray,
    extra: list[tuple[int, int, float]],
    rng: np.random.Generator,
) -> np.ndarray:
    """Physical activity in METs for each minute."""
    mets = np.full(minutes, AWAKE_METS)
    for day in range(minutes // DAY + 1):
        offset = day * DAY
        for start, end, level in occupation_periods(occupation):
            mets[offset + start : min(minutes, offset + end)] = level
        for _ in range(rng.poisson(3)):
            walk = offset + int(rng.integers(7 * 60, 21 * 60))
            mets[walk : min(minutes, walk + int(rng.integers(5, 16)))] = 3.0
    for start, end, level in extra:
        mets[max(0, start) : min(minutes, end)] = level
    mets *= rng.lognormal(0, 0.1, minutes)
    mets[asleep] = ASLEEP_METS
    return np.maximum(mets, 0.9)


def steps_per_minute(mets: np.ndarray, asleep: np.ndarray, rng: np.random.Generator):
    """Steps for each minute. Walking (3 METs or more) gives many steps, and light work fewer."""
    noise = rng.uniform(0.7, 1.3, len(mets))
    walking = np.clip((mets - 1.3) * 45, 0, 125)
    light_work = np.clip((mets - 1.5) * 20, 0, None)
    idle = rng.poisson(2, len(mets))
    steps = np.where(mets >= 3.0, walking, np.where(mets >= 2.0, light_work, idle)) * noise
    steps[asleep] = 0
    return np.round(steps)


def _smooth(values: np.ndarray, tau_min: float) -> np.ndarray:
    """Exponential smoothing with the time constant tau, starting at the first value."""
    alpha = 1 / tau_min
    return lfilter([alpha], [1, alpha - 1], values, zi=[values[0] * (1 - alpha)])[0]


def _ar1(n: int, sd: float, phi: float, rng: np.random.Generator) -> np.ndarray:
    """Correlated noise with the standard deviation sd and the correlation phi between minutes."""
    shocks = rng.normal(0, sd * np.sqrt(1 - phi**2), n)
    return lfilter([1], [1, -phi], shocks, zi=[phi * rng.normal(0, sd)])[0]


@dataclass
class HeartSignals:
    heart_rate: np.ndarray
    rmssd: np.ndarray


def heart_signals(
    glucose: np.ndarray,
    mets: np.ndarray,
    asleep: np.ndarray,
    hours_without_water: np.ndarray,
    profile: SignalProfile,
    rng: np.random.Generator,
) -> HeartSignals:
    minutes = len(mets)
    hour = (np.arange(minutes) % DAY) / 60
    circadian = -5 * np.cos(2 * np.pi * (hour - 4) / 24)
    activity = _smooth(9 * np.maximum(mets - 1, 0), 3)
    low = _smooth(profile.hypo_hr_rise * np.clip((72 - glucose[:minutes]) / 12, 0, 1), 10)
    thirst = np.minimum(4, 0.4 * np.maximum(hours_without_water - 8, 0))
    calm = profile.resting_hr + circadian - 5 * asleep + activity
    heart_rate = calm + low + thirst + _ar1(minutes, 2.5, 0.98, rng)
    stress = low + thirst
    rmssd = (
        profile.rmssd_base
        * np.exp(-0.04 * stress)
        * np.exp(-0.012 * activity)
        * np.where(asleep, 1.2, 1.0)
        * rng.lognormal(0, 0.15, minutes)
    )
    return HeartSignals(np.clip(heart_rate, 40, 190), np.clip(rmssd, 3, 150))


def cgm_readings(
    glucose: np.ndarray, profile: SignalProfile, rng: np.random.Generator, interval_min: int = 5
) -> tuple[np.ndarray, np.ndarray]:
    """Turn the twin's glucose into CGM readings: delayed, noisy, every 5 minutes, with gaps."""
    minutes = len(glucose) - 1
    sample = np.arange(int(rng.integers(0, interval_min)), minutes + 1, interval_min)
    delayed = glucose[np.clip(sample - profile.cgm_lag_min, 0, minutes)]
    noise = _ar1(len(sample), profile.cgm_noise_sd, 0.7, rng)
    values = np.clip(delayed * (1 + profile.cgm_bias) + noise, 40, 400)
    keep = rng.random(len(sample)) > 0.02
    for _ in range(rng.poisson(minutes / (3 * DAY))):
        gap_start = int(rng.integers(0, minutes))
        gap_length = int(rng.integers(30, 121))
        keep &= ~((sample >= gap_start) & (sample < gap_start + gap_length))
    return sample[keep], np.round(values[keep], 1)

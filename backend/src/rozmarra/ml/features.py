"""The features for the prediction models (docs/techstack.md, Section 7.1).

The same code builds features for synthetic and real patients. It uses only what a real
system would know at the time of the prediction: the CGM readings up to that time, the
smartwatch signals up to that time, the logged meals and doses, the fasting plan, the
health record and the estimated twin. Every twin forecast starts with the trend-matched
start (docs/techstack.md, Section 5.7).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from rozmarra.fasting.meals import FoodCategory
from rozmarra.ml.labels import find_events
from rozmarra.twin.medicines import Dose, Meal
from rozmarra.twin.model import (
    CENTRES,
    Forcing,
    calibrate_production,
    fasting_factor,
    secretagogue_effect,
    trend_matched_start,
)
from rozmarra.twin.simulate import TwinProfile, build_forcing, morning_inputs
from rozmarra.twin.solver import integrate

DAY = 1440
GRID = 5  # Wearable signals use a 5-minute grid.
TWIN_SAMPLES = 10
FAST_TYPES = ["none", "navratri", "karva_chauth", "ekadashi", "ramadan", "jain", "chhath", "custom"]
CATEGORY_CODES = {
    FoodCategory.FAST_ABSORBING: 0,
    FoodCategory.MIXED: 1,
    FoodCategory.SLOW_ABSORBING: 2,
}

# The feature groups, used for the ablation study (docs/techstack.md, Section 8).
CGM_FEATURES = [
    "cgm_now",
    "cgm_change_15",
    "cgm_change_30",
    "cgm_change_60",
    "cgm_slope_30",
    "cgm_min_2h",
    "cgm_sd_2h",
    "cgm_missing_2h",
    "cgm_tbr_24h",
]
HISTORY_FEATURES = [
    "hist_tbr_7d",
    "hist_cv_7d",
    "hist_lows_7d",
    "hist_tbr_14d",
    "hist_cv_14d",
    "hist_lows_14d",
    "hist_days",
]
TWIN_FEATURES = [
    "twin_30",
    "twin_60",
    "twin_120",
    "twin_60_p10",
    "twin_min_120",
    "twin_min_time",
    "twin_min_60",
    "twin_insulin",
    "twin_su_effect",
    "twin_carbs_absorbing",
    "twin_fasting_factor",
]
WEARABLE_FEATURES = [
    "hr_now",
    "hr_delta_from_usual",
    "hr_slope_30",
    "rmssd_ratio",
    "steps_last_30",
    "steps_last_60",
    "mets_now",
    "sleep_hours_24h",
]
CONTEXT_FEATURES = [
    "fast_type",
    "minutes_since_fast_start",
    "minutes_until_fast_end",
    "water_allowed",
    "minutes_since_last_meal",
    "last_meal_carbs",
]
RECORD_FEATURES = [
    "age",
    "sex_female",
    "bmi",
    "years_with_diabetes",
    "hba1c",
    "egfr",
    "takes_sulfonylurea",
    "takes_insulin",
    "takes_premixed",
    "takes_basal",
    "takes_metformin",
    "takes_sglt2",
    "takes_dpp4",
    "su_dose_ratio",
    "insulin_daily_units",
    "cyp2c9_activity",
    "hypo_history",
    "hypo_unaware",
    "beta_blocker",
    "heart_disease",
    "idf_dar_total",
]
E2_FEATURES = [
    "twin_peak_after_meal",
    "twin_peak_p90",
    "planned_carbs",
    "planned_category",
    "minutes_fasted_at_prediction",
]

GROUPS = {
    "cgm": CGM_FEATURES + HISTORY_FEATURES,
    "twin": TWIN_FEATURES,
    "wearables": WEARABLE_FEATURES,
    "context": CONTEXT_FEATURES,
    "record": RECORD_FEATURES,
}
ALL_POINT_FEATURES = [f for group in GROUPS.values() for f in group]


@dataclass
class Fast:
    start: int
    end: int
    fast_type: str
    water_allowed: bool
    breaking_minute: int | None


@dataclass
class PatientSeries:
    """Everything known about one patient, on a timeline in minutes from `start`."""

    patient_id: str
    start: pd.Timestamp
    minutes: int
    cgm_minutes: np.ndarray
    cgm_values: np.ndarray
    interval: int
    meals: list[Meal]
    doses: list[Dose]
    activities: list[tuple[int, int, float]]
    fasts: list[Fast]
    record: dict
    profile: TwinProfile
    wearables: dict[str, np.ndarray] = field(default_factory=dict)  # 5-minute grid arrays


# --- CGM and history features ------------------------------------------------------------


def _dense(minutes: np.ndarray, values: np.ndarray, step: int, length: int) -> np.ndarray:
    """Place readings on a regular grid. Each reading goes to the grid point at or after it,
    so that a prediction at a grid point never uses a reading from the future."""
    dense = np.full(length // step + 2, np.nan)
    index = np.clip(np.ceil(minutes / step).astype(int), 0, len(dense) - 1)
    dense[index] = values
    return dense


def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
    """The slope of a straight line through the readings in each window, per sample."""
    x = pd.Series(np.arange(len(series), dtype=float), index=series.index).where(series.notna())
    y = series
    n = y.notna().astype(float).rolling(window, min_periods=1).sum()
    sx = x.rolling(window, min_periods=1).sum()
    sy = y.rolling(window, min_periods=1).sum()
    sxy = (x * y).rolling(window, min_periods=1).sum()
    sxx = (x * x).rolling(window, min_periods=1).sum()
    denominator = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / denominator.replace(0, np.nan)
    return slope.where(n >= 2)


def cgm_features(ps: PatientSeries, points: np.ndarray) -> pd.DataFrame:
    step = ps.interval
    dense = _dense(ps.cgm_minutes, ps.cgm_values, step, ps.minutes)
    s = pd.Series(dense)
    present = s.notna().astype(float)

    def samples(minutes: int) -> int:
        return max(1, int(round(minutes / step)))

    w2h, w24, w7, w14 = samples(120), samples(DAY), samples(7 * DAY), samples(14 * DAY)
    low = (s < 70).astype(float).where(s.notna())
    events = find_events(ps.cgm_minutes, ps.cgm_values, step)
    event_counts = np.zeros(len(dense))
    for event in events:
        event_counts[min(len(dense) - 1, int(round(event.start / step)))] += 1
    event_counts = pd.Series(event_counts)

    def tbr(window):
        return (
            low.rolling(window, min_periods=1).sum() / present.rolling(window, min_periods=1).sum()
        )

    def cv(window):
        return s.rolling(window, min_periods=12).std() / s.rolling(window, min_periods=12).mean()

    # The current value may be up to one interval old, as in the label rule.
    now = s.ffill(limit=1)
    table = pd.DataFrame(
        {
            "cgm_now": now,
            "cgm_change_15": now - s.shift(samples(15)).ffill(limit=1),
            "cgm_change_30": now - s.shift(samples(30)).ffill(limit=1),
            "cgm_change_60": now - s.shift(samples(60)).ffill(limit=1),
            "cgm_slope_30": _rolling_slope(s, samples(30) + 1) / step,
            "cgm_min_2h": s.rolling(w2h, min_periods=1).min(),
            "cgm_sd_2h": s.rolling(w2h, min_periods=2).std(),
            "cgm_missing_2h": w2h - present.rolling(w2h, min_periods=1).sum(),
            "cgm_tbr_24h": tbr(w24),
            "hist_tbr_7d": tbr(w7),
            "hist_cv_7d": cv(w7),
            "hist_lows_7d": event_counts.rolling(w7, min_periods=1).sum(),
            "hist_tbr_14d": tbr(w14),
            "hist_cv_14d": cv(w14),
            "hist_lows_14d": event_counts.rolling(w14, min_periods=1).sum(),
        }
    )
    index = np.clip(np.floor(points / step).astype(int), 0, len(dense) - 1)
    out = table.iloc[index].reset_index(drop=True)
    first = ps.cgm_minutes[0] if len(ps.cgm_minutes) else 0
    out["hist_days"] = np.clip((points - first) / DAY, 0, 14)
    return out


# --- Wearable features -------------------------------------------------------------------


def _usual_by_time_of_day(values: np.ndarray) -> np.ndarray:
    """The median of the same 5-minute slot on the previous 7 days."""
    per_day = DAY // GRID
    days = int(np.ceil(len(values) / per_day))
    padded = np.full(days * per_day, np.nan)
    padded[: len(values)] = values
    grid = padded.reshape(days, per_day)
    usual = np.full_like(grid, np.nan)
    with warnings.catch_warnings():
        # Slots without any earlier value stay missing, which numpy reports as a warning.
        warnings.simplefilter("ignore", RuntimeWarning)
        for d in range(1, days):
            usual[d] = np.nanmedian(grid[max(0, d - 7) : d], axis=0)
    return usual.reshape(-1)[: len(values)]


def wearable_features(ps: PatientSeries, points: np.ndarray) -> pd.DataFrame:
    index = np.clip(points // GRID, 0, ps.minutes // GRID)
    out = pd.DataFrame(index=range(len(points)))
    hr = ps.wearables.get("heart_rate")
    if hr is not None and np.isfinite(hr).any():
        with np.errstate(all="ignore"):
            usual = _usual_by_time_of_day(hr)
        hr_s = pd.Series(hr)
        out["hr_now"] = hr[np.clip(index, 0, len(hr) - 1)]
        out["hr_delta_from_usual"] = (hr - usual)[np.clip(index, 0, len(hr) - 1)]
        out["hr_slope_30"] = ((hr_s - hr_s.shift(6)) / 30).to_numpy()[
            np.clip(index, 0, len(hr) - 1)
        ]
    rmssd = ps.wearables.get("hrv_rmssd")
    if rmssd is not None and np.isfinite(rmssd).any():
        with np.errstate(all="ignore"):
            usual = _usual_by_time_of_day(rmssd)
        out["rmssd_ratio"] = (rmssd / usual)[np.clip(index, 0, len(rmssd) - 1)]
    steps = ps.wearables.get("steps")
    if steps is not None and np.isfinite(steps).any():
        s = pd.Series(steps)
        i = np.clip(index, 0, len(steps) - 1)
        out["steps_last_30"] = s.rolling(6, min_periods=1).sum().to_numpy()[i]
        out["steps_last_60"] = s.rolling(12, min_periods=1).sum().to_numpy()[i]
    mets = ps.wearables.get("mets")
    if mets is not None and np.isfinite(mets).any():
        out["mets_now"] = mets[np.clip(index, 0, len(mets) - 1)]
    sleep = ps.wearables.get("asleep")
    if sleep is not None:
        s = pd.Series(sleep)
        out["sleep_hours_24h"] = (
            s.rolling(DAY // GRID, min_periods=1).sum() * GRID / 60
        ).to_numpy()[np.clip(index, 0, len(sleep) - 1)]
    for name in WEARABLE_FEATURES:
        if name not in out:
            out[name] = np.nan
    return out[WEARABLE_FEATURES]


# --- Fasting context ---------------------------------------------------------------------


def context_features(ps: PatientSeries, points: np.ndarray) -> pd.DataFrame:
    rows = []
    meal_minutes = np.array([m.minute for m in ps.meals]) if ps.meals else np.array([])
    meal_carbs = np.array([m.carbs_g for m in ps.meals]) if ps.meals else np.array([])
    order = np.argsort(meal_minutes)
    meal_minutes, meal_carbs = meal_minutes[order], meal_carbs[order]
    for t in points:
        fast = next((f for f in ps.fasts if f.start <= t <= f.end), None)
        i = np.searchsorted(meal_minutes, t, side="right") - 1
        rows.append(
            (
                FAST_TYPES.index(fast.fast_type) if fast else 0,
                t - fast.start if fast else np.nan,
                fast.end - t if fast else np.nan,
                float(fast.water_allowed) if fast else np.nan,
                t - meal_minutes[i] if i >= 0 else np.nan,
                meal_carbs[i] if i >= 0 else np.nan,
            )
        )
    return pd.DataFrame(rows, columns=CONTEXT_FEATURES)


# --- Twin forecasts ----------------------------------------------------------------------


class TwinForecaster:
    """Runs the estimated twin from many start points of one patient in one batch."""

    def __init__(self, ps: PatientSeries, samples: int = TWIN_SAMPLES, seed: int = 2026):
        self.ps = ps
        rng = np.random.default_rng(seed)
        values = ps.profile.sample(samples, rng)
        self.samples = samples
        mets = np.full(ps.minutes, 1.2)
        for a, b, level in ps.activities:
            mets[max(0, a) : min(ps.minutes, b)] = level
        self.forcing = build_forcing(
            ps.meals,
            ps.doses,
            ps.minutes,
            ps.profile.body_weight,
            ps.profile.cyp_factor,
            mets,
            values["k_abs_factor"],
            values["meal_factor"],
        )
        self.p = ps.profile.parameters(values)
        mornings = [d * DAY + 7 * 60 for d in range(1, max(2, ps.minutes // DAY))]
        mornings = [m for m in mornings if m < ps.minutes] or [min(7 * 60, ps.minutes - 1)]
        columns = [morning_inputs(self.forcing, m) for m in mornings]
        morning = tuple(
            np.median(np.stack([np.broadcast_to(c[i], (samples,)) for c in columns]), axis=0)
            for i in range(8)
        )
        self.p = calibrate_production(self.p, morning)

    def run(
        self, starts: np.ndarray, glucose: np.ndarray, slope: np.ndarray, horizon: int
    ) -> np.ndarray:
        """Return the forecasts with the shape (points, samples, horizon + 1)."""
        P, K = len(starts), self.samples
        starts = np.clip(starts, 0, self.ps.minutes - horizon - 1)
        index = starts[:, None] + np.arange(horizon)[None, :]
        shared = Forcing(
            *(
                np.broadcast_to(getattr(self.forcing, n), (K, self.ps.minutes))
                if getattr(self.forcing, n).ndim == 1
                else getattr(self.forcing, n)
                for n in Forcing.FIELDS
            )
        )
        batch = Forcing(
            *(
                getattr(shared, n)[:, index].transpose(1, 0, 2).reshape(P * K, horizon)
                for n in Forcing.FIELDS
            )
        )
        p = _repeat_points(self.p, P)
        g0 = np.repeat(glucose, K)
        s0 = np.repeat(np.nan_to_num(slope), K)
        start_state = trend_matched_start(p, g0, s0, batch.column(0))
        G = integrate(*start_state, p, batch).G
        self.last_insulin = start_state[2].reshape(P, K)[:, 0]
        return G.reshape(P, K, horizon + 1)

    def inputs_at(self, minutes: np.ndarray) -> dict[str, np.ndarray]:
        m = np.clip(minutes, 0, self.ps.minutes - 1)
        ahead = np.clip(m[:, None] + np.arange(0, 360, 5)[None, :], 0, self.ps.minutes - 1)
        ra = np.atleast_2d(self.forcing.ra)[0]
        return {
            "twin_su_effect": secretagogue_effect(self.forcing.secretagogue[m]),
            "twin_carbs_absorbing": ra[ahead].sum(axis=1) * 5,
            "twin_fasting_factor": fasting_factor(self.forcing.since_meal[m]),
        }


def _repeat_points(p, copies: int):
    """Order the batch as point-major: each point has its K samples next to each other."""
    from rozmarra.twin.model import Parameters

    values = {}
    for name in (
        "G_b",
        "I_b",
        "body_weight",
        "renal_factor",
        "S_G",
        "S_I",
        "beta",
        "k_abs_factor",
        "meal_factor",
        "gamma_su",
        "cr_factor",
        "P0",
    ):
        array = np.atleast_1d(getattr(p, name))
        values[name] = np.tile(array, copies) if len(array) > 1 else array
    P0 = values.pop("P0")
    return Parameters(**values, k_hgp=p.k_hgp, a_f=p.a_f, P0=P0)


def twin_features(
    forecaster: TwinForecaster, points: np.ndarray, cgm: pd.DataFrame
) -> pd.DataFrame:
    glucose = cgm["cgm_now"].to_numpy()
    usable = np.isfinite(glucose)
    out = pd.DataFrame(np.nan, index=range(len(points)), columns=TWIN_FEATURES)
    if not usable.any():
        return out
    G = forecaster.run(points[usable], glucose[usable], cgm["cgm_slope_30"].to_numpy()[usable], 120)
    mean = G[:, 0, :]
    out.loc[usable, "twin_30"] = mean[:, 30]
    out.loc[usable, "twin_60"] = mean[:, 60]
    out.loc[usable, "twin_120"] = mean[:, 120]
    out.loc[usable, "twin_60_p10"] = np.percentile(G[:, :, 60], 10, axis=1)
    out.loc[usable, "twin_min_120"] = mean.min(axis=1)
    out.loc[usable, "twin_min_60"] = mean[:, :61].min(axis=1)
    out.loc[usable, "twin_min_time"] = mean.argmin(axis=1)
    out.loc[usable, "twin_insulin"] = forecaster.last_insulin
    for name, values in forecaster.inputs_at(points).items():
        out[name] = values
    return out


def record_frame(ps: PatientSeries, count: int) -> pd.DataFrame:
    return pd.DataFrame([{name: ps.record.get(name, np.nan) for name in RECORD_FEATURES}] * count)


def point_features(
    ps: PatientSeries, points: np.ndarray, forecaster: TwinForecaster | None = None
) -> pd.DataFrame:
    """All point features (CGM, history, twin, wearables, context and record)."""
    points = np.asarray(points, dtype=int)
    cgm = cgm_features(ps, points)
    forecaster = forecaster or TwinForecaster(ps)
    parts = [
        cgm,
        twin_features(forecaster, points, cgm),
        wearable_features(ps, points),
        context_features(ps, points),
        record_frame(ps, len(points)),
    ]
    table = pd.concat(parts, axis=1)
    return table[ALL_POINT_FEATURES].astype(float)


def breaking_meal_features(ps: PatientSeries, forecaster: TwinForecaster | None = None):
    """E2 features for each meal that breaks a fast, at 2 hours before the meal."""
    fasts = [f for f in ps.fasts if f.breaking_minute is not None]
    if not fasts:
        return pd.DataFrame(columns=ALL_POINT_FEATURES + E2_FEATURES)
    forecaster = forecaster or TwinForecaster(ps)
    meals = {int(round(m.minute)): m for m in ps.meals}
    predictions = np.array([f.breaking_minute - 120 for f in fasts], dtype=int)
    table = point_features(ps, predictions, forecaster)
    cgm = table[["cgm_now", "cgm_slope_30"]]
    glucose = cgm["cgm_now"].fillna(ps.profile.G_b).to_numpy()
    G = forecaster.run(predictions, glucose, cgm["cgm_slope_30"].to_numpy(), 360)
    peaks = G[:, :, 120:].max(axis=2)
    extra = []
    for i, fast in enumerate(fasts):
        meal = meals.get(fast.breaking_minute) or min(
            ps.meals, key=lambda m: abs(m.minute - fast.breaking_minute)
        )
        extra.append(
            {
                "twin_peak_after_meal": peaks[i, 0],
                "twin_peak_p90": np.percentile(peaks[i], 90),
                "planned_carbs": meal.carbs_g,
                "planned_category": CATEGORY_CODES[meal.category],
                "minutes_fasted_at_prediction": predictions[i] - fast.start,
            }
        )
    return pd.concat([table.reset_index(drop=True), pd.DataFrame(extra)], axis=1)


def profile_from_values(values: dict, fixed: dict) -> TwinProfile:
    """Build an estimated twin profile from stored values (for example a table row)."""
    from rozmarra.twin.model import FITTED_NAMES

    names = FITTED_NAMES
    mean = np.log([values.get(n, CENTRES[n]) for n in names])
    cov = np.asarray(fixed.get("log_cov", np.zeros((len(names), len(names)))))
    return TwinProfile(
        fixed["G_b"],
        fixed["I_b"],
        fixed["body_weight"],
        fixed["egfr"],
        fixed.get("cr_factor", 1.0),
        fixed.get("cyp_factor", 1.0),
        names,
        mean,
        cov,
        fixed.get("source", "estimated"),
    )

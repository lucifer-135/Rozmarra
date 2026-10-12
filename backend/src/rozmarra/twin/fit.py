"""Fitting a twin to each real patient (docs/techstack.md, Section 5.6).

- Data: the first 70% of each patient's days are used for fitting, and the last 30%
  are held back for testing.
- Method: maximum a posteriori estimation with scipy.optimize.least_squares. Log-normal
  priors keep each parameter close to its population value.
- Safety weights: the squared error is multiplied by 3 when the measured glucose is
  below 70 mg/dL and the twin is higher, and when the measured glucose is above
  250 mg/dL and the twin is lower. This idea comes from the T2DSim AI project.
- Slope matching: the fit also compares the change between consecutive readings in the
  simulation and in the CGM data, with the same weight of 3. This idea also comes from
  the T2DSim AI project.
- Windows: the fit works in 12-hour windows. Each window starts at the measured CGM
  value with a trend-matched start, so that errors do not build up over many hours.
- Uncertainty: the covariance of the log parameters comes from the Jacobian of the fit
  (a Laplace approximation).

The forecasts in the fit report use the meals and doses recorded in the data, in the
same way that a fasting plan provides them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import time

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from rozmarra.fasting.meals import FoodCategory
from rozmarra.medicines import MedicineClass, get_medicine
from rozmarra.twin import model
from rozmarra.twin.medicines import Dose, Meal, meal_appearance
from rozmarra.twin.model import FITTED, Parameters
from rozmarra.twin.simulate import build_forcing
from rozmarra.twin.solver import integrate

WINDOW_MIN = 720
WINDOW_STARTS = (time(6, 0), time(18, 0))
FIT_SHARE = 0.7
MIN_COMPLETENESS = 0.7
SIGMA_MG_DL = 15.0  # The typical size of an error of the model and the sensor
SAFETY_WEIGHT = 3.0
SLOPE_WEIGHT = 3.0
LOW, HIGH = 70.0, 250.0
FORECAST_HORIZONS = (30, 60, 120)
FORECAST_EVERY_MIN = 60
DEFAULT_MEAL_CARBS_G = 40.0
MORNING = time(7, 0)


@dataclass
class PatientData:
    patient_id: str
    dataset: str
    start: pd.Timestamp  # The time of minute 0
    minutes: int
    cgm_minute: np.ndarray
    cgm_value: np.ndarray
    interval_min: int
    meals: list[Meal]
    doses: list[Dose]
    mets: np.ndarray
    body_weight: float
    I_b: float
    egfr: float
    cr_factor: float
    fasting_glucose: float | None
    split_minute: int = 0

    @property
    def takes_secretagogue(self) -> bool:
        return any(
            get_medicine(d.name).medicine_class
            in {MedicineClass.SULFONYLUREA, MedicineClass.GLINIDE}
            for d in self.doses
        )

    def minute_of(self, moment: pd.Timestamp) -> int:
        return int(round((moment - self.start) / pd.Timedelta(minutes=1)))

    def clock_minutes(self, clock: time) -> list[int]:
        """The minute index of a clock time on every day of the timeline."""
        first = self.start.normalize()
        days = int(self.minutes // 1440) + 2
        offsets = [
            self.minute_of(first + pd.Timedelta(days=d, hours=clock.hour, minutes=clock.minute))
            for d in range(days)
        ]
        return [m for m in offsets if 0 <= m < self.minutes]


@dataclass
class Windows:
    starts: np.ndarray  # (W,) minute of each window start
    g0: np.ndarray  # (W,) CGM value at the start
    slope: np.ndarray  # (W,) CGM trend over the last 30 minutes, mg/dL per minute
    offsets: np.ndarray  # (W, R) minutes after the start of each reading, padded
    values: np.ndarray  # (W, R) measured readings, padded
    mask: np.ndarray  # (W, R) True for real readings
    length: int

    def __len__(self) -> int:
        return len(self.starts)


@dataclass
class TwinFit:
    patient_id: str
    dataset: str
    G_b: float
    I_b: float
    body_weight: float
    egfr: float
    cr_factor: float
    takes_secretagogue: bool
    fitted_names: list[str]
    fitted: dict[str, float]
    log_mean: list[float]
    log_cov: list[list[float]]
    metrics: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return self.__dict__.copy()


# --- Loading the data of one patient -----------------------------------------------------


def meal_category(details: dict) -> FoodCategory:
    """Choose a food category from the nutrients, when they are known (an assumption)."""
    carbs = details.get("carbs_g") or 0
    other = (details.get("fat_g") or 0) + (details.get("protein_g") or 0)
    other += 2 * (details.get("fiber_g") or 0)
    if carbs <= 0 or "fat_g" not in details:
        return FoodCategory.MIXED
    ratio = other / carbs
    if ratio < 0.3:
        return FoodCategory.FAST_ABSORBING
    if ratio > 1.0:
        return FoodCategory.SLOW_ABSORBING
    return FoodCategory.MIXED


def load_patient(
    patient: pd.Series, timeseries: pd.DataFrame, events: pd.DataFrame
) -> PatientData | None:
    pid = patient["patient_id"]
    cgm = timeseries[(timeseries["patient_id"] == pid) & (timeseries["signal"] == "glucose_cgm")]
    cgm = cgm.sort_values("timestamp_local")
    if len(cgm) < 100:
        return None
    start = cgm["timestamp_local"].iloc[0].floor("h")
    end = cgm["timestamp_local"].iloc[-1]
    minutes = int((end - start) / pd.Timedelta(minutes=1)) + 1
    cgm_minute = ((cgm["timestamp_local"] - start) / pd.Timedelta(minutes=1)).round().astype(int)
    interval = int(np.median(np.diff(cgm_minute.to_numpy())))

    patient_events = events[events["patient_id"] == pid]
    details = patient_events["details"].map(json.loads)
    event_minutes = ((patient_events["start"] - start) / pd.Timedelta(minutes=1)).to_numpy()
    recorded = [
        d.get("carbs_g")
        for d, t in zip(details, patient_events["event_type"], strict=True)
        if t == "meal" and d.get("carbs_g")
    ]
    default_carbs = float(np.median(recorded)) if len(recorded) >= 3 else DEFAULT_MEAL_CARBS_G

    meals, doses = [], []
    for minute, kind, d in zip(event_minutes, patient_events["event_type"], details, strict=True):
        if kind == "meal":
            carbs = d.get("carbs_g")
            meals.append(
                Meal(float(minute), float(carbs if carbs else default_carbs), meal_category(d))
            )
        elif kind in {"insulin", "medicine"} and d.get("route") in {"subcutaneous", "oral"}:
            doses.append(Dose(float(minute), d["name"], float(d["dose"])))

    mets = np.ones(minutes)
    activity = timeseries[(timeseries["patient_id"] == pid) & (timeseries["signal"] == "mets")]
    if len(activity):
        idx = ((activity["timestamp_local"] - start) / pd.Timedelta(minutes=1)).round().astype(int)
        for minute, value in zip(idx, activity["value"], strict=True):
            if 0 <= minute < minutes:
                mets[minute : minute + 5] = value

    def number(name: str, default: float) -> float:
        value = patient.get(name)
        return default if value is None or pd.isna(value) else float(value)

    years = number("years_with_diabetes", 0.0)
    data = PatientData(
        patient_id=pid,
        dataset=str(patient["dataset"]),
        start=start,
        minutes=minutes,
        cgm_minute=cgm_minute.to_numpy(),
        cgm_value=cgm["value"].to_numpy(dtype=float),
        interval_min=interval,
        meals=meals,
        doses=doses,
        mets=mets,
        body_weight=number("weight_kg", 65.0),
        I_b=float(np.clip(number("fasting_insulin_uu_ml", model.I_B_DEFAULT), *model.I_B_RANGE)),
        egfr=number("egfr", 90.0),
        cr_factor=model.CR_REDUCED if years > 15 else 1.0,
        fasting_glucose=number("fasting_glucose_mg_dl", float("nan")),
    )
    days = sorted({(start + pd.Timedelta(minutes=int(m))).date() for m in data.cgm_minute})
    n_fit = int(np.ceil(FIT_SHARE * len(days)))
    first_test_day = days[min(n_fit, len(days) - 1)]
    data.split_minute = data.minute_of(pd.Timestamp(first_test_day))
    return data


def baseline_glucose(data: PatientData) -> float:
    """The fasting level G_b: the median CGM value from 5:00 am to 7:00 am on fitting days."""
    times = data.start + pd.to_timedelta(data.cgm_minute, unit="min")
    hours = times.hour
    early = (hours >= 5) & (hours < 7) & (data.cgm_minute < data.split_minute)
    if early.sum() >= 4:
        return float(np.median(data.cgm_value[early]))
    if data.fasting_glucose and not np.isnan(data.fasting_glucose):
        return float(data.fasting_glucose)
    return float(np.median(data.cgm_value))


# --- Windows and forecasts ---------------------------------------------------------------


def trend(data: PatientData, minute: int) -> tuple[float, float] | None:
    """The CGM value at a minute and the slope of a straight line through the last 30 minutes."""
    near = (data.cgm_minute >= minute - 30) & (data.cgm_minute <= minute)
    if near.sum() < 2 or minute not in set(data.cgm_minute[near]):
        return None
    t, g = data.cgm_minute[near], data.cgm_value[near]
    slope = float(np.polyfit(t, g, 1)[0])
    return float(g[t == minute][0]), slope


def make_windows(data: PatientData, starts: list[int], length: int) -> Windows:
    rows = []
    expected = length / data.interval_min
    for nominal in starts:
        candidates = data.cgm_minute[
            (data.cgm_minute >= nominal) & (data.cgm_minute < nominal + 2 * data.interval_min)
        ]
        if len(candidates) == 0:
            continue
        start = int(candidates[0])
        if start + length >= data.minutes:
            continue
        state = trend(data, start)
        if state is None:
            continue
        inside = (data.cgm_minute > start) & (data.cgm_minute <= start + length)
        if inside.sum() < MIN_COMPLETENESS * expected:
            continue
        rows.append((start, *state, data.cgm_minute[inside] - start, data.cgm_value[inside]))
    width = max((len(r[3]) for r in rows), default=0)
    offsets = np.zeros((len(rows), width), dtype=int)
    values = np.zeros((len(rows), width))
    mask = np.zeros((len(rows), width), dtype=bool)
    for i, (_, _, _, off, val) in enumerate(rows):
        offsets[i, : len(off)], values[i, : len(val)], mask[i, : len(off)] = off, val, True
    return Windows(
        starts=np.array([r[0] for r in rows], dtype=int),
        g0=np.array([r[1] for r in rows]),
        slope=np.array([r[2] for r in rows]),
        offsets=offsets,
        values=values,
        mask=mask,
        length=length,
    )


def fitting_windows(data: PatientData, test: bool = False) -> Windows:
    nominal = sorted(m for clock in WINDOW_STARTS for m in data.clock_minutes(clock))
    if test:
        chosen = [m for m in nominal if m >= data.split_minute]
    else:
        chosen = [m for m in nominal if m + WINDOW_MIN <= data.split_minute]
    return make_windows(data, chosen, WINDOW_MIN)


def forecast_windows(data: PatientData) -> Windows:
    """Forecast start points every hour on the held-out days, 120 minutes long."""
    starts = list(
        range(data.split_minute, data.minutes - max(FORECAST_HORIZONS), FORECAST_EVERY_MIN)
    )
    return make_windows(data, starts, max(FORECAST_HORIZONS))


# --- Simulating batches of windows -------------------------------------------------------


class WindowSimulator:
    """Runs K parameter sets on W windows of one patient in a single batch."""

    def __init__(self, data: PatientData, base: Parameters, cyp_factor: float = 1.0):
        self.data = data
        self.base = base
        self.forcing = build_forcing(
            data.meals, data.doses, data.minutes, data.body_weight, cyp_factor, data.mets
        )
        # The meal input depends on the fitted parameters, so run() recalculates it.
        self.forcing.ra = self.forcing.ra[0]
        mornings = [m for m in data.clock_minutes(MORNING) if m < max(data.split_minute, 1)]
        mornings = mornings or data.clock_minutes(MORNING)[:1] or [0]
        columns = [self.forcing.column(m) for m in mornings]
        morning = [np.median([np.atleast_1d(c[i])[0] for c in columns]) for i in range(8)]
        morning[0], morning[6] = 0.0, 1.0  # No meal is absorbing, and the patient is at rest.
        self.morning = tuple(np.array([v]) for v in morning)

    def parameters(self, values: dict[str, np.ndarray]) -> Parameters:
        return model.calibrate_production(self.base.with_fitted(values), self.morning)

    def run(self, values: dict[str, np.ndarray], windows: Windows) -> np.ndarray:
        """Return simulated glucose with the shape (K, W, L + 1)."""
        p = self.parameters(values)
        K, W = len(p.P0), len(windows)
        ra = meal_appearance(
            self.data.meals, self.data.minutes, self.data.body_weight, p.k_abs_factor, p.meal_factor
        )
        index = windows.starts[:, None] + np.arange(windows.length)[None, :]
        shared = self.forcing.windows(windows.starts, windows.length).tiled(K)
        shared.ra = ra[:, index].reshape(K * W, windows.length)
        batch = repeat_parameters(p, W)
        g0 = np.tile(windows.g0, K)
        slope = np.tile(windows.slope, K)
        start = model.trend_matched_start(batch, g0, slope, shared.column(0))
        G = integrate(*start, batch, shared).G
        return G.reshape(K, W, windows.length + 1)


def repeat_parameters(p: Parameters, copies: int) -> Parameters:
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
        values[name] = np.repeat(array, copies) if len(array) > 1 else array
    return Parameters(
        **{k: v for k, v in values.items() if k != "P0"}, k_hgp=p.k_hgp, a_f=p.a_f, P0=values["P0"]
    )


def simulated_at_readings(G: np.ndarray, windows: Windows) -> np.ndarray:
    """Pick the simulated value at each reading. The result has the shape (K, W, R)."""
    return np.take_along_axis(
        G, np.broadcast_to(windows.offsets, G.shape[:1] + windows.offsets.shape), axis=2
    )


def error_metrics(simulated: np.ndarray, windows: Windows) -> dict:
    error = (simulated - windows.values)[windows.mask]
    measured = windows.values[windows.mask]
    if len(error) == 0:
        return {"rmse_mg_dl": None, "mard_percent": None, "readings": 0}
    return {
        "rmse_mg_dl": round(float(np.sqrt(np.mean(error**2))), 1),
        "mard_percent": round(float(np.mean(np.abs(error) / measured) * 100), 1),
        "readings": int(len(error)),
    }


# --- The fit -----------------------------------------------------------------------------


@dataclass
class FitProblem:
    simulator: WindowSimulator
    windows: Windows
    names: list[str]
    centre: np.ndarray
    sd: np.ndarray
    low: np.ndarray
    high: np.ndarray

    def values(self, thetas: np.ndarray) -> dict[str, np.ndarray]:
        return {name: np.exp(thetas[:, i]) for i, name in enumerate(self.names)}

    def residuals(self, thetas: np.ndarray) -> np.ndarray:
        """Residuals for K parameter sets, with the shape (K, R)."""
        thetas = np.atleast_2d(thetas)
        G = self.simulator.run(self.values(thetas), self.windows)
        sim = simulated_at_readings(G, self.windows)
        obs = self.windows.values[None]
        error = sim - obs
        weight = np.ones_like(error)
        weight[(obs < LOW) & (error > 0)] = SAFETY_WEIGHT
        weight[(obs > HIGH) & (error < 0)] = SAFETY_WEIGHT
        level = (np.sqrt(weight) * error / SIGMA_MG_DL)[:, self.windows.mask]
        pair = self.windows.mask[:, 1:] & self.windows.mask[:, :-1]
        slope_error = np.diff(sim, axis=2) - np.diff(obs, axis=2)
        slope = (np.sqrt(SLOPE_WEIGHT) * slope_error / SIGMA_MG_DL)[:, pair]
        prior = (thetas - self.centre) / self.sd
        return np.concatenate([level, slope, prior], axis=1)

    def fun(self, theta: np.ndarray) -> np.ndarray:
        return self.residuals(theta[None])[0]

    def jac(self, theta: np.ndarray) -> np.ndarray:
        step = 1e-4
        thetas = np.vstack([theta, theta + step * np.eye(len(theta))])
        r = self.residuals(thetas)
        return ((r[1:] - r[0]) / step).T


def build_problem(data: PatientData) -> FitProblem:
    base = Parameters(
        G_b=baseline_glucose(data),
        I_b=data.I_b,
        body_weight=data.body_weight,
        renal_factor=min(data.egfr / 90.0, 1.0),
        cr_factor=data.cr_factor,
    )
    simulator = WindowSimulator(data, base)
    chosen = [p for p in FITTED if p.name != "gamma_su" or data.takes_secretagogue]
    sd = []
    for p in chosen:
        # Meals in CGMacros have recorded carbohydrates, so the meal-size factor stays closer to 1.
        sd.append(0.15 if p.name == "meal_factor" and data.dataset == "CGMacros" else p.log_sd)
    return FitProblem(
        simulator=simulator,
        windows=fitting_windows(data),
        names=[p.name for p in chosen],
        centre=np.log([p.centre for p in chosen]),
        sd=np.array(sd),
        low=np.log([p.low for p in chosen]),
        high=np.log([p.high for p in chosen]),
    )


def fit_patient(data: PatientData, max_evaluations: int = 30) -> TwinFit | None:
    problem = build_problem(data)
    if len(problem.windows) < 2:
        return None
    result = least_squares(
        problem.fun,
        problem.centre.copy(),
        jac=problem.jac,
        bounds=(problem.low, problem.high),
        x_scale=problem.sd,
        max_nfev=max_evaluations,
        method="trf",
    )
    theta = result.x
    J = result.jac
    dof = max(len(result.fun) - len(theta), 1)
    scale = 2 * result.cost / dof
    cov = np.linalg.pinv(J.T @ J) * scale
    # The uncertainty of a parameter is never larger than its prior uncertainty.
    sd = np.minimum(np.sqrt(np.clip(np.diag(cov), 1e-12, None)), problem.sd)
    corr = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)).clip(1e-24))
    cov = corr * np.outer(sd, sd)

    values = {name: float(np.exp(theta[i])) for i, name in enumerate(problem.names)}
    fit = TwinFit(
        patient_id=data.patient_id,
        dataset=data.dataset,
        G_b=round(float(problem.simulator.base.G_b[0]), 1),
        I_b=round(data.I_b, 1),
        body_weight=round(data.body_weight, 1),
        egfr=round(data.egfr, 1),
        cr_factor=data.cr_factor,
        takes_secretagogue=data.takes_secretagogue,
        fitted_names=problem.names,
        fitted=values,
        log_mean=theta.tolist(),
        log_cov=cov.tolist(),
    )
    fit.metrics = evaluate_fit(data, problem, values)
    fit.metrics["optimiser_evaluations"] = int(result.nfev)
    return fit


def evaluate_fit(data: PatientData, problem: FitProblem, values: dict[str, float]) -> dict:
    simulator = problem.simulator
    arrays = {k: np.array([v]) for k, v in values.items()}
    metrics: dict = {"fit_windows": len(problem.windows)}
    fit_sim = simulated_at_readings(simulator.run(arrays, problem.windows), problem.windows)[0]
    metrics["fit"] = error_metrics(fit_sim, problem.windows)

    test = fitting_windows(data, test=True)
    metrics["test_windows"] = len(test)
    if len(test):
        test_sim = simulated_at_readings(simulator.run(arrays, test), test)[0]
        metrics["test"] = error_metrics(test_sim, test)
        lows = (test.values < LOW) & test.mask
        metrics["test_windows_with_low"] = int(lows.any(axis=1).sum())
        metrics["test_windows_with_low_where_twin_shows_low"] = int(
            (lows.any(axis=1) & ((test_sim < LOW) & test.mask).any(axis=1)).sum()
        )

    forecasts = forecast_windows(data)
    metrics["forecast_starts"] = len(forecasts)
    if len(forecasts):
        G = simulator.run(arrays, forecasts)[0]
        result = {}
        for horizon in FORECAST_HORIZONS:
            hit = (forecasts.offsets == horizon) & forecasts.mask
            rows, cols = np.nonzero(hit)
            if len(rows) == 0:
                continue
            measured = forecasts.values[rows, cols]
            twin = G[rows, horizon]
            last = forecasts.g0[rows]
            line = np.clip(forecasts.g0[rows] + forecasts.slope[rows] * horizon, 40, 400)
            result[str(horizon)] = {
                "twin": rmse(twin - measured),
                "last_value": rmse(last - measured),
                "straight_line": rmse(line - measured),
                "count": int(len(rows)),
            }
        metrics["forecast_rmse_mg_dl"] = result
    return metrics


def rmse(error: np.ndarray) -> float:
    return round(float(np.sqrt(np.mean(np.square(error)))), 1)

"""Running the twin: building the inputs and simulating a timeline or a fasting plan.

A fasting plan simulation starts one usual day before the plan, so that the medicine
and insulin levels at the start of the fast are realistic. The usual day uses the
patient's usual medicines and a usual Indian meal routine. Liver glucose production
is calibrated on that usual day, so a change in the plan, such as a lower dose,
changes the result in the way the doctor expects.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta

import numpy as np

from rozmarra.fasting.meals import FoodCategory
from rozmarra.fasting.plan import FastingPlan
from rozmarra.fasting.templates import UsualDose
from rozmarra.twin.medicines import (
    Dose,
    Meal,
    insulin_appearance,
    meal_appearance,
    medicine_activity,
    minutes_since_last_meal,
)
from rozmarra.twin.model import (
    CENTRES,
    F_ABSORBED,
    FITTED,
    FITTED_NAMES,
    I_B_RANGE,
    V_G,
    Forcing,
    Parameters,
    calibrate_production,
    steady_start,
)
from rozmarra.twin.solver import integrate

WARMUP_MIN = 1440
# Usual doses on the two days before the timeline still act at its start.
HISTORY_DAYS = 2
BAND_SAMPLES = 100
# A usual Indian daily routine for the day before the plan. These are starting values.
USUAL_MEALS = (
    (time(8, 30), 50.0, FoodCategory.MIXED),
    (time(13, 30), 70.0, FoodCategory.MIXED),
    (time(17, 0), 20.0, FoodCategory.FAST_ABSORBING),
    (time(20, 30), 70.0, FoodCategory.MIXED),
)
MORNING_TEST = time(7, 0)


def build_forcing(
    meals: Iterable[Meal],
    doses: Iterable[Dose],
    minutes: int,
    body_weight: float,
    cyp_clearance_factor: float = 1.0,
    mets: np.ndarray | None = None,
    k_abs_factor: np.ndarray | float = 1.0,
    meal_factor: np.ndarray | float = 1.0,
    before_start_min: float = 600,
) -> Forcing:
    """Build the inputs for one timeline. The meal input has one row for each parameter set."""
    meals = list(meals)
    doses = list(doses)
    activity = medicine_activity(doses, minutes, cyp_clearance_factor)
    ra = meal_appearance(
        meals,
        minutes,
        body_weight,
        np.atleast_1d(k_abs_factor),
        np.atleast_1d(meal_factor),
        F_ABSORBED,
        V_G,
    )
    return Forcing(
        ra=ra,
        ri=insulin_appearance(doses, minutes),
        secretagogue=activity.secretagogue,
        metformin=activity.metformin,
        dpp4=activity.dpp4,
        sglt2=activity.sglt2,
        mets=np.ones(minutes) if mets is None else np.asarray(mets, dtype=float),
        since_meal=minutes_since_last_meal(meals, minutes, before_start_min),
    )


def percentile_band(
    samples: np.ndarray, percentiles: Sequence[float] = (10, 50, 90)
) -> dict[int, np.ndarray]:
    """The percentiles of simulated glucose across parameter samples, for each minute."""
    values = np.percentile(samples, percentiles, axis=0)
    return {int(p): values[i] for i, p in enumerate(percentiles)}


def morning_inputs(forcing: Forcing, minute: int) -> tuple[np.ndarray, ...]:
    """The inputs at a usual morning minute, used to calibrate P0."""
    inputs = list(forcing.column(minute))
    inputs[0] = np.zeros_like(np.atleast_1d(inputs[0]))  # No meal is absorbing.
    inputs[6] = np.ones_like(np.atleast_1d(inputs[6]))  # The patient is at rest.
    return tuple(inputs)


def population_parameters(
    G_b: float, I_b: float, body_weight: float, egfr: float, cr_factor: float = 1.0, **fitted
) -> Parameters:
    return Parameters(
        G_b=G_b,
        I_b=I_b,
        body_weight=body_weight,
        renal_factor=min(egfr / 90.0, 1.0),
        cr_factor=cr_factor,
        **fitted,
    )


_BOUNDS = {p.name: (np.log(p.low), np.log(p.high)) for p in FITTED}


@dataclass
class TwinProfile:
    """What the simulator needs to know about one patient's twin.

    The fitted parameters are described on the log scale by a mean and a covariance.
    The first parameter sample is always the mean, which is the most likely twin.
    """

    G_b: float
    I_b: float
    body_weight: float
    egfr: float
    cr_factor: float
    cyp_factor: float
    names: tuple[str, ...]
    log_mean: np.ndarray
    log_cov: np.ndarray
    source: str = "population"

    @classmethod
    def population(cls, G_b, I_b, body_weight, egfr, cr_factor=1.0, cyp_factor=1.0):
        return cls(
            G_b=float(G_b),
            I_b=float(np.clip(I_b, *I_B_RANGE)),
            body_weight=float(body_weight),
            egfr=float(egfr),
            cr_factor=float(cr_factor),
            cyp_factor=float(cyp_factor),
            names=FITTED_NAMES,
            log_mean=np.log([CENTRES[n] for n in FITTED_NAMES]),
            log_cov=np.diag([p.log_sd**2 for p in FITTED]),
        )

    def with_parameters(self, values: dict[str, float], log_cov=None, source: str = "fitted"):
        """A copy of the profile with other fitted parameters, for example the average patient."""
        mean = np.array([np.log(values.get(n, CENTRES[n])) for n in self.names])
        cov = np.zeros((len(self.names), len(self.names))) if log_cov is None else log_cov
        return TwinProfile(
            self.G_b,
            self.I_b,
            self.body_weight,
            self.egfr,
            self.cr_factor,
            self.cyp_factor,
            self.names,
            mean,
            np.asarray(cov),
            source,
        )

    def sample(self, count: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
        draws = rng.multivariate_normal(
            self.log_mean, self.log_cov, size=count, check_valid="ignore", method="eigh"
        )
        draws[0] = self.log_mean
        for i, name in enumerate(self.names):
            low, high = _BOUNDS[name]
            draws[:, i] = np.clip(draws[:, i], low, high)
        return {name: np.exp(draws[:, i]) for i, name in enumerate(self.names)}

    def parameters(self, values: dict[str, np.ndarray]) -> Parameters:
        return population_parameters(
            self.G_b, self.I_b, self.body_weight, self.egfr, self.cr_factor, **values
        )


@dataclass
class PlanSimulation:
    """The result of simulating a fasting plan. Every array has one value for each minute."""

    start: datetime  # The time of the first value, which is the start of the plan window
    point: np.ndarray  # The most likely twin
    p10: np.ndarray
    p50: np.ndarray
    p90: np.ndarray
    average: np.ndarray | None  # The average patient with the same plan
    samples: int
    curves: np.ndarray | None = None  # Every sample curve, with the shape (samples, minutes)

    def time_at(self, minute: int) -> datetime:
        return self.start + timedelta(minutes=int(minute))

    @property
    def minutes(self) -> int:
        return len(self.point) - 1


def _days(first: datetime, last: datetime):
    day = first.date()
    while day <= last.date():
        yield day
        day += timedelta(days=1)


def plan_timeline(plan: FastingPlan, usual_doses: Iterable[UsualDose]):
    """Return the start, the length, the meals, the doses and the METs of a plan timeline."""
    t0 = (plan.window_start - timedelta(minutes=WARMUP_MIN)).replace(second=0, microsecond=0)
    minutes = int((plan.window_end - t0) / timedelta(minutes=1)) + 1

    def minute(moment: datetime) -> float:
        return (moment - t0) / timedelta(minutes=1)

    meals = [
        Meal(minute(datetime.combine(day, clock)), carbs, category)
        for day in _days(t0 - timedelta(days=1), plan.window_start)
        for clock, carbs, category in USUAL_MEALS
        if datetime.combine(day, clock) < plan.window_start
    ]
    meals += [Meal(minute(m.time), m.carbs_g, m.food_category) for m in plan.meals]

    doses = [
        Dose(minute(datetime.combine(day, usual.time)), usual.name, usual.dose)
        for day in _days(t0 - timedelta(days=HISTORY_DAYS), plan.window_start)
        for usual in usual_doses
        if datetime.combine(day, usual.time) < plan.window_start
    ]
    doses += [Dose(minute(d.time), d.name, d.dose) for d in plan.medicines]

    mets = np.ones(minutes)
    for activity in plan.activities:
        start, end = max(0, int(minute(activity.start))), min(minutes, int(minute(activity.end)))
        mets[start:end] = activity.mets

    morning = datetime.combine(t0.date(), MORNING_TEST)
    if morning < t0:
        morning += timedelta(days=1)
    return t0, minutes, meals, doses, mets, int(minute(morning))


def simulate_plan(
    plan: FastingPlan,
    profile: TwinProfile,
    usual_doses: Iterable[UsualDose],
    samples: int = BAND_SAMPLES,
    average: TwinProfile | None = None,
    seed: int = 2026,
    keep_curves: bool = False,
) -> PlanSimulation:
    """Simulate a fasting plan with an uncertainty band and, if given, the average patient."""
    t0, minutes, meals, doses, mets, morning = plan_timeline(plan, list(usual_doses))
    values = profile.sample(samples, np.random.default_rng(seed))
    if average is not None:
        extra = average.sample(1, np.random.default_rng(seed))
        values = {k: np.concatenate([values[k], extra[k]]) for k in values}
    p = profile.parameters(values)
    forcing = build_forcing(
        meals,
        doses,
        minutes,
        profile.body_weight,
        profile.cyp_factor,
        mets,
        p.k_abs_factor,
        p.meal_factor,
    )
    p = calibrate_production(p, morning_inputs(forcing, morning))
    G = integrate(*steady_start(p, forcing.column(0)), p, forcing).G
    window = G[:, WARMUP_MIN:]
    band = percentile_band(window[:samples])
    return PlanSimulation(
        start=t0 + timedelta(minutes=WARMUP_MIN),
        point=window[0],
        p10=band[10],
        p50=band[50],
        p90=band[90],
        average=window[samples] if average is not None else None,
        samples=samples,
        curves=window[:samples] if keep_curves else None,
    )

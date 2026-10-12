"""Medicine activity curves and absorption profiles for meals and injected insulin.

These parts of the twin do not depend on glucose, so Rozmarra calculates them in
advance for the whole timeline of a patient. Each function returns one value for
each minute of the timeline. Minute 0 is the start of the timeline, and doses or
meals before the start have negative times.

- Medicines taken by mouth follow the activity curve in docs/techstack.md,
  Section 5.2. This idea comes from the T2DSim AI project, and the code is our own.
- Injected insulin moves through two compartments under the skin with equal rate
  constants k, so a dose of D units appears in the blood at the rate D k² t e^(-kt).
  Basal insulin (glargine, degludec and detemir) is released at a constant rate
  over 24 hours.
- A meal moves through two gut compartments with the rate k_abs, so it appears in
  the blood at the rate f D k_abs² t e^(-k_abs t).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from rozmarra.fasting.meals import ABSORPTION_RATE_PER_MIN, FoodCategory
from rozmarra.medicines import ActivityCurve, InsulinAction, MedicineClass, get_medicine

LN2 = np.log(2.0)
# The rate constants of the two compartments under the skin (docs/techstack.md, Section 5.3).
INSULIN_RATE_PER_MIN = {
    InsulinAction.RAPID: 1 / 55,
    InsulinAction.REGULAR: 1 / 120,
    InsulinAction.NPH: 1 / 300,
}
BASAL_RELEASE_MIN = 1440
# Meals are followed for 10 hours. After that time, less than 0.1% of the slowest meal remains.
MEAL_HORIZON_MIN = 600
INSULIN_HORIZON_MIN = 2160

SECRETAGOGUE_CLASSES = {MedicineClass.SULFONYLUREA, MedicineClass.GLINIDE}


@dataclass(frozen=True)
class Dose:
    minute: float
    name: str
    amount: float


@dataclass(frozen=True)
class Meal:
    minute: float
    carbs_g: float
    category: FoodCategory


def activity_curve(t_min: np.ndarray, curve: ActivityCurve) -> np.ndarray:
    """The activity of one standard dose, t minutes after the dose. It peaks at exactly 1."""
    t = np.asarray(t_min, dtype=float)
    beta = LN2 / curve.half_life_min
    alpha = 1 + beta * curve.t_peak_min
    out = np.zeros_like(t)
    inside = (t > 0) & (t <= curve.t_max_min)
    ti = t[inside]
    out[inside] = (ti / curve.t_peak_min) ** (alpha - 1) * np.exp(-beta * (ti - curve.t_peak_min))
    return out


def adjusted_curve(name: str, cyp_clearance_factor: float = 1.0) -> ActivityCurve | None:
    """The activity curve of a medicine. CYP2C9 slows the clearance of sulfonylureas.

    Rozmarra divides the sulfonylurea half-life and maximum duration by the clearance
    factor c_cyp (docs/techstack.md, Section 5.3).
    """
    medicine = get_medicine(name)
    curve = medicine.curve
    if curve is None or medicine.medicine_class is not MedicineClass.SULFONYLUREA:
        return curve
    return ActivityCurve(
        curve.t_peak_min,
        curve.half_life_min / cyp_clearance_factor,
        curve.t_max_min / cyp_clearance_factor,
    )


@dataclass
class MedicineActivity:
    """The summed activity of each group of oral medicines, one value for each minute."""

    secretagogue: np.ndarray
    metformin: np.ndarray
    dpp4: np.ndarray
    sglt2: np.ndarray


def medicine_activity(
    doses: Iterable[Dose], minutes: int, cyp_clearance_factor: float = 1.0
) -> MedicineActivity:
    grid = np.arange(minutes, dtype=float)
    groups = {key: np.zeros(minutes) for key in ("secretagogue", "metformin", "dpp4", "sglt2")}
    for dose in doses:
        medicine = get_medicine(dose.name)
        curve = adjusted_curve(dose.name, cyp_clearance_factor)
        if curve is None:
            continue
        match medicine.medicine_class:
            case cls if cls in SECRETAGOGUE_CLASSES:
                key = "secretagogue"
            case MedicineClass.BIGUANIDE:
                key = "metformin"
            case MedicineClass.DPP4_INHIBITOR:
                key = "dpp4"
            case MedicineClass.SGLT2_INHIBITOR:
                key = "sglt2"
            case _:
                continue
        start = max(0, int(np.floor(dose.minute)))
        stop = min(minutes, int(np.ceil(dose.minute + curve.t_max_min)) + 1)
        if stop <= start:
            continue
        window = grid[start:stop]
        groups[key][start:stop] += (
            dose.amount / medicine.standard_dose * activity_curve(window - dose.minute, curve)
        )
    return MedicineActivity(**groups)


def insulin_appearance(doses: Iterable[Dose], minutes: int) -> np.ndarray:
    """The rate at which injected insulin reaches the blood, in units per minute."""
    grid = np.arange(minutes, dtype=float)
    rate = np.zeros(minutes)
    for dose in doses:
        medicine = get_medicine(dose.name)
        if not medicine.is_insulin:
            continue
        for action, share in medicine.insulin_parts:
            units = dose.amount * share
            if action is InsulinAction.BASAL:
                start = max(0, int(np.ceil(dose.minute)))
                stop = min(minutes, int(np.ceil(dose.minute + BASAL_RELEASE_MIN)))
                if stop > start:
                    rate[start:stop] += units / BASAL_RELEASE_MIN
                continue
            k = INSULIN_RATE_PER_MIN[action]
            start = max(0, int(np.floor(dose.minute)))
            stop = min(minutes, int(np.ceil(dose.minute + INSULIN_HORIZON_MIN)))
            if stop <= start:
                continue
            tau = np.clip(grid[start:stop] - dose.minute, 0, None)
            rate[start:stop] += units * k * k * tau * np.exp(-k * tau)
    return rate


def meal_appearance(
    meals: Iterable[Meal],
    minutes: int,
    body_weight_kg: float,
    k_abs_factor: np.ndarray | float = 1.0,
    meal_factor: np.ndarray | float = 1.0,
    absorbed_share: float = 0.9,
    glucose_volume_dl_per_kg: float = 1.6,
) -> np.ndarray:
    """The rate at which meal glucose raises plasma glucose, in mg/dL per minute.

    The factors can be arrays of length B, one for each parameter set. The result
    then has the shape (B, minutes).
    """
    k_factor = np.atleast_1d(np.asarray(k_abs_factor, dtype=float))
    size_factor = np.atleast_1d(np.asarray(meal_factor, dtype=float))
    batch = max(len(k_factor), len(size_factor))
    out = np.zeros((batch, minutes))
    grid = np.arange(minutes, dtype=float)
    for meal in meals:
        if meal.carbs_g <= 0:
            continue
        start = max(0, int(np.floor(meal.minute)))
        stop = min(minutes, int(np.ceil(meal.minute + MEAL_HORIZON_MIN)))
        if stop <= start:
            continue
        tau = np.clip(grid[start:stop] - meal.minute, 0, None)[None, :]
        k = (ABSORPTION_RATE_PER_MIN[meal.category] * k_factor)[:, None]
        dose = meal.carbs_g * 1000 * size_factor[:, None] / body_weight_kg
        out[:, start:stop] += (
            absorbed_share * dose * k * k * tau * np.exp(-k * tau) / glucose_volume_dl_per_kg
        )
    return out if np.ndim(k_abs_factor) or np.ndim(meal_factor) else out[0]


def minutes_since_last_meal(
    meals: Iterable[Meal], minutes: int, before_start_min: float = 600, min_carbs_g: float = 5
) -> np.ndarray:
    """The time since the last meal with at least 5 g of carbohydrate, for each minute.

    Before the first known meal, the count starts at before_start_min minutes.
    """
    since = np.arange(minutes, dtype=float) + before_start_min
    for meal in sorted(meals, key=lambda m: m.minute):
        if meal.carbs_g < min_carbs_g:
            continue
        start = max(0, int(np.ceil(meal.minute)))
        if start < minutes:
            since[start:] = np.minimum(
                since[start:], np.arange(minutes - start) + (start - meal.minute)
            )
    return since

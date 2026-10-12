"""Running the twin: building the inputs and simulating a timeline or a fasting plan."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from rozmarra.twin.medicines import (
    Dose,
    Meal,
    insulin_appearance,
    meal_appearance,
    medicine_activity,
    minutes_since_last_meal,
)
from rozmarra.twin.model import F_ABSORBED, V_G, Forcing, Parameters


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

import time as clock
from datetime import time

import numpy as np
import pytest

from rozmarra.ehr.demo_patients import DEMO_FASTS, SUNITA
from rozmarra.fasting.templates import UsualDose, build_plan
from rozmarra.twin.profiles import average_profile, profile_for_record
from rozmarra.twin.simulate import WARMUP_MIN, simulate_plan

FAST = DEMO_FASTS[SUNITA.patient_id]
PLAN_A = build_plan(
    FAST.template_id, SUNITA.patient_id, FAST.date, SUNITA.city, SUNITA.usual_doses()
)
PROFILE = profile_for_record(SUNITA, FAST.date)
# A stand-in for the fitted twins: one twin with different parameters.
TWINS = [
    {
        "fitted": {
            "S_G": 0.01,
            "S_I": 4e-4,
            "beta": 0.01,
            "k_abs_factor": 0.8,
            "meal_factor": 0.55,
            "gamma_su": 1.0,
        }
    }
]


def plan_b():
    """Plan B: 1 mg of glimepiride with sargi, and dapagliflozin and metformin after the fast."""
    plan = PLAN_A.model_copy(deep=True)
    plan.plan_name = "Plan B: lower glimepiride dose with sargi"
    sargi = plan.meals[0].time
    breaking = plan.breaking_meal.time
    for dose in plan.medicines:
        if dose.name == "glimepiride" and dose.time.date() == FAST.date:
            dose.dose, dose.time = 1, sargi
        elif dose.name in {"dapagliflozin", "metformin"} and dose.time.date() == FAST.date:
            dose.time = max(dose.time, breaking)
    return plan


def test_the_simulation_covers_the_plan_window_with_an_ordered_band():
    result = simulate_plan(PLAN_A, PROFILE, SUNITA.usual_doses(), samples=50)
    assert result.start == PLAN_A.window_start.replace(second=0, microsecond=0)
    assert result.time_at(result.minutes) >= PLAN_A.window_end - np.timedelta64(1, "m")
    assert np.all(result.p10 <= result.p50 + 1e-9)
    assert np.all(result.p50 <= result.p90 + 1e-9)
    assert result.p90.max() - result.p10.min() > 0, "The band has a width."
    assert result.average is None


def test_one_fasting_day_with_an_uncertainty_band_runs_quickly():
    simulate_plan(PLAN_A, PROFILE, SUNITA.usual_doses(), samples=10)  # The first call warms up.
    start = clock.perf_counter()
    simulate_plan(
        PLAN_A, PROFILE, SUNITA.usual_doses(), samples=100, average=average_profile(PROFILE, TWINS)
    )
    elapsed = clock.perf_counter() - start
    # The target on a laptop is less than 1 second. The limit here allows slower test machines.
    assert elapsed < 2.0


def test_the_average_patient_curve_differs_from_the_patients_own_twin():
    result = simulate_plan(
        PLAN_A, PROFILE, SUNITA.usual_doses(), samples=20, average=average_profile(PROFILE, TWINS)
    )
    assert result.average is not None
    assert result.average.shape == result.point.shape
    assert np.abs(result.average - result.point).max() > 1


def test_plan_b_keeps_glucose_higher_during_the_fast_than_plan_a():
    def lowest_during_fast(plan):
        result = simulate_plan(plan, PROFILE, SUNITA.usual_doses(), samples=1)
        start = int((plan.fast_start - result.start).total_seconds() // 60)
        end = int((plan.fast_end - result.start).total_seconds() // 60)
        return result.point[start:end].min()

    assert lowest_during_fast(plan_b()) >= lowest_during_fast(PLAN_A)


def test_the_warm_up_day_uses_the_usual_doses_before_the_plan():
    from rozmarra.twin.simulate import plan_timeline

    doses = [UsualDose("glimepiride", 2, time(8, 0))]
    _, _, _, timeline_doses, _, morning = plan_timeline(PLAN_A, doses)
    before = [d for d in timeline_doses if d.minute < WARMUP_MIN]
    assert len(before) >= 2, "The usual doses of the days before the plan are included."
    assert 0 <= morning < WARMUP_MIN, "P0 is calibrated on the usual day."


@pytest.mark.parametrize("samples", [1, 5])
def test_the_first_sample_is_the_most_likely_twin(samples):
    values = PROFILE.sample(samples, np.random.default_rng(1))
    assert values["S_I"][0] == pytest.approx(np.exp(PROFILE.log_mean[1]))

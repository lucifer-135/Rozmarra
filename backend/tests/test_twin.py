import numpy as np
import pytest
from scipy.integrate import solve_ivp

from rozmarra.fasting.meals import FoodCategory
from rozmarra.medicines import MEDICINES, get_medicine
from rozmarra.twin import model
from rozmarra.twin.medicines import (
    Dose,
    Meal,
    activity_curve,
    adjusted_curve,
    insulin_appearance,
    meal_appearance,
)
from rozmarra.twin.simulate import build_forcing, morning_inputs, population_parameters
from rozmarra.twin.solver import integrate

DAY = 1440


def calibrated(meals=(), doses=(), minutes=DAY, a_f=model.A_F, **fitted):
    p = population_parameters(140, 10, 70, 90, **fitted)
    p.a_f = a_f
    forcing = build_forcing(meals, doses, minutes, 70)
    return model.calibrate_production(p, morning_inputs(forcing, 0)), forcing


@pytest.mark.parametrize("name", [n for n, m in MEDICINES.items() if m.curve is not None])
def test_activity_curves_peak_at_one_and_stay_inside_their_duration(name):
    curve = get_medicine(name).curve
    assert activity_curve(np.array([curve.t_peak_min]), curve)[0] == pytest.approx(1.0)
    outside = activity_curve(np.array([-30.0, 0.0, curve.t_max_min + 1]), curve)
    assert np.all(outside == 0)
    t = np.arange(0, curve.t_max_min + 1)
    assert activity_curve(t, curve).max() <= 1.0 + 1e-12


def test_cyp2c9_variant_lengthens_the_glimepiride_curve():
    normal = adjusted_curve("glimepiride", 1.0)
    slow = adjusted_curve("glimepiride", 0.65)
    assert slow.half_life_min == pytest.approx(normal.half_life_min / 0.65)
    assert adjusted_curve("metformin", 0.65) == get_medicine("metformin").curve


def test_insulin_and_meal_inputs_deliver_the_whole_dose():
    rate = insulin_appearance([Dose(0, "premixed_insulin_30_70", 10)], 3000)
    assert rate.sum() == pytest.approx(10, rel=0.01)
    basal = insulin_appearance([Dose(0, "insulin_glargine", 18)], 3000)
    assert basal.sum() == pytest.approx(18, rel=1e-6)
    ra = meal_appearance([Meal(0, 50, FoodCategory.MIXED)], 900, 70)
    expected = 0.9 * 50_000 / 70 / 1.6  # absorbed glucose in mg/kg divided by V_G
    assert ra.sum() == pytest.approx(expected, rel=0.01)


def test_glucose_stays_at_the_fasting_level_without_meals_or_medicines():
    p, forcing = calibrated(a_f=0.0)
    trajectory = integrate(*model.steady_start(p, forcing.column(0)), p, forcing)
    assert np.abs(trajectory.G - 140).max() < 1


def test_a_50_g_meal_raises_glucose_by_a_plausible_amount():
    meals = [Meal(60, 50, FoodCategory.MIXED)]
    p, forcing = calibrated(meals, minutes=8 * 60)
    G = integrate(*model.steady_start(p, forcing.column(0)), p, forcing).G[0]
    rise = G.max() - 140
    assert 40 < rise < 160
    assert 45 <= G.argmax() - 60 <= 150
    assert abs(G[60 + 360] - 140) < 15, "Glucose returns close to the fasting level within 6 hours."


def test_the_solver_matches_scipy_within_1_mg_dl():
    meals = [Meal(120, 60, FoodCategory.MIXED), Meal(600, 40, FoodCategory.FAST_ABSORBING)]
    doses = [
        Dose(60, "glimepiride", 2),
        Dose(60, "metformin", 500),
        Dose(60, "insulin_glargine", 12),
    ]
    p, forcing = calibrated(meals, doses, minutes=DAY)
    start = model.steady_start(p, forcing.column(0))
    ours = integrate(*start, p, forcing).G[0]

    def rhs(t, y):
        k = min(int(np.floor(t)), forcing.length - 1)
        dG, dX, dI = model.derivatives(*(np.array([v]) for v in y), p, forcing.column(k))
        return [dG[0], dX[0], dI[0]]

    y0 = [float(np.atleast_1d(v)[0]) for v in start]
    reference = solve_ivp(
        rhs,
        (0, DAY),
        y0,
        method="LSODA",
        t_eval=np.arange(DAY + 1),
        max_step=0.5,
        rtol=1e-8,
        atol=1e-8,
    )
    assert reference.success
    assert np.abs(ours - reference.y[0]).max() < 1.0


@pytest.mark.parametrize("slope", [-1.5, -0.5, 0.0, 0.8, 2.0])
def test_the_trend_matched_start_reproduces_the_cgm_trend(slope):
    p, forcing = calibrated([Meal(30, 40, FoodCategory.MIXED)], minutes=600)
    inputs = forcing.column(90)
    G0, X0, I0 = model.trend_matched_start(p, np.array([150.0]), np.array([slope]), inputs)
    dG, _, _ = model.derivatives(G0, X0, I0, p, inputs)
    limited = np.isclose(X0, model.X_MIN_FACTOR * p.S_G) | np.isclose(X0, model.X_MAX)
    if not limited.any():
        assert abs(dG[0] - slope) < 0.1
        assert I0[0] == pytest.approx(p.I_b[0] + X0[0] / p.S_I[0])


def test_the_trend_matched_start_respects_the_limits_on_x0():
    p, forcing = calibrated(minutes=60)
    G0, X0, _ = model.trend_matched_start(p, np.array([120.0]), np.array([25.0]), forcing.column(0))
    assert X0[0] == pytest.approx(model.X_MIN_FACTOR * p.S_G[0])


def test_a_lower_glimepiride_dose_gives_higher_glucose_during_a_fast():
    # The usual dose is 2 mg on the days before the fast, so P0 is calibrated on the usual
    # plan. Only the dose on the day of the fast changes.
    def lowest(dose):
        doses = [Dose(8 * 60 + d * DAY, "glimepiride", 2) for d in range(2)]
        doses.append(Dose(2 * DAY + 8 * 60, "glimepiride", dose))
        meals = [
            Meal(t + d * DAY, c, FoodCategory.MIXED)
            for d in range(2)
            for t, c in ((8 * 60, 50), (13 * 60, 70), (20 * 60, 70))
        ]
        p = population_parameters(115, 10, 70, 90, S_I=4e-4)
        forcing = build_forcing(meals, doses, 3 * DAY, 70, 0.65)
        p = model.calibrate_production(p, morning_inputs(forcing, 2 * DAY + 7 * 60))
        G = integrate(*model.steady_start(p, forcing.column(0)), p, forcing).G[0]
        return G[2 * DAY + 8 * 60 : 2 * DAY + 23 * 60].min()

    assert lowest(1) > lowest(2)

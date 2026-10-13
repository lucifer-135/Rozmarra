from types import SimpleNamespace

import numpy as np

from rozmarra.fasting.meals import FoodCategory
from rozmarra.ml.datasets import real_breaking_meals
from rozmarra.twin.medicines import Meal

DAY = 1440


def patient(meals, split_minute=2 * DAY):
    return SimpleNamespace(
        cgm_minute=np.arange(0, 6 * DAY, 15),
        split_minute=split_minute,
        meals=[Meal(minute, carbs, FoodCategory.MIXED) for minute, carbs in meals],
    )


def test_only_meals_after_8_hours_without_food_on_held_out_days_are_chosen():
    meals = [
        (2 * DAY - 240, 50),  # Dinner on the last fitted day.
        (2 * DAY + 480, 40),  # Breakfast after 12 hours without food: chosen.
        (2 * DAY + 780, 60),  # Lunch after 5 hours: not chosen.
        (2 * DAY + 1200, 50),  # Dinner after 7 hours: not chosen.
        (3 * DAY + 420, 10),  # Breakfast after 11 hours, but with only 10 g: not chosen.
        (3 * DAY + 900, 45),  # Lunch after 8 hours: chosen.
    ]
    fasts = real_breaking_meals(patient(meals))
    assert [f.breaking_minute for f in fasts] == [2 * DAY + 480, 3 * DAY + 900]
    assert fasts[0].start == 2 * DAY - 240
    assert all(f.fast_type == "custom" for f in fasts)


def test_meals_on_fitted_days_are_not_chosen():
    meals = [(DAY - 240, 50), (DAY + 480, 40)]
    assert real_breaking_meals(patient(meals)) == []

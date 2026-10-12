from datetime import date, datetime, time, timedelta

import pytest

from rozmarra.fasting.calendar import KARVA_CHAUTH_2026, sun_times
from rozmarra.fasting.templates import TEMPLATES, UsualDose, build_plan

TOLERANCE = timedelta(minutes=6)


def close_to(actual: datetime, hour: int, minute: int) -> bool:
    expected = actual.replace(hour=hour, minute=minute)
    return abs(actual - expected) <= TOLERANCE


def test_sun_times_in_delhi_on_karva_chauth():
    sun = sun_times(KARVA_CHAUTH_2026, "Delhi")
    assert close_to(sun.sunrise, 6, 31)
    assert close_to(sun.sunset, 17, 40)
    assert sun.dawn < sun.sunrise < sun.sunset


def test_sun_times_in_hyderabad_during_ramadan_2027():
    sun = sun_times(date(2027, 2, 20), "Hyderabad")
    assert close_to(sun.sunrise, 6, 42)
    assert close_to(sun.sunset, 18, 22)
    # Dawn at 18 degrees below the horizon comes about 70 to 80 minutes before sunrise.
    assert timedelta(minutes=65) <= sun.sunrise - sun.dawn <= timedelta(minutes=85)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
def test_every_template_builds_a_consistent_plan(template):
    plan = build_plan(template.id, "SY-TEST", date(2026, 10, 28), "Delhi")
    breaking = [meal for meal in plan.meals if meal.breaks_fast]
    assert len(breaking) == 1, "Each template has exactly one meal that breaks the fast."
    assert plan.fast_start < plan.fast_end
    # The meal that breaks the fast comes at the end of the fast or soon after it.
    assert timedelta(0) <= breaking[0].time - plan.fast_end <= timedelta(hours=1)
    assert plan.water_allowed == template.water_allowed
    if template.no_food_during_fast:
        inside = [m for m in plan.meals if plan.fast_start < m.time < plan.fast_end]
        assert inside == [], "A strict fast has no meals inside the fasting window."
    assert template.word_hi in {"व्रत", "उपवास", "रोज़ा"}
    assert all(meal.label_hi for meal in plan.meals)


def test_karva_chauth_allows_no_water_between_sunrise_and_moonrise():
    plan = build_plan("karva_chauth", "SY-0001", KARVA_CHAUTH_2026, "Delhi")
    sun = sun_times(KARVA_CHAUTH_2026, "Delhi")
    assert not plan.water_allowed
    assert plan.fast_start < sun.sunrise
    assert plan.fast_end.time() == time(20, 14)
    assert plan.meals[0].label.startswith("Sargi") and plan.meals[0].time < sun.sunrise
    assert 15 <= plan.fast_hours <= 16
    # The longest time without food stays below 16 hours, so the IDF-DAR item scores 0.
    assert plan.longest_gap_without_food_hours < 16


def test_ramadan_runs_from_dawn_to_sunset():
    day = date(2027, 2, 20)
    plan = build_plan("ramadan", "SY-0003", day, "Hyderabad")
    sun = sun_times(day, "Hyderabad")
    assert plan.fast_start == sun.dawn
    assert plan.fast_end == sun.sunset
    assert plan.meals[0].time < sun.dawn
    assert 12 <= plan.fast_hours <= 14.5
    assert plan.longest_gap_without_food_hours < 16


def test_navratri_with_one_meal_has_a_gap_of_16_hours_or_more():
    plan = build_plan("navratri_one_meal", "SY-0002", date(2026, 10, 15), "Ahmedabad")
    assert plan.longest_gap_without_food_hours >= 16
    assert plan.activities[0].label == "Garba or dandiya dancing"
    assert plan.activities[0].start > plan.breaking_meal.time


@pytest.mark.parametrize("template_id", ["nirjala_ekadashi", "chhath", "jain_upvas"])
def test_long_fasts_last_more_than_24_hours(template_id):
    plan = build_plan(template_id, "SY-TEST", date(2026, 11, 15), "Patna")
    assert plan.fast_hours > 24


def test_usual_medicines_are_copied_unchanged_into_the_window():
    doses = [UsualDose("glimepiride", 2, time(8, 0)), UsualDose("metformin", 500, time(20, 30))]
    plan = build_plan("karva_chauth", "SY-0001", KARVA_CHAUTH_2026, "Delhi", doses)
    names = [(dose.name, dose.time.time()) for dose in plan.medicines]
    assert ("glimepiride", time(8, 0)) in names
    assert ("metformin", time(20, 30)) in names
    assert not any(dose.is_changed for dose in plan.medicines)
    assert all(plan.window_start <= dose.time <= plan.window_end for dose in plan.medicines)


def test_karva_chauth_outside_delhi_asks_for_the_local_moonrise():
    plan = build_plan("karva_chauth", "SY-TEST", KARVA_CHAUTH_2026, "Mumbai")
    assert any("local moonrise" in note for note in plan.notes)


def test_a_plan_survives_a_round_trip_through_json():
    plan = build_plan("ramadan", "SY-0003", date(2027, 2, 20), "Hyderabad")
    again = type(plan).model_validate_json(plan.model_dump_json())
    assert again == plan

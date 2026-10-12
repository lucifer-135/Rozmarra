import numpy as np
import pytest

from rozmarra.ml.labels import (
    breaking_meal_labels,
    completeness,
    find_events,
    point_labels,
    readings_needed,
)


def series(values, interval):
    return np.arange(len(values)) * interval, np.array(values, dtype=float)


@pytest.mark.parametrize(("interval", "needed"), [(5, 3), (15, 2)])
def test_the_15_minute_rule_needs_the_right_number_of_readings(interval, needed):
    assert readings_needed(interval) == needed


def test_three_low_readings_in_a_row_make_an_event_with_5_minute_data():
    minutes, values = series([100, 90, 68, 65, 66, 75, 80, 85, 90], 5)
    (event,) = find_events(minutes, values, 5)
    assert event.start == 10
    assert event.end == 20
    assert event.extreme == 65
    assert not event.severe


def test_two_low_readings_are_not_enough_with_5_minute_data():
    minutes, values = series([100, 68, 65, 75, 80, 85, 90], 5)
    assert find_events(minutes, values, 5) == []


def test_two_low_readings_in_a_row_make_an_event_with_15_minute_data():
    minutes, values = series([100, 68, 52, 80, 85, 90], 15)
    (event,) = find_events(minutes, values, 15)
    assert (event.start, event.end) == (15, 30)
    assert event.severe, "A value below 54 mg/dL makes the event severe."


def test_a_gap_in_the_data_breaks_the_run():
    minutes = np.array([0, 5, 10, 40, 45, 50, 55])
    values = np.array([100, 65, 66, 64, 90, 95, 100], dtype=float)
    assert find_events(minutes, values, 5) == []


def test_the_event_ends_only_after_15_minutes_at_or_above_70():
    values = [100, 65, 64, 63, 72, 66, 65, 64, 80, 85, 90, 95]
    minutes, values = series(values, 5)
    events = find_events(minutes, values, 5)
    assert len(events) == 1, "One reading above 70 mg/dL does not end the event."
    assert events[0].end == 35


def test_high_events_use_the_same_rule():
    minutes, values = series([200, 255, 260, 270, 240, 230, 220], 5)
    (event,) = find_events(minutes, values, 5, threshold=250, below=False, severe_threshold=None)
    assert event.extreme == 270


def test_completeness_counts_the_share_of_expected_readings():
    minutes = np.arange(0, 121, 5)
    assert completeness(minutes, 0, 120, 5) == 1.0
    sparse = minutes[::2]
    assert completeness(sparse, 0, 120, 5) == pytest.approx(0.5)


def test_e1_labels_mark_the_hour_before_a_low_event():
    values = [120] * 30 + [100, 90, 80, 72, 68, 65, 64, 66, 80, 90] + [110] * 20
    minutes, values = series(values, 5)
    labels = point_labels(minutes, values, 5, [(0, int(minutes[-1]))]).set_index("minute")
    event_start = 170
    assert labels.loc[event_start - 60, "label"] == 1
    assert labels.loc[event_start - 5, "label"] == 1
    assert labels.loc[event_start - 65, "label"] == 0
    assert event_start + 5 not in labels.index, "Time points already below 70 mg/dL are left out."
    assert not labels.loc[0, "usable"], "The first point lacks two hours of history."
    assert labels.loc[150, "usable"]


def test_e1_labels_cover_only_the_fasting_window():
    minutes, values = series([120] * 100, 5)
    labels = point_labels(minutes, values, 5, [(200, 300)])
    assert labels["minute"].min() == 200 and labels["minute"].max() == 300
    assert labels["label"].sum() == 0


def test_e2_labels_follow_the_four_hours_after_the_meal():
    values = [130] * 40 + [180, 230, 260, 270, 265, 240, 200] + [160] * 50
    minutes, values = series(values, 5)
    labels = breaking_meal_labels(minutes, values, 5, meal_minutes=[150, 400])
    assert labels["label"].tolist() == [1, 0]
    assert labels["prediction_minute"].tolist() == [30, 280]

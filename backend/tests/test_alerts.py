import numpy as np
import pandas as pd

from rozmarra.ml.alerts import detected_share, event_runs, raise_alerts, threshold_for_events


def frame(minutes, patient="P1"):
    return pd.DataFrame({"patient_id": patient, "minute": minutes})


def test_an_alert_is_not_repeated_within_30_minutes():
    f = frame(np.arange(0, 60, 5))
    p = np.full(len(f), 0.5)
    alert = raise_alerts(f, p, 0.4)
    assert list(f.minute[alert]) == [0, 30]


def test_an_alert_is_repeated_when_the_chance_rises_by_10_points():
    f = frame([0, 5, 10, 15])
    p = np.array([0.5, 0.55, 0.61, 0.65])
    alert = raise_alerts(f, p, 0.4)
    assert list(f.minute[alert]) == [0, 10]


def test_each_patient_starts_without_a_previous_alert():
    f = pd.concat([frame([0, 5], "P1"), frame([0, 5], "P2")], ignore_index=True)
    alert = raise_alerts(f, np.full(4, 0.9), 0.5)
    assert list(alert) == [True, False, True, False]


def test_a_negative_point_or_a_gap_starts_a_new_event():
    f = frame([0, 5, 10, 15, 20, 40, 45])
    y = np.array([1, 1, 0, 0, 1, 1, 1])
    # A negative point ends the first event, and the gap from 20 to 40 minutes ends the second.
    assert list(event_runs(f, y, 5)) == [0, 0, -1, -1, 1, 2, 2]
    # With 15-minute data, a gap of 20 minutes stays inside one event and a gap of 25 does not.
    assert list(event_runs(frame([0, 15, 35, 60]), np.ones(4), 15)) == [0, 0, 0, 1]


def test_an_event_counts_as_detected_when_one_alert_falls_inside_it():
    runs = np.array([0, 0, -1, 1, 1])
    assert detected_share(runs, np.array([False, True, False, False, False])) == 0.5
    assert detected_share(np.full(3, -1), np.ones(3, dtype=bool)) is None


def test_the_alert_level_is_the_highest_that_detects_enough_events():
    # Four events of two points each. The best chance inside each event is 0.9, 0.8, 0.7 and
    # 0.6, so detecting three of the four events needs a level of 0.7 or lower.
    f = frame(np.arange(0, 200, 5))
    y = np.zeros(len(f))
    p = np.full(len(f), 0.1)
    for start, best in zip((0, 50, 100, 150), (0.9, 0.8, 0.7, 0.6), strict=True):
        index = f.index[f.minute.isin([start, start + 5])]
        y[index] = 1
        p[index] = [best, best - 0.05]
    level = threshold_for_events(f, y, p, 5, target=0.75)
    # The candidate levels are quantiles of the chances, so the level is just at or below 0.7.
    assert 0.69 < level <= 0.7

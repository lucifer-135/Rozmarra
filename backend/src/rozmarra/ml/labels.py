"""Event labels from CGM data (docs/techstack.md, Section 6.4, and docs/prd.md, Section 10).

- A low blood sugar event starts when glucose stays below 70 mg/dL for at least 15
  minutes. With 5-minute data, this means three readings in a row. With 15-minute data,
  it means two readings in a row. The event ends when glucose stays at or above 70 mg/dL
  for at least 15 minutes. Readings count as "in a row" only when no reading is missing
  between them. The event is severe if glucose falls below 54 mg/dL.
- E1: each time point during a fasting window (every 5 minutes) has the label 1 if a low
  blood sugar event starts within the next 60 minutes. Time points where glucose is
  already below 70 mg/dL are not used.
- E2: each meal that breaks a fast has the label 1 if glucose stays above 250 mg/dL for
  at least 15 minutes within the 4 hours after the meal. The prediction is made 2 hours
  before the meal.
- E3: like E1, for glucose above 300 mg/dL.
- Data completeness: a time point is usable only when at least 70% of the expected CGM
  readings are present in the last 2 hours and in the period that the label covers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_DURATION_MIN = 15
COMPLETENESS = 0.7
HISTORY_MIN = 120
STEP_MIN = 5
E2_WINDOW_MIN = 240
E2_LEAD_MIN = 120


@dataclass(frozen=True)
class GlucoseEvent:
    start: int  # Minute of the first reading of the event
    end: int  # Minute of the last reading of the event
    extreme: float  # The lowest value of a low event, or the highest value of a high event
    severe: bool


def readings_needed(interval_min: int, duration_min: int = MIN_DURATION_MIN) -> int:
    """The number of readings in a row that cover the duration: 3 for 5-minute data, 2 for 15."""
    return max(2, int(np.ceil(duration_min / interval_min)))


def find_events(
    minutes: np.ndarray,
    values: np.ndarray,
    interval_min: int,
    threshold: float = 70.0,
    below: bool = True,
    severe_threshold: float | None = 54.0,
) -> list[GlucoseEvent]:
    """Find events in one patient's CGM series. The minutes must be sorted."""
    minutes = np.asarray(minutes)
    values = np.asarray(values, dtype=float)
    needed = readings_needed(interval_min)
    inside = values < threshold if below else values > threshold
    # Two readings are "in a row" when the time between them is at most 1.5 intervals.
    breaks = np.concatenate([[True], np.diff(minutes) > 1.5 * interval_min])

    events: list[GlucoseEvent] = []
    run_in, run_out = 0, 0
    current_start = None
    extreme = None
    for i in range(len(values)):
        if breaks[i]:
            run_in = run_out = 0
        if inside[i]:
            run_in += 1
            run_out = 0
            if current_start is None and run_in >= needed:
                first = i - needed + 1
                current_start = first
                window = values[first : i + 1]
                extreme = window.min() if below else window.max()
            elif current_start is not None:
                extreme = min(extreme, values[i]) if below else max(extreme, values[i])
        else:
            run_out += 1
            run_in = 0
            if current_start is not None and run_out >= needed:
                last = i - needed
                events.append(
                    _event(minutes, current_start, last, extreme, below, severe_threshold)
                )
                current_start = None
    if current_start is not None:
        last = int(np.nonzero(inside)[0][-1])
        events.append(_event(minutes, current_start, last, extreme, below, severe_threshold))
    return events


def _event(minutes, first, last, extreme, below, severe_threshold) -> GlucoseEvent:
    severe = severe_threshold is not None and (
        extreme < severe_threshold if below else extreme > severe_threshold
    )
    return GlucoseEvent(int(minutes[first]), int(minutes[last]), float(extreme), bool(severe))


def completeness(minutes: np.ndarray, start: float, end: float, interval_min: int) -> float:
    """The share of expected readings present in the interval (start, end]."""
    expected = (end - start) / interval_min
    if expected <= 0:
        return 1.0
    present = np.count_nonzero((minutes > start) & (minutes <= end))
    return min(present / expected, 1.0)


def point_labels(
    minutes: np.ndarray,
    values: np.ndarray,
    interval_min: int,
    windows: list[tuple[int, int]],
    horizon_min: int = 60,
    threshold: float = 70.0,
    below: bool = True,
) -> pd.DataFrame:
    """Labels for E1 (below=True) or E3 (below=False) at every 5 minutes inside the windows."""
    events = find_events(minutes, values, interval_min, threshold, below, None)
    starts = np.array([e.start for e in events])
    rows = []
    for window_start, window_end in windows:
        for t in range(int(window_start), int(window_end) + 1, STEP_MIN):
            latest = np.searchsorted(minutes, t, side="right") - 1
            if latest < 0 or t - minutes[latest] > interval_min:
                continue
            current = values[latest]
            if (below and current < threshold) or (not below and current > threshold):
                continue
            label = (
                bool(np.any((starts > t) & (starts <= t + horizon_min))) if len(starts) else False
            )
            usable = (
                completeness(minutes, t - HISTORY_MIN, t, interval_min) >= COMPLETENESS
                and completeness(minutes, t, t + horizon_min, interval_min) >= COMPLETENESS
            )
            rows.append((t, int(label), usable))
    return pd.DataFrame(rows, columns=["minute", "label", "usable"])


def breaking_meal_labels(
    minutes: np.ndarray,
    values: np.ndarray,
    interval_min: int,
    meal_minutes: list[int],
    threshold: float = 250.0,
) -> pd.DataFrame:
    """E2 labels for the meals that break a fast."""
    events = find_events(
        minutes, values, interval_min, threshold, below=False, severe_threshold=None
    )
    rows = []
    for meal in meal_minutes:
        hit = any(
            meal < e.start <= meal + E2_WINDOW_MIN or e.start <= meal <= e.end for e in events
        )
        prediction = meal - E2_LEAD_MIN
        usable = (
            completeness(minutes, prediction - HISTORY_MIN, prediction, interval_min)
            >= COMPLETENESS
            and completeness(minutes, meal, meal + E2_WINDOW_MIN, interval_min) >= COMPLETENESS
        )
        rows.append((meal, prediction, int(hit), usable))
    return pd.DataFrame(rows, columns=["meal_minute", "prediction_minute", "label", "usable"])

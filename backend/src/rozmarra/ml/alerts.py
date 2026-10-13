"""The alert rules, shared by the evaluation and the live fasting monitor.

- An alert is raised when the estimated chance reaches the alert level.
- The same alert is not repeated within 30 minutes, unless the chance rises by 10 percentage
  points or more since the last alert (FR-C7).
- An event is one run of time points with a positive label, which is the hour before one
  episode of low blood sugar. An event counts as detected in time when at least one alert
  falls inside its run. An alert at a time point with a negative label is a false alert.
- The alert level is the highest level at which the alerts detect at least 80% of the events
  of the validation patients. The validation patients belong to the training group, so the
  test patients never influence the alert level.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REPEAT_MIN = 30
REPEAT_RISE = 0.10
TARGET_EVENT_SENSITIVITY = 0.8


def raise_alerts(
    frame: pd.DataFrame,
    p: np.ndarray,
    threshold: float,
    repeat_min: float = REPEAT_MIN,
    rise: float = REPEAT_RISE,
) -> np.ndarray:
    """Mark the time points where an alert is raised. The frame needs patient_id and minute."""
    alert = np.zeros(len(frame), dtype=bool)
    patients = frame["patient_id"].to_numpy()
    minutes = frame["minute"].to_numpy()
    order = np.lexsort((minutes, patients))
    last_patient, last_minute, last_chance = None, -np.inf, 0.0
    for i in order:
        if patients[i] != last_patient:
            last_patient, last_minute, last_chance = patients[i], -np.inf, 0.0
        if p[i] < threshold:
            continue
        if minutes[i] - last_minute >= repeat_min or p[i] >= last_chance + rise:
            alert[i] = True
            last_minute, last_chance = minutes[i], p[i]
    return alert


def event_runs(frame: pd.DataFrame, label: np.ndarray, step) -> np.ndarray:
    """Number the runs of positive time points. The step is in minutes, for each row or for all."""
    run = np.full(len(frame), -1)
    steps = np.broadcast_to(np.asarray(step, dtype=float), (len(frame),))
    patients, minutes = frame["patient_id"].to_numpy(), frame["minute"].to_numpy()
    order = np.lexsort((minutes, patients))
    current, previous = -1, None
    for i in order:
        if label[i] != 1:
            previous = None
            continue
        if (
            previous is None
            or patients[i] != patients[previous]
            or minutes[i] - minutes[previous] > 1.5 * steps[i]
        ):
            current += 1
        run[i] = current
        previous = i
    return run


def detected_share(runs: np.ndarray, alert: np.ndarray) -> float | None:
    ids = np.unique(runs[runs >= 0])
    if len(ids) == 0:
        return None
    hit = np.unique(runs[(runs >= 0) & alert])
    return len(hit) / len(ids)


def threshold_for_events(
    frame: pd.DataFrame,
    y: np.ndarray,
    p: np.ndarray,
    step,
    target: float = TARGET_EVENT_SENSITIVITY,
) -> float | None:
    """The highest alert level that detects at least the target share of the events."""
    runs = event_runs(frame, y, step)
    if not (runs >= 0).any():
        return None
    candidates = np.unique(np.quantile(p, np.linspace(0.5, 0.9995, 300)))[::-1]
    for threshold in candidates:
        share = detected_share(runs, raise_alerts(frame, p, threshold))
        if share is not None and share >= target:
            return float(threshold)
    return None

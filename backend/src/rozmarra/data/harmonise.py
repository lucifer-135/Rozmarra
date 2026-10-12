"""The standard data format that every dataset is converted into.

The format follows docs/techstack.md, Section 4.1:

- The time-series table is one long table with one reading in each row.
- The events table holds meals, medicines and insulin doses, with details in JSON.
- The patients table holds the static information about each real patient.

The open datasets shift their dates for privacy, so Rozmarra uses the time of day
and the day number, not the calendar date. Rozmarra never fills a gap in the data.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

TIMESERIES_COLUMNS = [
    "patient_id",
    "timestamp_local",
    "timezone",
    "signal",
    "value",
    "unit",
    "source",
    "dataset",
    "device",
]
EVENT_COLUMNS = ["patient_id", "start", "end", "event_type", "details"]

REAL_OPEN = "real_open"


def long_signal(
    patient_id: str,
    times: pd.Series,
    values: pd.Series,
    *,
    signal: str,
    unit: str,
    dataset: str,
    device: str,
    timezone: str,
) -> pd.DataFrame:
    """Build rows of the time-series table for one signal, without the missing readings."""
    frame = pd.DataFrame({"timestamp_local": pd.to_datetime(times), "value": values})
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["timestamp_local", "value"])
    frame["patient_id"] = patient_id
    frame["timezone"] = timezone
    frame["signal"] = signal
    frame["unit"] = unit
    frame["source"] = REAL_OPEN
    frame["dataset"] = dataset
    frame["device"] = device
    return frame[TIMESERIES_COLUMNS]


def resample_mean(times: pd.Series, values: pd.Series, minutes: int) -> pd.Series:
    """Average the readings in each interval. Intervals without readings stay missing."""
    series = pd.Series(
        pd.to_numeric(values, errors="coerce").to_numpy(), index=pd.to_datetime(times)
    )
    series = series[~series.index.isna()].sort_index()
    return series.resample(f"{minutes}min").mean().dropna()


def event(
    patient_id: str, start: Any, event_type: str, details: dict[str, Any], end: Any = None
) -> dict[str, Any]:
    start = pd.Timestamp(start)
    return {
        "patient_id": patient_id,
        "start": start,
        "end": pd.Timestamp(end) if end is not None else start,
        "event_type": event_type,
        "details": json.dumps(details, ensure_ascii=False, sort_keys=True),
    }


def events_frame(rows: Iterable[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=EVENT_COLUMNS)


def concat(frames: Iterable[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)


def write_parquet(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path

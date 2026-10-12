"""The loader for the CGMacros dataset (PhysioNet, version 1.0.0).

Each participant has one CSV file with readings every minute: two CGMs (Dexcom G6 Pro
and FreeStyle Libre Pro), heart rate and activity from a Fitbit smartwatch, and meals
with their nutrients. The file bio.csv holds demographics and laboratory results.

The loader keeps Dexcom glucose as the main CGM signal, at 5-minute intervals, and
FreeStyle Libre glucose as a second signal at 15-minute intervals. It averages heart
rate and METs over 5-minute intervals. The dataset stores METs multiplied by 10.
Eleven files give a Fitbit intensity level instead of METs. The loader turns each
level into an approximate MET value, which is an assumption that the data card records.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

import pandas as pd

from rozmarra.data.harmonise import (
    EVENT_COLUMNS,
    REAL_OPEN,
    TIMESERIES_COLUMNS,
    concat,
    event,
    events_frame,
    long_signal,
    resample_mean,
)

DATASET = "CGMacros"
# The study took place in Texas, in the United States.
TIMEZONE = "America/Chicago"
DEXCOM = "Dexcom G6 Pro"
LIBRE = "FreeStyle Libre Pro"
WATCH = "Fitbit Sense"

# Approximate METs for each Fitbit intensity level: sedentary, light, fairly active
# and very active. This mapping is an assumption.
INTENSITY_TO_METS = {0: 1.0, 1: 2.5, 2: 4.5, 3: 7.0}
LB_TO_KG = 0.45359237
INCH_TO_CM = 2.54


def diabetes_status(hba1c: float) -> str:
    """Group participants by HbA1c, as the dataset does."""
    if pd.isna(hba1c):
        return "unknown"
    if hba1c < 5.7:
        return "healthy"
    if hba1c < 6.5:
        return "prediabetes"
    return "type_2_diabetes"


def patient_id_for(number: int) -> str:
    return f"CG-{int(number):03d}"


def mets_from(frame: pd.DataFrame) -> pd.Series | None:
    if "METs" in frame.columns:
        return pd.to_numeric(frame["METs"], errors="coerce") / 10
    if "Intensity" in frame.columns:
        return pd.to_numeric(frame["Intensity"], errors="coerce").map(INTENSITY_TO_METS)
    return None


def _nutrient(meal: pd.Series, share: float, name: str) -> float | None:
    """The amount of a nutrient that the participant ate, scaled by the share consumed."""
    value = pd.to_numeric(meal.get(name), errors="coerce")
    return None if pd.isna(value) else round(float(value) * share, 1)


def convert_participant(patient_id: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert one participant's minute-level table into the standard format."""
    frame = frame.rename(columns=lambda c: str(c).strip())
    times = pd.to_datetime(frame["Timestamp"], errors="coerce")
    common = {"dataset": DATASET, "timezone": TIMEZONE}

    def signal(values: pd.Series | None, minutes: int, name: str, unit: str, device: str):
        if values is None:
            return pd.DataFrame(columns=TIMESERIES_COLUMNS)
        series = resample_mean(times, values, minutes)
        return long_signal(
            patient_id,
            series.index.to_series(),
            series,
            signal=name,
            unit=unit,
            device=device,
            **common,
        )

    steps = None
    if "Steps" in frame.columns:
        step_series = pd.Series(
            pd.to_numeric(frame["Steps"], errors="coerce").to_numpy(), index=times
        ).sort_index()
        step_series = step_series[~step_series.index.isna()].resample("5min").sum(min_count=1)
        steps = long_signal(
            patient_id,
            step_series.index.to_series(),
            step_series,
            signal="steps",
            unit="steps",
            device=WATCH,
            **common,
        )

    parts = [
        signal(frame.get("Dexcom GL"), 5, "glucose_cgm", "mg/dL", DEXCOM),
        signal(frame.get("Libre GL"), 15, "glucose_cgm_secondary", "mg/dL", LIBRE),
        signal(frame.get("HR"), 5, "heart_rate", "beats per minute", WATCH),
        signal(mets_from(frame), 5, "mets", "MET", WATCH),
    ]
    if steps is not None:
        parts.append(steps)

    rows = []
    meals = frame[frame["Meal Type"].notna()] if "Meal Type" in frame.columns else frame.iloc[:0]
    for index, meal in meals.iterrows():
        share = pd.to_numeric(meal.get("Amount Consumed"), errors="coerce")
        share = 1.0 if pd.isna(share) else float(share) / 100
        nutrient = partial(_nutrient, meal, share)
        rows.append(
            event(
                patient_id,
                times[index],
                "meal",
                {
                    "meal_type": str(meal["Meal Type"]).strip(),
                    "calories": nutrient("Calories"),
                    "carbs_g": nutrient("Carbs"),
                    "protein_g": nutrient("Protein"),
                    "fat_g": nutrient("Fat"),
                    "fiber_g": nutrient("Fiber"),
                    "carbs_source": "recorded",
                },
            )
        )
    return concat(parts, TIMESERIES_COLUMNS), events_frame(rows)


def load_bio(path: Path) -> pd.DataFrame:
    bio = pd.read_csv(path)
    bio.columns = [str(c).strip() for c in bio.columns]
    hba1c = pd.to_numeric(bio["A1c PDL (Lab)"], errors="coerce")
    return pd.DataFrame(
        {
            "patient_id": bio["subject"].map(patient_id_for),
            "dataset": DATASET,
            "source": REAL_OPEN,
            "timezone": TIMEZONE,
            "sex": bio["Gender"].astype(str).str.strip().map({"F": "female", "M": "male"}),
            "age": pd.to_numeric(bio["Age"], errors="coerce"),
            "height_cm": (pd.to_numeric(bio["Height"], errors="coerce") * INCH_TO_CM).round(1),
            "weight_kg": (pd.to_numeric(bio["Body weight"], errors="coerce") * LB_TO_KG).round(1),
            "bmi": pd.to_numeric(bio["BMI"], errors="coerce").round(1),
            "diabetes_status": hba1c.map(diabetes_status),
            "hba1c_percent": hba1c,
            "fasting_glucose_mg_dl": pd.to_numeric(bio["Fasting GLU - PDL (Lab)"], errors="coerce"),
            "fasting_insulin_uu_ml": pd.to_numeric(bio["Insulin"], errors="coerce"),
        }
    )


def load(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load every participant. Return the time series, the events and the patients."""
    root = raw_dir / "cgmacros" / "CGMacros"
    patients = load_bio(root / "bio.csv")
    series, events = [], []
    for path in sorted(root.glob("CGMacros-*/CGMacros-*.csv")):
        number = int(path.stem.split("-")[1])
        timeseries, participant_events = convert_participant(
            patient_id_for(number), pd.read_csv(path)
        )
        series.append(timeseries)
        events.append(participant_events)
    return concat(series, TIMESERIES_COLUMNS), concat(events, EVENT_COLUMNS), patients

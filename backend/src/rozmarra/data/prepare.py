"""The command "rozmarra data prepare": convert the open datasets into the standard format.

The command writes three Parquet files to data/processed (timeseries.parquet,
events.parquet and patients.parquet) and a short summary to reports/data_summary.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from rozmarra.config import PROCESSED_DIR, RAW_DIR, REPORTS_DIR
from rozmarra.data import cgmacros, shanghai
from rozmarra.data.harmonise import EVENT_COLUMNS, TIMESERIES_COLUMNS, concat, write_parquet

LOADERS = {"shanghai": (shanghai, "shanghai_t2dm"), "cgmacros": (cgmacros, "cgmacros")}


def summarise(timeseries: pd.DataFrame, events: pd.DataFrame, patients: pd.DataFrame) -> dict:
    summary: dict = {"source": "real_open", "datasets": {}}
    glucose = timeseries[timeseries["signal"] == "glucose_cgm"]
    for dataset, group in patients.groupby("dataset"):
        ids = set(group["patient_id"])
        cgm = glucose[glucose["patient_id"].isin(ids)]
        days = cgm.groupby("patient_id")["timestamp_local"].agg(lambda t: t.max() - t.min())
        meals = events[(events["patient_id"].isin(ids)) & (events["event_type"] == "meal")]
        carbs = meals["details"].map(lambda d: json.loads(d).get("carbs_g"))
        summary["datasets"][dataset] = {
            "patients": len(ids),
            "patients_with_cgm": int(cgm["patient_id"].nunique()),
            "patients_by_diabetes_status": group["diabetes_status"].value_counts().to_dict(),
            "cgm_readings": len(cgm),
            "median_days_of_cgm": round(days.dt.total_seconds().median() / 86400, 1),
            "share_of_cgm_readings_below_70_mg_dl": round(float((cgm["value"] < 70).mean()), 4),
            "share_of_cgm_readings_below_54_mg_dl": round(float((cgm["value"] < 54).mean()), 4),
            "meals": len(meals),
            "meals_with_carbohydrates": int(carbs.notna().sum()),
            "signals": sorted(timeseries[timeseries["patient_id"].isin(ids)]["signal"].unique()),
        }
    return summary


def prepare(
    datasets: tuple[str, ...] = ("shanghai", "cgmacros"),
    raw_dir: Path = RAW_DIR,
    out_dir: Path = PROCESSED_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> dict:
    series, events, patients = [], [], []
    for name in datasets:
        module, folder = LOADERS[name]
        if not (raw_dir / folder).exists():
            raise FileNotFoundError(
                f"The {name} dataset is not in {raw_dir / folder}. "
                "Please run 'rozmarra data download' first."
            )
        print(f"Converting the {module.DATASET} dataset ...", flush=True)
        timeseries, dataset_events, dataset_patients = module.load(raw_dir)
        series.append(timeseries)
        events.append(dataset_events)
        patients.append(dataset_patients)

    timeseries = concat(series, TIMESERIES_COLUMNS)
    all_events = concat(events, EVENT_COLUMNS)
    all_patients = pd.concat(patients, ignore_index=True)
    write_parquet(timeseries, out_dir / "timeseries.parquet")
    write_parquet(all_events, out_dir / "events.parquet")
    write_parquet(all_patients, out_dir / "patients.parquet")

    summary = summarise(timeseries, all_events, all_patients)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "data_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

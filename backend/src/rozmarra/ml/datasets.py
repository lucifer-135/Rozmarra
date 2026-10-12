"""Feature tables for training and evaluation.

- Synthetic E1, E1 120 minutes ahead, E1 at 54 mg/dL and E3: every labelled time point in
  the fasting windows of the synthetic cohort.
- Synthetic E2: each meal that breaks a fast, 2 hours before the meal.
- Real E1 and E1 at 54 mg/dL: every CGM time point on the normal days of the real patients
  with a fitted twin. The real data contains no fasting days.

The estimated twins of the virtual patients come from the same seeds as the cohort, which
is fully reproducible. The tables go to data/processed/features.
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from rozmarra.config import PROCESSED_DIR, RANDOM_SEED
from rozmarra.ehr.records import PatientRecord
from rozmarra.fasting.meals import FoodCategory
from rozmarra.medicines import MedicineClass, get_medicine
from rozmarra.ml.features import (
    DAY,
    GRID,
    Fast,
    PatientSeries,
    TwinForecaster,
    breaking_meal_features,
    point_features,
    profile_from_values,
)
from rozmarra.ml.labels import point_labels
from rozmarra.risk.idf_dar import Hypoglycaemia, Macrovascular, calculate
from rozmarra.synth.split import fold_of
from rozmarra.twin.medicines import Dose, Meal
from rozmarra.twin.profiles import load_twins

FEATURE_DIR = PROCESSED_DIR / "features"
SYNTHETIC_DIR = PROCESSED_DIR / "synthetic"
HYPO_ORDER = [
    Hypoglycaemia.NONE,
    Hypoglycaemia.LESS_THAN_WEEKLY,
    Hypoglycaemia.SEVERAL_PER_WEEK,
    Hypoglycaemia.RECENT_SEVERE,
    Hypoglycaemia.UNAWARE,
]
SYNTHETIC_TARGETS = ("e1", "e1_120", "e1_54", "e3")


def record_features(record: PatientRecord, day) -> dict:
    classes = {get_medicine(m.name).medicine_class for m in record.medicines}
    su_ratio = sum(
        s.dose / get_medicine(m.name).standard_dose
        for m in record.medicines
        for s in m.schedule
        if get_medicine(m.name).medicine_class is MedicineClass.SULFONYLUREA
    )
    insulin = sum(
        s.dose for m in record.medicines for s in m.schedule if get_medicine(m.name).is_insulin
    )
    score = calculate(record.idf_dar_inputs(day, fasting_hours=None))
    return {
        "age": record.age_on(day),
        "sex_female": float(record.sex == "female"),
        "bmi": record.bmi,
        "years_with_diabetes": record.years_with_diabetes_on(day),
        "hba1c": record.hba1c_percent,
        "egfr": record.egfr,
        "takes_sulfonylurea": float(MedicineClass.SULFONYLUREA in classes),
        "takes_insulin": float(any(get_medicine(m.name).is_insulin for m in record.medicines)),
        "takes_premixed": float(MedicineClass.PREMIXED_INSULIN in classes),
        "takes_basal": float(MedicineClass.BASAL_INSULIN in classes),
        "takes_metformin": float(MedicineClass.BIGUANIDE in classes),
        "takes_sglt2": float(MedicineClass.SGLT2_INHIBITOR in classes),
        "takes_dpp4": float(MedicineClass.DPP4_INHIBITOR in classes),
        "su_dose_ratio": su_ratio,
        "insulin_daily_units": insulin,
        "cyp2c9_activity": record.cyp2c9_activity_score,
        "hypo_history": float(HYPO_ORDER.index(record.hypoglycaemia)),
        "hypo_unaware": float(record.hypoglycaemia is Hypoglycaemia.UNAWARE),
        "beta_blocker": float(record.takes_beta_blocker),
        "heart_disease": float(
            [Macrovascular.NONE, Macrovascular.STABLE, Macrovascular.UNSTABLE].index(
                record.heart_disease
            )
        ),
        "idf_dar_total": score.total,
    }


def _grid(times: pd.Series, values: pd.Series, start: pd.Timestamp, minutes: int, how="mean"):
    index = ((times - start) / pd.Timedelta(minutes=1)).to_numpy() // GRID
    out = np.full(minutes // GRID + 1, np.nan)
    frame = pd.DataFrame({"i": index.astype(int), "v": values.to_numpy()})
    frame = frame[(frame.i >= 0) & (frame.i < len(out))]
    agg = frame.groupby("i")["v"].mean() if how == "mean" else frame.groupby("i")["v"].sum()
    out[agg.index.to_numpy()] = agg.to_numpy()
    return out


# --- Synthetic patients ------------------------------------------------------------------


def synthetic_series(
    twin, timeseries: pd.DataFrame, events: pd.DataFrame, patient: pd.Series
) -> PatientSeries:
    start = pd.Timestamp(patient["timeline_start"])
    cgm = timeseries[timeseries.signal == "glucose_cgm"].sort_values("timestamp_local")
    end = timeseries["timestamp_local"].max()
    minutes = int((end - start) / pd.Timedelta(minutes=1)) + 1
    details = events["details"].map(json.loads)

    def minute(t):
        return (pd.Timestamp(t) - start) / pd.Timedelta(minutes=1)

    meals, doses, activities, fasts = [], [], [], []
    breaking = {}
    for (_, row), d in zip(events.iterrows(), details, strict=True):
        if row.event_type == "meal":
            meals.append(
                Meal(minute(row.start), float(d["carbs_g"]), FoodCategory(d["food_category"]))
            )
            if d.get("breaks_fast"):
                breaking[d["episode"]] = int(round(minute(row.start)))
        elif row.event_type in {"insulin", "medicine"}:
            doses.append(Dose(minute(row.start), d["name"], float(d["dose"])))
        elif row.event_type == "activity":
            activities.append((int(minute(row.start)), int(minute(row.end)), float(d["mets"])))
    for (_, row), d in zip(events.iterrows(), details, strict=True):
        if row.event_type == "fast":
            fasts.append(
                Fast(
                    int(minute(row.start)),
                    int(minute(row.end)),
                    d["fast_type"],
                    bool(d["water_allowed"]),
                    breaking.get(d["episode"]),
                )
            )

    wearables = {}
    for signal, how in (
        ("heart_rate", "mean"),
        ("hrv_rmssd", "mean"),
        ("steps", "sum"),
        ("mets", "mean"),
    ):
        rows = timeseries[timeseries.signal == signal]
        wearables[signal] = _grid(rows.timestamp_local, rows.value, start, minutes, how)
    sleep = timeseries[timeseries.signal == "sleep_stage"]
    asleep = _grid(sleep.timestamp_local, (sleep.value >= 1).astype(float), start, minutes)
    wearables["asleep"] = np.nan_to_num(asleep)
    return PatientSeries(
        patient_id=twin.record.patient_id,
        start=start,
        minutes=minutes,
        cgm_minutes=((cgm.timestamp_local - start) / pd.Timedelta(minutes=1)).to_numpy(),
        cgm_values=cgm.value.to_numpy(dtype=float),
        interval=5,
        meals=meals,
        doses=doses,
        activities=activities,
        fasts=fasts,
        record=record_features(twin.record, start.date()),
        profile=twin.profile,
        wearables=wearables,
    )


def _synthetic_job(job) -> dict[str, pd.DataFrame]:
    twin, group, timeseries, events, patient, labels = job
    ps = synthetic_series(twin, timeseries, events, patient)
    forecaster = TwinForecaster(ps)
    keys = ["minute", "episode", "template_id"]
    points = pd.concat([labels[t][keys] for t in SYNTHETIC_TARGETS]).drop_duplicates("minute")
    points = points.sort_values("minute").reset_index(drop=True)
    table = point_features(ps, points["minute"].to_numpy(), forecaster)
    table.insert(0, "patient_id", ps.patient_id)
    table.insert(1, "group", group)
    for column in keys:
        table[column] = points[column].to_numpy()
    for target in SYNTHETIC_TARGETS:
        frame = labels[target].set_index("minute")
        table[f"label_{target}"] = table["minute"].map(frame["label"])
        table[f"usable_{target}"] = table["minute"].map(frame["usable"]).fillna(False).astype(bool)

    e2 = breaking_meal_features(ps, forecaster)
    if len(e2):
        e2_labels = labels["e2"].reset_index(drop=True)
        e2.insert(0, "patient_id", ps.patient_id)
        e2.insert(1, "group", group)
        e2["label_e2"] = e2_labels["label"].to_numpy()[: len(e2)]
        e2["usable_e2"] = e2_labels["usable"].to_numpy()[: len(e2)]
        e2["template_id"] = e2_labels["template_id"].to_numpy()[: len(e2)]
    return {"e1": table, "e2": e2}


def _synthetic_part(job) -> list[dict[str, pd.DataFrame]]:
    """Build the features of the patients in one part file of the synthetic cohort.

    Each worker reads its own part file, so the whole cohort never passes between processes.
    The estimated twins come from the same seed as the cohort.
    """
    from rozmarra.synth.cohort import make_virtual_twins

    part, folder, count, seed, gamma_su_centre = job
    timeseries = pd.read_parquet(part)
    ids = sorted(timeseries["patient_id"].unique())
    pairs = {
        twin.record.patient_id: (twin, group)
        for twin, group in make_virtual_twins(count, seed, gamma_su_centre)
    }
    events = pd.read_parquet(folder / "events", filters=[("patient_id", "in", ids)])
    patients = pd.read_parquet(folder / "virtual_patients").set_index("patient_id")
    labels = {
        t: pd.read_parquet(folder / f"labels_{t}", filters=[("patient_id", "in", ids)])
        for t in SYNTHETIC_TARGETS + ("e2",)
    }
    results = []
    for pid in ids:
        twin, group = pairs[pid]
        patient_labels = {t: frame[frame.patient_id == pid] for t, frame in labels.items()}
        results.append(
            _synthetic_job(
                (
                    twin,
                    group,
                    timeseries[timeseries.patient_id == pid],
                    events[events.patient_id == pid],
                    patients.loc[pid],
                    patient_labels,
                )
            )
        )
    return results


def synthetic_jobs(
    folder: Path = SYNTHETIC_DIR,
    count: int = 500,
    seed: int = RANDOM_SEED,
    gamma_su_centre: float = 3.0,
):
    for part in sorted((folder / "timeseries").glob("part-*.parquet")):
        yield part, folder, count, seed, gamma_su_centre


# --- Real patients -----------------------------------------------------------------------


REAL_CLASSES = {
    "sulfonylurea": ("gliclazide", "glimepiride", "glibenclamide", "gliquidone"),
    "insulin": ("insulin", "novolin", "humulin", "gansulin", "scilin"),
    "premixed": ("70/30", "30r", "40r", "50/50", "m30"),
    "basal": ("glargine", "glarigine", "degludec", "detemir"),
    "metformin": ("metformin",),
    "sglt2": ("gliflozin",),
    "dpp4": ("gliptin",),
}


def real_record_features(patient: pd.Series) -> dict:
    text = str(patient.get("medicines_text") or "").lower()

    def has(kind):
        return float(any(word in text for word in REAL_CLASSES[kind]))

    def number(name):
        value = patient.get(name)
        return np.nan if value is None or pd.isna(value) else float(value)

    return {
        "age": number("age"),
        "sex_female": float(patient.get("sex") == "female"),
        "bmi": number("bmi"),
        "years_with_diabetes": number("years_with_diabetes"),
        "hba1c": number("hba1c_percent"),
        "egfr": number("egfr"),
        "takes_sulfonylurea": has("sulfonylurea"),
        "takes_insulin": has("insulin"),
        "takes_premixed": has("premixed"),
        "takes_basal": has("basal"),
        "takes_metformin": has("metformin"),
        "takes_sglt2": has("sglt2"),
        "takes_dpp4": has("dpp4"),
        "beta_blocker": float(bool(patient.get("takes_beta_blocker"))),
        "heart_disease": float(bool(patient.get("heart_disease"))),
        "hypo_history": float(bool(patient.get("hypoglycaemia_history"))),
    }


def _real_job(job) -> pd.DataFrame:
    from rozmarra.twin.fit import load_patient

    patient, timeseries, events, twin = job
    data = load_patient(patient, timeseries, events)
    if data is None:
        return pd.DataFrame()
    profile = profile_from_values(
        twin["fitted"],
        {
            "G_b": twin["G_b"],
            "I_b": twin["I_b"],
            "body_weight": twin["body_weight"],
            "egfr": twin["egfr"],
            "cr_factor": twin["cr_factor"],
            "source": "fitted twin",
        },
    )
    wearables = {}
    for signal in ("heart_rate", "mets", "steps"):
        rows = timeseries[timeseries.signal == signal]
        if len(rows):
            wearables[signal] = _grid(
                rows.timestamp_local,
                rows.value,
                data.start,
                data.minutes,
                "sum" if signal == "steps" else "mean",
            )
    ps = PatientSeries(
        patient_id=data.patient_id,
        start=data.start,
        minutes=data.minutes,
        cgm_minutes=data.cgm_minute.astype(float),
        cgm_values=data.cgm_value,
        interval=data.interval_min,
        meals=data.meals,
        doses=data.doses,
        activities=[],
        fasts=[],
        record=real_record_features(patient),
        profile=profile,
        wearables=wearables,
    )
    window = [(int(data.cgm_minute[0]) + 120, int(data.cgm_minute[-1]) - 60)]
    labels = point_labels(
        data.cgm_minute, data.cgm_value, data.interval_min, window, step_min=data.interval_min
    )
    labels_54 = point_labels(
        data.cgm_minute,
        data.cgm_value,
        data.interval_min,
        window,
        threshold=54.0,
        step_min=data.interval_min,
    )
    if labels.empty:
        return pd.DataFrame()
    table = point_features(ps, labels["minute"].to_numpy(), TwinForecaster(ps))
    table.insert(0, "patient_id", ps.patient_id)
    table.insert(1, "dataset", data.dataset)
    table.insert(2, "fold", fold_of(ps.patient_id))
    table["minute"] = labels["minute"].to_numpy()
    table["held_out_day"] = table["minute"] >= data.split_minute
    table["label_e1"] = labels["label"].to_numpy()
    table["usable_e1"] = labels["usable"].to_numpy()
    by_minute = labels_54.set_index("minute")
    table["label_e1_54"] = table["minute"].map(by_minute["label"])
    table["usable_e1_54"] = table["minute"].map(by_minute["usable"]).fillna(False).astype(bool)
    return table


def real_jobs():
    from rozmarra.twin.report import usable_patients

    timeseries = pd.read_parquet(PROCESSED_DIR / "timeseries.parquet")
    events = pd.read_parquet(PROCESSED_DIR / "events.parquet")
    patients = usable_patients(pd.read_parquet(PROCESSED_DIR / "patients.parquet"))
    twins = {t["patient_id"]: t for t in load_twins()}
    ts_groups = dict(tuple(timeseries.groupby("patient_id")))
    ev_groups = dict(tuple(events.groupby("patient_id")))
    for _, patient in patients.iterrows():
        pid = patient["patient_id"]
        if pid in twins and pid in ts_groups:
            yield patient, ts_groups[pid], ev_groups.get(pid, events.iloc[:0]), twins[pid]


def build_feature_tables(workers: int = 6, out_dir: Path = FEATURE_DIR) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        synthetic = [r for part in pool.map(_synthetic_part, synthetic_jobs()) for r in part]
        real = list(pool.map(_real_job, real_jobs(), chunksize=2))
    e1 = pd.concat([r["e1"] for r in synthetic], ignore_index=True)
    e2 = pd.concat([r["e2"] for r in synthetic if len(r["e2"])], ignore_index=True)
    real_table = pd.concat([r for r in real if len(r)], ignore_index=True)
    for name, frame in (("e1_synthetic", e1), ("e2_synthetic", e2), ("e1_real", real_table)):
        frame.to_parquet(out_dir / f"{name}.parquet", index=False)
    return {"e1_synthetic": len(e1), "e2_synthetic": len(e2), "e1_real": len(real_table)}


__all__ = ["build_feature_tables", "record_features", "DAY"]

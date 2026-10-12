"""The whole-fast forecast F1 (docs/prd.md, Section 10, FR-C4).

Before the fast begins, the estimated twin simulates the plan with many parameter samples.
The simulation gives the twin's view: the share of samples with low blood sugar during the
fast, the expected minutes below 70 mg/dL, the lowest value and its time, and the share of
samples with high blood sugar after the meal that breaks the fast. A logistic regression
then combines the twin's view with the patient's CGM history from the 14 days before the
fast and the health record. It gives the estimated chance of low blood sugar during the
fast, and the estimated chance of high blood sugar after the fast is broken.

The models learn on the episodes of the training virtual patients and are tested on the
episodes of the test virtual patients. They are stored as plain numbers in JSON files.
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from rozmarra.config import MODELS_DIR, PROCESSED_DIR, RANDOM_SEED
from rozmarra.fasting.plan import FastingPlan
from rozmarra.ml.labels import find_events
from rozmarra.twin.simulate import PlanSimulation, simulate_plan

EPISODE_SAMPLES = 30
LOW, HIGH = 70.0, 250.0
PEAK_CAP = 600.0
HISTORY_DAYS = 14

LOW_FEATURES = [
    "twin_low_share",
    "twin_lowest_p10",
    "twin_lowest_p50",
    "twin_minutes_below_70",
    "hist_tbr_14d",
    "hist_lows_14d",
    "hist_cv_14d",
    "hist_mean_14d",
    "fast_hours",
    "water_allowed",
    "takes_insulin",
    "takes_sulfonylurea",
    "age",
    "egfr",
    "idf_dar_total",
]
HIGH_FEATURES = [
    "twin_high_share",
    "twin_peak_p50",
    "breaking_carbs",
    "breaking_fast_food",
    "hist_mean_14d",
    "hist_cv_14d",
    "hist_tar_14d",
    "hba1c",
    "takes_insulin",
]


def _runs(
    curve: np.ndarray,
    start: int,
    end: int,
    above: float | None = None,
    below: float | None = None,
    minimum: int = 15,
) -> bool:
    segment = curve[max(0, start) : max(0, end)]
    inside = segment < below if below is not None else segment > above
    if not inside.any():
        return False
    changes = np.diff(np.concatenate([[0], inside.astype(int), [0]]))
    lengths = np.nonzero(changes == -1)[0] - np.nonzero(changes == 1)[0]
    return bool((lengths >= minimum).any())


def twin_outcomes(simulation: PlanSimulation, plan: FastingPlan) -> dict:
    """The twin's view of a plan, from every parameter sample."""

    def minute(t):
        return int((t - simulation.start) / timedelta(minutes=1))

    a, b = minute(plan.fast_start), minute(plan.fast_end)
    curves = simulation.curves
    lows = [_runs(c, a, b, below=LOW) for c in curves]
    minutes_below = [(c[max(0, a) : b] < LOW).sum() for c in curves]
    p50 = simulation.p50[max(0, a) : b]
    out = {
        "twin_low_share": float(np.mean(lows)),
        "twin_minutes_below_70": float(np.mean(minutes_below)),
        "twin_lowest_p50": float(p50.min()) if len(p50) else np.nan,
        "twin_lowest_p10": float(simulation.p10[max(0, a) : b].min()) if len(p50) else np.nan,
        "twin_lowest_minute": int(a + int(np.argmin(p50))) if len(p50) else None,
    }
    meal = plan.breaking_meal
    if meal is not None:
        m = minute(meal.time)
        out["twin_high_share"] = float(np.mean([_runs(c, m, m + 240, above=HIGH) for c in curves]))
        # Twins with extreme fitted parameters can predict peaks above 1,000 mg/dL, which is
        # not physiological, so the peak is capped.
        out["twin_peak_p50"] = min(float(simulation.p50[m : m + 240].max()), PEAK_CAP)
        out["breaking_carbs"] = meal.carbs_g
        out["breaking_fast_food"] = float(meal.food_category.value == "fast_absorbing")
    return out


def history_features(
    cgm_minutes: np.ndarray, cgm_values: np.ndarray, at_minute: float, interval: int = 5
) -> dict:
    """CGM history from the 14 days before the fast."""
    window = (cgm_minutes < at_minute) & (cgm_minutes >= at_minute - HISTORY_DAYS * 1440)
    values = cgm_values[window]
    if len(values) < 12:
        return {
            "hist_tbr_14d": np.nan,
            "hist_lows_14d": np.nan,
            "hist_cv_14d": np.nan,
            "hist_mean_14d": np.nan,
            "hist_tar_14d": np.nan,
        }
    events = find_events(cgm_minutes[window], values, interval)
    return {
        "hist_tbr_14d": float(np.mean(values < 70)),
        "hist_lows_14d": float(len(events)),
        "hist_cv_14d": float(values.std() / values.mean()),
        "hist_mean_14d": float(values.mean()),
        "hist_tar_14d": float(np.mean(values > 250)),
    }


def plan_features(plan: FastingPlan, record_values: dict) -> dict:
    return {
        "fast_hours": plan.fast_hours,
        "water_allowed": float(plan.water_allowed),
        **{
            k: record_values.get(k, np.nan)
            for k in (
                "takes_insulin",
                "takes_sulfonylurea",
                "age",
                "egfr",
                "idf_dar_total",
                "hba1c",
            )
        },
    }


# --- Building the episode table from the synthetic cohort --------------------------------


def _episode_part(job) -> list[dict]:
    from rozmarra.ml.datasets import record_features
    from rozmarra.synth.cohort import build_timeline, make_virtual_twins

    part, folder, count, seed = job
    timeseries = pd.read_parquet(part, columns=["patient_id", "timestamp_local", "signal", "value"])
    cgm_all = timeseries[timeseries.signal == "glucose_cgm"]
    ids = sorted(cgm_all.patient_id.unique())
    events = pd.read_parquet(folder / "events", filters=[("patient_id", "in", ids)])
    labels = pd.read_parquet(folder / "labels_e2", filters=[("patient_id", "in", ids)])
    twins = make_virtual_twins(count, seed)
    rows = []
    for index, (twin, group) in enumerate(twins):
        pid = twin.record.patient_id
        if pid not in ids:
            continue
        timeline = build_timeline(twin, group, seed * 1000 + index)
        cgm = cgm_all[cgm_all.patient_id == pid]
        cgm_minutes = (
            (cgm.timestamp_local - pd.Timestamp(timeline.start)) / pd.Timedelta(minutes=1)
        ).to_numpy()
        cgm_values = cgm.value.to_numpy()
        patient_events = events[events.patient_id == pid]
        logged = patient_events[patient_events.event_type == "meal"]
        record_values = record_features(twin.record, timeline.start.date())
        for episode in timeline.episodes:
            plan = episode.plan.model_copy(deep=True)
            # The system knows only the logged carbohydrates of each planned meal.
            for meal in plan.meals:
                match = logged[
                    (logged.start - pd.Timestamp(meal.time)).abs() < pd.Timedelta(minutes=1)
                ]
                if len(match):
                    meal.carbs_g = float(json.loads(match.iloc[0].details)["carbs_g"])
            simulation = simulate_plan(
                plan,
                twin.profile,
                twin.record.usual_doses(),
                samples=EPISODE_SAMPLES,
                keep_curves=True,
                seed=RANDOM_SEED + index,
            )
            a = timeline.minute(plan.fast_start)
            b = timeline.minute(plan.fast_end)
            inside = (cgm_minutes >= a - 60) & (cgm_minutes <= b)
            events_low = find_events(cgm_minutes[inside], cgm_values[inside], 5)
            low = any(a <= e.start <= b for e in events_low)
            e2 = labels[(labels.patient_id == pid) & (labels.episode == episode.number)]
            rows.append(
                {
                    "patient_id": pid,
                    "group": group,
                    "episode": episode.number,
                    "template_id": plan.template_id,
                    **twin_outcomes(simulation, plan),
                    **history_features(cgm_minutes, cgm_values, a),
                    **plan_features(plan, record_values),
                    "label_low": int(low),
                    "label_high": int(e2.label.iloc[0]) if len(e2) else np.nan,
                    "usable_high": bool(e2.usable.iloc[0]) if len(e2) else False,
                }
            )
    return rows


def build_episode_table(
    workers: int = 6, count: int = 500, seed: int = RANDOM_SEED
) -> pd.DataFrame:
    folder = PROCESSED_DIR / "synthetic"
    jobs = [
        (part, folder, count, seed)
        for part in sorted((folder / "timeseries").glob("part-*.parquet"))
    ]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = [row for part in pool.map(_episode_part, jobs) for row in part]
    table = pd.DataFrame(rows)
    out = PROCESSED_DIR / "features" / "episodes.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(out, index=False)
    return table


# --- The episode models ------------------------------------------------------------------


class EpisodeModel:
    """A logistic regression stored as plain numbers."""

    def __init__(
        self,
        name: str,
        features: list[str],
        fill: dict,
        mean: list,
        scale: list,
        coef: list,
        intercept: float,
    ):
        self.name, self.features, self.fill = name, features, fill
        self.mean, self.scale = np.array(mean), np.array(scale)
        self.coef, self.intercept = np.array(coef), intercept

    @classmethod
    def fit(cls, name: str, table: pd.DataFrame, features: list[str], label: str):
        fill = {f: float(table[f].median()) if table[f].notna().any() else 0.0 for f in features}
        X = table[features].fillna(fill).to_numpy(dtype=float)
        mean, scale = X.mean(axis=0), X.std(axis=0)
        scale[scale == 0] = 1.0
        model = LogisticRegression(C=1.0, max_iter=2000)
        model.fit((X - mean) / scale, table[label].astype(int))
        return cls(
            name,
            features,
            fill,
            mean.tolist(),
            scale.tolist(),
            model.coef_[0].tolist(),
            float(model.intercept_[0]),
        )

    def predict(self, table: pd.DataFrame) -> np.ndarray:
        X = table[self.features].fillna(self.fill).to_numpy(dtype=float)
        z = ((X - self.mean) / self.scale) @ self.coef + self.intercept
        return 1 / (1 + np.exp(-z))

    def save(self, folder: Path = MODELS_DIR) -> Path:
        path = folder / f"{self.name}.json"
        path.write_text(
            json.dumps(
                {
                    "name": self.name,
                    "features": self.features,
                    "fill": self.fill,
                    "mean": self.mean.tolist(),
                    "scale": self.scale.tolist(),
                    "coef": self.coef.tolist(),
                    "intercept": self.intercept,
                },
                indent=1,
            ),
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, name: str, folder: Path = MODELS_DIR) -> EpisodeModel:
        data = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
        return cls(
            data["name"],
            data["features"],
            data["fill"],
            data["mean"],
            data["scale"],
            data["coef"],
            data["intercept"],
        )


def _scores(y, p) -> dict:
    if len(np.unique(y)) < 2:
        return {"auroc": None, "auprc": None}
    return {
        "auroc": round(float(roc_auc_score(y, p)), 3),
        "auprc": round(float(average_precision_score(y, p)), 3),
    }


def train_episode_models(table: pd.DataFrame | None = None) -> dict:
    from rozmarra.ml.evaluate import ranking_with_intervals

    table = (
        table
        if table is not None
        else pd.read_parquet(PROCESSED_DIR / "features" / "episodes.parquet")
    )
    table = table.assign(twin_peak_p50=table["twin_peak_p50"].clip(upper=PEAK_CAP))
    train, test = table[table.group == "training"], table[table.group == "test"].copy()
    report = {}
    for name, features, label, twin_feature in (
        ("f1_low", LOW_FEATURES, "label_low", "twin_low_share"),
        ("f1_high", HIGH_FEATURES, "label_high", "twin_high_share"),
    ):
        rows_train = train[train[label].notna()]
        rows_test = test[test[label].notna()].copy()
        model = EpisodeModel.fit(name, rows_train, features, label)
        model.save()
        rows_test["p"] = model.predict(rows_test)
        y = rows_test[label].astype(int).to_numpy()
        report[name] = {
            "episodes": int(len(rows_test)),
            "patients": int(rows_test.patient_id.nunique()),
            "episodes_with_event": int(y.sum()),
            **ranking_with_intervals(rows_test, label, "p", 1000),
            "brier": round(float(brier_score_loss(y, rows_test.p)), 4),
            "twin_alone": _scores(y, rows_test[twin_feature].fillna(0).to_numpy()),
        }
        if name == "f1_low":
            report[name]["idf_dar_alone"] = _scores(y, rows_test.idf_dar_total.fillna(0).to_numpy())
    return report

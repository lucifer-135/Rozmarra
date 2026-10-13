"""Evaluation of the prediction models (docs/techstack.md, Section 8, and docs/prd.md, Section 15).

- Synthetic data: the models learn on the 400 training virtual patients and are tested on
  the 100 test virtual patients, whose donors come only from the real test group.
- Real data: five-fold cross-validation grouped by person. Each fold is tested only on the
  held-out days of its patients, on which the patients' twins were not fitted.
- Metrics: AUROC, AUPRC, the Brier score, a calibration curve, sensitivity, specificity and
  balanced accuracy at both alert thresholds, the share of low blood sugar events with an
  alert in the hour before them, the median warning time, and false alerts per patient per
  day. An alert is not repeated within 30 minutes unless the chance rises by 10 percentage
  points (ml/alerts.py). Alert level A detects 80% of the events of the validation patients.
- Confidence intervals: 95% intervals from bootstrap samples drawn by patient.
- Baselines: the last glucose value, a straight-line trend, the IDF-DAR score alone, a model
  that uses only CGM data, and the twin alone. The ablation study compares models that use
  one data stream each with the model that uses all streams.
- Only time points that meet the 70% data completeness rule are scored.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from rozmarra.config import MODELS_DIR, RANDOM_SEED, REPORTS_DIR
from rozmarra.ml.alerts import event_runs, raise_alerts
from rozmarra.ml.datasets import FEATURE_DIR
from rozmarra.ml.features import (
    ALL_POINT_FEATURES,
    CGM_FEATURES,
    E2_FEATURES,
    HISTORY_FEATURES,
    RECORD_FEATURES,
    WEARABLE_FEATURES,
)
from rozmarra.ml.train import TrainedModel, fit_model

BOOTSTRAPS = 1000
BOOTSTRAPS_SMALL = 200
HORIZON = {"e1": 60, "e1_54": 60, "e1_120": 120, "e3": 60}

# On real data, the full model leaves out the health record. The real records are sparse and
# constant for each patient, and a comparison on validation patients (never the test patients)
# showed better results without them.
REAL_FEATURES = [f for f in ALL_POINT_FEATURES if f not in RECORD_FEATURES]

ABLATION = {
    "health record alone": RECORD_FEATURES,
    "wearables alone": WEARABLE_FEATURES,
    "CGM alone": CGM_FEATURES + HISTORY_FEATURES,
    "CGM and wearables": CGM_FEATURES + HISTORY_FEATURES + WEARABLE_FEATURES,
    "all streams": ALL_POINT_FEATURES,
}


# --- Metrics -----------------------------------------------------------------------------


def _safe(fn, y, s):
    if len(np.unique(y)) < 2:
        return None
    return float(fn(y, s))


def ranking_metrics(y: np.ndarray, score: np.ndarray) -> dict:
    """AUROC and AUPRC. A missing baseline score counts as the median score, which is neutral."""
    score = np.asarray(score, dtype=float)
    if not np.isfinite(score).all():
        finite = score[np.isfinite(score)]
        score = np.where(np.isfinite(score), score, np.median(finite) if len(finite) else 0.0)
    return {
        "auroc": _safe(roc_auc_score, y, score),
        "auprc": _safe(average_precision_score, y, score),
    }


def threshold_metrics(
    frame: pd.DataFrame, y: np.ndarray, p: np.ndarray, threshold: float, step: int
) -> dict:
    pos, neg = y == 1, y == 0
    flagged = p >= threshold
    sensitivity = float(np.mean(flagged[pos])) if pos.any() else None
    specificity = float(np.mean(~flagged[neg])) if neg.any() else None
    alert = raise_alerts(frame, p, threshold)
    runs = event_runs(frame, y, step)
    detected, warnings = 0, []
    run_ids = np.unique(runs[runs >= 0])
    minutes = frame["minute"].to_numpy()
    for r in run_ids:
        members = runs == r
        if alert[members].any():
            detected += 1
            event_start = minutes[members].max() + step
            warnings.append(event_start - minutes[members & alert].min())
    days = len(frame) * step / 1440
    return {
        "threshold": round(float(threshold), 4),
        "sensitivity_points": _round(sensitivity),
        "specificity_points": _round(specificity),
        "balanced_accuracy": _round(
            None if sensitivity is None else (sensitivity + specificity) / 2
        ),
        "events": int(len(run_ids)),
        "events_detected_in_time": int(detected),
        "event_sensitivity": _round(detected / len(run_ids) if len(run_ids) else None),
        "median_warning_minutes": float(np.median(warnings)) if warnings else None,
        "false_alerts_per_patient_day": _round(float((alert & neg).sum() / days) if days else None),
    }


def _round(value, digits=3):
    return None if value is None else round(float(value), digits)


def calibration_curve(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    rows = []
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        inside = (p >= low) & (p <= high)
        if inside.sum():
            rows.append(
                {
                    "mean_predicted": round(float(p[inside].mean()), 4),
                    "observed_rate": round(float(y[inside].mean()), 4),
                    "count": int(inside.sum()),
                }
            )
    return rows


def bootstrap(frame: pd.DataFrame, metric_fn, n: int, seed: int = RANDOM_SEED) -> dict:
    """95% intervals of each metric from bootstrap samples drawn by patient."""
    rng = np.random.default_rng(seed)
    groups = frame.groupby("patient_id").indices
    keys = list(groups)
    results: dict[str, list[float]] = {}
    for _ in range(n):
        chosen = rng.choice(len(keys), size=len(keys), replace=True)
        index = np.concatenate([groups[keys[c]] for c in chosen])
        for name, value in metric_fn(frame.iloc[index]).items():
            if value is not None:
                results.setdefault(name, []).append(value)
    return {
        name: [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]
        for name, v in results.items()
        if len(v) >= n * 0.5
    }


def full_report(
    frame: pd.DataFrame,
    y_col: str,
    p_col: str,
    thresholds: dict[str, float],
    step: int,
    n_boot: int = BOOTSTRAPS,
) -> dict:
    y = frame[y_col].astype(int).to_numpy()
    p = frame[p_col].to_numpy()
    report = {
        "time_points": int(len(frame)),
        "patients": int(frame["patient_id"].nunique()),
        "positive_time_points": int(y.sum()),
        **{k: _round(v) for k, v in ranking_metrics(y, p).items()},
        "brier": _round(brier_score_loss(y, p), 4),
        "calibration": calibration_curve(y, p),
        "thresholds": {
            name: threshold_metrics(frame, y, p, t, step) for name, t in thresholds.items()
        },
    }
    report["confidence_intervals_95"] = bootstrap_with_events(
        frame, y, p, thresholds["sensitivity_80"], step, n_boot
    )
    return report


def bootstrap_with_events(
    frame: pd.DataFrame,
    y: np.ndarray,
    p: np.ndarray,
    threshold: float,
    step: int,
    n: int,
    seed: int = RANDOM_SEED,
) -> dict:
    """Bootstrap by patient. Alerts within a patient do not change when patients are
    resampled, so the event counts of each patient are computed once and then summed."""
    alert = raise_alerts(frame, p, threshold)
    runs = event_runs(frame, y, step)
    groups = frame.groupby("patient_id").indices
    keys = list(groups)
    counts = {}
    for key in keys:
        index = groups[key]
        patient_runs = runs[index]
        ids = np.unique(patient_runs[patient_runs >= 0])
        detected = sum(alert[index][patient_runs == r].any() for r in ids)
        counts[key] = (len(ids), detected, int((alert[index] & (y[index] == 0)).sum()), len(index))
    table = np.array([counts[k] for k in keys], dtype=float)
    rng = np.random.default_rng(seed)
    results: dict[str, list[float]] = {}
    for _ in range(n):
        chosen = rng.choice(len(keys), size=len(keys), replace=True)
        index = np.concatenate([groups[keys[c]] for c in chosen])
        values = ranking_metrics(y[index], p[index])
        values["brier"] = float(brier_score_loss(y[index], p[index]))
        total = table[chosen].sum(axis=0)
        values["event_sensitivity"] = total[1] / total[0] if total[0] else None
        values["false_alerts_per_patient_day"] = total[2] / (total[3] * step / 1440)
        for name, value in values.items():
            if value is not None:
                results.setdefault(name, []).append(value)
    return {
        name: [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]
        for name, v in results.items()
        if len(v) >= n * 0.5
    }


def ranking_with_intervals(frame: pd.DataFrame, y_col: str, score_col: str, n_boot: int) -> dict:
    y = frame[y_col].astype(int).to_numpy()
    values = ranking_metrics(y, frame[score_col].to_numpy())
    values = {k: _round(v) for k, v in values.items()}
    values["confidence_intervals_95"] = bootstrap(
        frame,
        lambda s: ranking_metrics(s[y_col].astype(int).to_numpy(), s[score_col].to_numpy()),
        n_boot,
    )
    return values


# --- Baseline scores (a higher score means a higher risk) ---------------------------------


def baseline_scores(table: pd.DataFrame, horizon: int, below: bool = True) -> dict[str, np.ndarray]:
    sign = -1.0 if below else 1.0
    line = table["cgm_now"] + table["cgm_slope_30"].fillna(0) * horizon
    twin = (
        table[["twin_30", "twin_60"]].min(axis=1)
        if below
        else table[["twin_30", "twin_60"]].max(axis=1)
    )
    if horizon >= 120:
        twin = table["twin_min_120"] if below else table["twin_120"]
    scores = {
        "last glucose value": sign * table["cgm_now"].to_numpy(),
        "straight-line trend": sign * line.to_numpy(),
        "twin alone": sign * twin.to_numpy(),
    }
    if table["idf_dar_total"].notna().any():
        scores["IDF-DAR score alone"] = table["idf_dar_total"].fillna(0).to_numpy()
    return scores


# --- Synthetic data ----------------------------------------------------------------------


def evaluate_synthetic_point_target(
    table: pd.DataFrame, target: str, full: bool
) -> tuple[dict, TrainedModel]:
    label, usable = f"label_{target}", f"usable_{target}"
    rows = table[table[usable] & table[label].notna()].copy()
    train, test = rows[rows.group == "training"], rows[rows.group == "test"].copy()
    model = fit_model(train, ALL_POINT_FEATURES, label, target, event_step=5)
    test["p"] = model.predict(test)
    thresholds = {
        "sensitivity_80": model.threshold_sensitivity,
        "balanced": model.threshold_balanced,
    }
    report = full_report(test, label, "p", thresholds, 5, BOOTSTRAPS if full else BOOTSTRAPS_SMALL)
    report["training"] = model.info
    if not full:
        return report, model

    below = target != "e3"
    for name, score in baseline_scores(test, HORIZON[target], below).items():
        test[f"baseline_{name}"] = score
    report["baselines"] = {
        name: ranking_with_intervals(test, label, f"baseline_{name}", BOOTSTRAPS_SMALL)
        for name in baseline_scores(test, HORIZON[target], below)
    }
    ablation = {}
    for name, features in ABLATION.items():
        sub = fit_model(train, features, label, f"{target}_{name}")
        test[f"ablation_{name}"] = sub.predict(test) if name != "all streams" else test["p"]
        ablation[name] = ranking_with_intervals(test, label, f"ablation_{name}", BOOTSTRAPS_SMALL)
    report["ablation"] = ablation
    report["baselines"]["model with CGM data only"] = ablation["CGM alone"]

    groups = {
        "insulin": test.takes_insulin == 1,
        "sulfonylurea without insulin": (test.takes_sulfonylurea == 1) & (test.takes_insulin == 0),
        "neither": (test.takes_sulfonylurea == 0) & (test.takes_insulin == 0),
        "age 65 or over": test.age >= 65,
        "age under 65": test.age < 65,
        "eGFR below 60": test.egfr < 60,
        "eGFR 60 or above": test.egfr >= 60,
        "female": test.sex_female == 1,
        "male": test.sex_female == 0,
    }
    report["subgroups"] = {}
    for name, mask in groups.items():
        sub = test[mask.to_numpy()]
        if len(sub) == 0:
            continue
        y = sub[label].astype(int).to_numpy()
        values = {k: _round(v) for k, v in ranking_metrics(y, sub["p"].to_numpy()).items()}
        values.update(
            threshold_metrics(sub, y, sub["p"].to_numpy(), model.threshold_sensitivity, 5)
        )
        values["patients"] = int(sub.patient_id.nunique())
        report["subgroups"][name] = values
    by_template = {}
    for template, sub in test.groupby("template_id"):
        y = sub[label].astype(int).to_numpy()
        by_template[template] = {
            k: _round(v) for k, v in ranking_metrics(y, sub["p"].to_numpy()).items()
        }
        by_template[template]["positive_time_points"] = int(y.sum())
    report["by_fasting_pattern"] = by_template
    return report, model


def evaluate_at_54(table: pd.DataFrame, model: TrainedModel) -> dict:
    """Score the E1 model against low blood sugar below 54 mg/dL."""
    rows = table[table.usable_e1_54 & table.label_e1_54.notna() & (table.group == "test")].copy()
    rows["p"] = model.predict(rows)
    thresholds = {
        "sensitivity_80": model.threshold_sensitivity,
        "balanced": model.threshold_balanced,
    }
    return full_report(rows, "label_e1_54", "p", thresholds, 5, BOOTSTRAPS_SMALL)


def evaluate_e2(table: pd.DataFrame) -> tuple[dict, TrainedModel]:
    rows = table[table.usable_e2].copy()
    features = ALL_POINT_FEATURES + E2_FEATURES
    train, test = rows[rows.group == "training"], rows[rows.group == "test"].copy()
    model = fit_model(train, features, "label_e2", "e2")
    test["p"] = model.predict(test)
    y = test.label_e2.astype(int).to_numpy()
    report = {
        "meals": int(len(test)),
        "patients": int(test.patient_id.nunique()),
        "meals_with_e2": int(y.sum()),
        **{k: _round(v) for k, v in ranking_metrics(y, test.p.to_numpy()).items()},
        "brier": _round(brier_score_loss(y, test.p), 4),
        "calibration": calibration_curve(y, test.p.to_numpy(), bins=5),
        "training": model.info,
    }
    report["thresholds"] = {}
    for name, t in (
        ("sensitivity_80", model.threshold_sensitivity),
        ("balanced", model.threshold_balanced),
    ):
        flagged = test.p.to_numpy() >= t
        sens = float(np.mean(flagged[y == 1])) if (y == 1).any() else None
        spec = float(np.mean(~flagged[y == 0])) if (y == 0).any() else None
        report["thresholds"][name] = {
            "threshold": round(t, 4),
            "sensitivity": _round(sens),
            "specificity": _round(spec),
        }
    test["baseline_planned_carbs"] = test.planned_carbs
    test["baseline_twin_peak"] = test.twin_peak_after_meal
    test["baseline_cgm"] = test.cgm_now
    report["confidence_intervals_95"] = bootstrap(
        test,
        lambda s: ranking_metrics(s.label_e2.astype(int).to_numpy(), s.p.to_numpy()),
        BOOTSTRAPS,
    )
    report["baselines"] = {
        "planned carbohydrates alone": ranking_with_intervals(
            test, "label_e2", "baseline_planned_carbs", BOOTSTRAPS_SMALL
        ),
        "twin peak alone": ranking_with_intervals(
            test, "label_e2", "baseline_twin_peak", BOOTSTRAPS_SMALL
        ),
        "glucose 2 hours before the meal": ranking_with_intervals(
            test, "label_e2", "baseline_cgm", BOOTSTRAPS_SMALL
        ),
    }
    return report, model


# --- Real data ---------------------------------------------------------------------------


def evaluate_real(table: pd.DataFrame) -> dict:
    rows = table[table.usable_e1].copy()
    predictions = []
    for fold in sorted(rows.fold.unique()):
        train = rows[rows.fold != fold]
        test = rows[(rows.fold == fold) & rows.held_out_day].copy()
        if test.empty or train.label_e1.sum() < 10:
            continue
        steps = np.where(train.dataset == "ShanghaiT2DM", 15, 5)
        model = fit_model(train, REAL_FEATURES, "label_e1", f"e1_real_fold{fold}", event_step=steps)
        test["p"] = model.predict(test)
        test["alert_threshold_sensitivity"] = model.threshold_sensitivity
        test["alert_threshold_balanced"] = model.threshold_balanced
        for name, features in ABLATION.items():
            if name == "all streams":
                test[f"ablation_{name}"] = test["p"]
            else:
                test[f"ablation_{name}"] = fit_model(train, features, "label_e1", name).predict(
                    test
                )
        predictions.append(test)
    pooled = pd.concat(predictions, ignore_index=True)
    # Each fold has its own thresholds, so the alerts use each row's own threshold.
    pooled["p_scaled_sensitivity"] = pooled.p / pooled.alert_threshold_sensitivity
    pooled["p_scaled_balanced"] = pooled.p / pooled.alert_threshold_balanced
    report = {
        "note": (
            "Five-fold cross-validation grouped by person. Each fold is tested only on "
            "the held-out days of its patients. The real data contains no fasting "
            "days, so these results describe normal days. On real data, the full model leaves "
            "out the sparse health record, and the ablation row 'all streams' is this model."
        )
    }
    for dataset, sub in [("all", pooled)] + list(pooled.groupby("dataset")):
        interval = 15 if dataset == "ShanghaiT2DM" else 5
        y = sub.label_e1.astype(int).to_numpy()
        part = {
            "time_points": int(len(sub)),
            "patients": int(sub.patient_id.nunique()),
            "positive_time_points": int(y.sum()),
            **{k: _round(v) for k, v in ranking_metrics(y, sub.p.to_numpy()).items()},
            "brier": _round(brier_score_loss(y, sub.p), 4) if len(sub) else None,
        }
        if dataset != "all":
            part["thresholds"] = {
                "sensitivity_80": threshold_metrics(
                    sub, y, sub.p_scaled_sensitivity.to_numpy(), 1.0, interval
                ),
                "balanced": threshold_metrics(
                    sub, y, sub.p_scaled_balanced.to_numpy(), 1.0, interval
                ),
            }
        report[dataset] = part
    report["all"]["confidence_intervals_95"] = bootstrap(
        pooled,
        lambda s: ranking_metrics(s.label_e1.astype(int).to_numpy(), s.p.to_numpy()),
        BOOTSTRAPS,
    )
    report["all"]["calibration"] = calibration_curve(
        pooled.label_e1.astype(int).to_numpy(), pooled.p.to_numpy()
    )
    for name, score in baseline_scores(pooled, 60).items():
        pooled[f"baseline_{name}"] = score
    report["baselines"] = {
        name: ranking_with_intervals(pooled, "label_e1", f"baseline_{name}", BOOTSTRAPS_SMALL)
        for name in baseline_scores(pooled, 60)
    }
    report["ablation"] = {
        name: ranking_with_intervals(pooled, "label_e1", f"ablation_{name}", BOOTSTRAPS_SMALL)
        for name in ABLATION
    }
    report["baselines"]["model with CGM data only"] = report["ablation"]["CGM alone"]
    at_54 = pooled[pooled.usable_e1_54 & pooled.label_e1_54.notna()]
    report["at_54"] = ranking_with_intervals(at_54, "label_e1_54", "p", BOOTSTRAPS_SMALL)
    report["at_54"]["positive_time_points"] = int(at_54.label_e1_54.sum())
    return report


def run_all(write: bool = True) -> dict:
    synthetic = pd.read_parquet(FEATURE_DIR / "e1_synthetic.parquet")
    e2_table = pd.read_parquet(FEATURE_DIR / "e2_synthetic.parquet")
    real = pd.read_parquet(FEATURE_DIR / "e1_real.parquet")

    metrics: dict = {
        "created_on": date.today().isoformat(),
        "notes": [
            "Synthetic results come from simulated fasting days of virtual patients and partly "
            "reflect the team's modelling assumptions.",
            "Real results come from normal days of real patients in ShanghaiT2DM and CGMacros.",
        ],
        "synthetic": {},
    }
    e1_report, e1_model = evaluate_synthetic_point_target(synthetic, "e1", full=True)
    e1_report["at_54"] = evaluate_at_54(synthetic, e1_model)
    metrics["synthetic"]["e1"] = e1_report
    models = {"e1": e1_model}
    for target in ("e1_120", "e3"):
        report, model = evaluate_synthetic_point_target(synthetic, target, full=False)
        metrics["synthetic"][target] = report
        models[target] = model
    e2_report, e2_model = evaluate_e2(e2_table)
    metrics["synthetic"]["e2"] = e2_report
    models["e2"] = e2_model
    metrics["real"] = {"e1": evaluate_real(real)}
    if write:
        for model in models.values():
            model.save(MODELS_DIR)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    return metrics

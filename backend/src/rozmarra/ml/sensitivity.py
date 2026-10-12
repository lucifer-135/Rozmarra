"""The sensitivity analysis with the weaker sulfonylurea effect.

The real data identified the sulfonylurea effect poorly, and its fitted median was
γ_su = 0.5. The main cohort uses the population value γ_su = 3 (model card, Section 5.5).
This analysis creates a second cohort in which the virtual patients' sulfonylurea effect
centres on 0.5, and repeats the E1 evaluation on it. The main results stay unchanged.
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from rozmarra.config import PROCESSED_DIR, RANDOM_SEED, REPORTS_DIR
from rozmarra.ml.datasets import _synthetic_part, synthetic_jobs
from rozmarra.ml.evaluate import evaluate_synthetic_point_target
from rozmarra.synth.cohort import build_cohort

WEAK_GAMMA_SU = 0.5
OUT_DIR = PROCESSED_DIR / "synthetic_weak_su"
SUMMARY_NAME = "synthetic_summary_weak_sulfonylurea.json"


def run(workers: int = 6, count: int = 500, seed: int = RANDOM_SEED) -> dict:
    cohort = build_cohort(
        count, seed, workers, OUT_DIR, gamma_su_centre=WEAK_GAMMA_SU, summary_name=SUMMARY_NAME
    )
    jobs = synthetic_jobs(OUT_DIR, count, seed, WEAK_GAMMA_SU)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        parts = [r for part in pool.map(_synthetic_part, jobs) for r in part]
    table = pd.concat([p["e1"] for p in parts], ignore_index=True)
    report, _ = evaluate_synthetic_point_target(table, "e1", full=False)
    result = {
        "gamma_su_centre": WEAK_GAMMA_SU,
        "episodes_with_low_blood_sugar": cohort["episodes_with_low_blood_sugar"],
        "by_medicine": cohort["by_medicine"],
        "e1": {
            k: report[k]
            for k in (
                "auroc",
                "auprc",
                "brier",
                "positive_time_points",
                "time_points",
                "thresholds",
                "confidence_intervals_95",
            )
        },
    }
    path = REPORTS_DIR / "metrics.json"
    if path.exists():
        metrics = json.loads(path.read_text(encoding="utf-8"))
        metrics["sensitivity_weak_sulfonylurea"] = result
        path.write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    return result

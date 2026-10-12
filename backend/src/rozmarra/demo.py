"""Preparation of the demo patients and their saved results.

The demo runs from the files in data/demo, so it does not need the large datasets.
The build writes each demo patient's health record, a draft plan with the usual
medicines (Plan A), the twin, a synthetic history of 14 normal days followed by the
planned fast, and a summary. Later steps will add the predictions.
"""

from __future__ import annotations

import json
from pathlib import Path

from rozmarra.config import DEMO_DIR, REPORTS_DIR
from rozmarra.ehr.demo_patients import DEMO_FASTS, DEMO_PATIENTS
from rozmarra.ehr.store import write_bundle
from rozmarra.fasting.templates import build_plan, get_template
from rozmarra.formatting import long_date
from rozmarra.risk.idf_dar import calculate
from rozmarra.risk.rules import dehydration_caution
from rozmarra.synth.cohort import build_demo_days


def build_demo(folder: Path = DEMO_DIR) -> list[dict]:
    summaries = []
    for record in DEMO_PATIENTS:
        fast = DEMO_FASTS[record.patient_id]
        template = get_template(fast.template_id)
        plan = build_plan(
            fast.template_id, record.patient_id, fast.date, record.city, record.usual_doses()
        )
        plan_path = folder / "plans" / f"{record.patient_id}_plan_a.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        write_bundle(record, folder / "patients")

        score = calculate(record.idf_dar_inputs(fast.date, plan))
        caution = dehydration_caution(
            plan.water_allowed,
            plan.fast_hours,
            [m.name for m in record.medicines],
            record.egfr,
            record.age_on(fast.date),
        )
        summaries.append(
            {
                "patient_id": record.patient_id,
                "label": record.label_on(fast.date),
                "source": "synthetic",
                "fast": template.short_name,
                "fast_description": template.name,
                "template_id": template.id,
                "fast_date": fast.date.isoformat(),
                "fast_date_text": long_date(fast.date),
                "city": record.city,
                "fast_word": record.fast_word,
                "note": fast.note,
                "idf_dar_total": score.total,
                "idf_dar_category": score.category.value,
                "dehydration_caution": caution is not None,
                "plan_status": plan.status.value,
            }
        )
    twins = build_demo_days(DEMO_PATIENTS, DEMO_FASTS, folder / "fasting_days")
    twin_payload = {}
    for summary in summaries:
        twin = twins[summary["patient_id"]]
        summary["donor_twin"] = twin.donor_id
        profile = twin.profile
        twin_payload[summary["patient_id"]] = {
            "source": "synthetic patient with the twin parameters of a real donor",
            "donor_id": twin.donor_id,
            "G_b": profile.G_b,
            "I_b": profile.I_b,
            "body_weight": profile.body_weight,
            "egfr": profile.egfr,
            "cr_factor": profile.cr_factor,
            "cyp_factor": profile.cyp_factor,
            "names": list(profile.names),
            "log_mean": profile.log_mean.tolist(),
            "log_cov": profile.log_cov.tolist(),
        }
    (folder / "demo_twins.json").write_text(json.dumps(twin_payload, indent=1), encoding="utf-8")
    (folder / "demo_patients.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    plot_demo_days(folder / "fasting_days", REPORTS_DIR / "figures" / "demo_fasting_days.png")
    return summaries


def plot_demo_days(folder: Path, path: Path) -> Path:
    """Plot the last two normal days, the fast and the day after for each demo patient."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    timeseries = pd.read_parquet(folder / "timeseries.parquet")
    events = pd.read_parquet(folder / "events.parquet")
    fig, axes = plt.subplots(len(DEMO_PATIENTS), 1, figsize=(13, 3.2 * len(DEMO_PATIENTS)))
    for ax, record in zip(axes, DEMO_PATIENTS, strict=True):
        pid = record.patient_id
        fast = events[(events.patient_id == pid) & (events.event_type == "fast")].iloc[0]
        start, end = fast.start - pd.Timedelta(days=2), fast.end + pd.Timedelta(days=1)
        rows = timeseries[
            (timeseries.patient_id == pid)
            & (timeseries.timestamp_local >= start)
            & (timeseries.timestamp_local <= end)
        ]
        cgm = rows[rows.signal == "glucose_cgm"]
        heart = rows[rows.signal == "heart_rate"]
        ax.axvspan(fast.start, fast.end, color="#f5cba7", alpha=0.45, label="Fasting window")
        ax.axhspan(70, 180, color="#2e8b57", alpha=0.07, label="Target range (70 to 180 mg/dL)")
        ax.axhline(70, color="#b03a2e", linestyle="--", linewidth=0.8)
        ax.plot(
            cgm.timestamp_local,
            cgm.value,
            ".",
            markersize=2.5,
            color="#1f4e79",
            label="Synthetic CGM",
        )
        low = cgm[cgm.value < 70]
        ax.plot(
            low.timestamp_local,
            low.value,
            "v",
            markersize=4,
            color="#b03a2e",
            label="Below 70 mg/dL (Low)",
        )
        twin_axis = ax.twinx()
        twin_axis.plot(
            heart.timestamp_local, heart.value, color="#c0392b", linewidth=0.5, alpha=0.5
        )
        twin_axis.set_ylabel("Heart rate (beats per minute)", fontsize=8)
        fast_date = DEMO_FASTS[pid].date
        ax.set_title(
            f"{record.label_on(fast_date)}: {get_template(DEMO_FASTS[pid].template_id).short_name} "
            f"on {long_date(fast_date)} (synthetic data, usual medicines)",
            fontsize=10,
        )
        ax.set_ylabel("Glucose (mg/dL)")
        ax.legend(loc="upper left", fontsize=7, ncol=4)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path

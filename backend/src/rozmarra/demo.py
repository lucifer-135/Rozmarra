"""Preparation of the demo patients and their saved results.

The demo runs from the files in data/demo, so it does not need the large datasets.
Today the build writes each demo patient's health record, a draft plan with the
usual medicines (Plan A) and a summary. Later steps will add the twin forecasts
and the predictions.
"""

from __future__ import annotations

import json
from pathlib import Path

from rozmarra.config import DEMO_DIR
from rozmarra.ehr.demo_patients import DEMO_FASTS, DEMO_PATIENTS
from rozmarra.ehr.store import write_bundle
from rozmarra.fasting.templates import build_plan, get_template
from rozmarra.formatting import long_date
from rozmarra.risk.idf_dar import calculate
from rozmarra.risk.rules import dehydration_caution


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
    (folder / "demo_patients.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summaries

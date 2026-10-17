"""The patient endpoints of the Rozmarra API (docs/techstack.md, Section 10)."""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from rozmarra.api import services
from rozmarra.api.store import STORE
from rozmarra.fasting.activities import ACTIVITY_PRESETS
from rozmarra.fasting.meals import FOOD_CATEGORY_LABELS
from rozmarra.fasting.plan import FastingPlan
from rozmarra.fasting.templates import TEMPLATES, build_plan
from rozmarra.formatting import long_date
from rozmarra.medicines import MEDICINES, NON_DIABETES_CLASSES, get_medicine
from rozmarra.plans.render import render_message, render_plan
from rozmarra.risk.idf_dar import NOTE_OTHER_FASTS, calculate

router = APIRouter(tags=["Patients"])

CYP2C9_SENTENCES = {
    "*1/*1": "This patient has the usual CYP2C9 genotype.",
    "reduced": (
        "This patient carries a reduced-function CYP2C9 gene variant. Sulfonylureas such "
        "as glimepiride may stay in the body longer than usual."
    ),
}


PLAN_ID = Path(pattern=r"^[a-z0-9-]{1,20}$", description="For example plan-a or plan-b")


def _record_or_404(patient_id: str):
    try:
        return STORE.record(patient_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="The patient is not known.") from None


def _check(*plans: FastingPlan) -> None:
    problems = [p for plan in plans for p in services.plan_problems(plan)]
    if problems:
        raise HTTPException(status_code=422, detail=" ".join(problems))


def _doctor_name(name: str) -> str:
    """The doctor's name without a leading "Dr", because the approval text adds it."""
    return re.sub(r"^dr\b\.?\s*", "", name.strip(), flags=re.IGNORECASE).strip()


class ComparePlans(BaseModel):
    plan_a: FastingPlan
    plan_b: FastingPlan


class Approval(BaseModel):
    doctor_name: str
    plan: FastingPlan
    doctor_contact: str = Field("", max_length=200)


class TemplateRequest(BaseModel):
    template_id: str
    date: date


@router.get("/templates", summary="List the fasting templates")
def templates():
    return [
        {
            "id": t.id,
            "fast_type": t.fast_type.value,
            "name": t.name,
            "name_hi": t.name_hi,
            "short_name": t.short_name,
            "word_hi": t.word_hi,
            "description": t.description,
            "water_allowed": t.water_allowed,
            "glucose_notes": t.glucose_notes,
        }
        for t in TEMPLATES
    ]


@router.get("/plan-options", summary="The medicines, food types and activities for the plan form")
def plan_options():
    return {
        "medicines": [
            {
                "name": m.name,
                "display_name": m.display_name,
                "display_name_hi": m.display_name_hi,
                "medicine_class": m.medicine_class.value,
                "for_diabetes": m.medicine_class not in NON_DIABETES_CLASSES,
                "unit": m.unit,
                "standard_dose": m.standard_dose,
                "max_single_dose": m.max_single_dose,
            }
            for m in sorted(MEDICINES.values(), key=lambda m: m.display_name)
        ],
        "food_categories": [
            {"id": category.value, "label": label}
            for category, label in FOOD_CATEGORY_LABELS.items()
        ],
        "activities": [
            {"id": a.id, "label": a.label, "mets": a.mets, "minutes": a.minutes}
            for a in ACTIVITY_PRESETS
        ],
    }


@router.get("/patients", summary="List the patients who plan to fast, sorted by risk")
def patients():
    rows = []
    for patient_id, summary in STORE.summaries.items():
        record = STORE.record(patient_id)
        fast = STORE.fast(patient_id)
        forecast = services.default_summary(patient_id)
        rows.append(
            {
                "patient_id": patient_id,
                "label": record.label_on(fast.date),
                "name": record.full_name,
                "name_hi": record.full_name_hi,
                "age": record.age_on(fast.date),
                "source": "synthetic",
                "fast": summary["fast"],
                "template_id": fast.template_id,
                "fast_date": fast.date.isoformat(),
                "fast_date_text": long_date(fast.date),
                "idf_dar_total": summary["idf_dar_total"],
                "idf_dar_category": summary["idf_dar_category"],
                "chance_of_low_during_fast": forecast["chance_of_low_during_fast"],
                "dehydration_caution": summary["dehydration_caution"],
                "plan_status": STORE.plan_status(patient_id),
            }
        )
    return sorted(rows, key=lambda r: -r["chance_of_low_during_fast"]["value"])


@router.get("/patients/{patient_id}", summary="The health record summary and the data sources")
def patient(patient_id: str):
    record = _record_or_404(patient_id)
    fast = STORE.fast(patient_id)
    donor = STORE.demo_twins[patient_id]["donor_id"]
    genotype = record.cyp2c9
    return {
        "patient_id": patient_id,
        "source": "synthetic",
        "label": record.label_on(fast.date),
        "name": record.full_name,
        "name_hi": record.full_name_hi,
        "age": record.age_on(fast.date),
        "sex": record.sex,
        "city": record.city,
        "language": record.language,
        "fast_word": record.fast_word,
        "fasts_kept": record.fasts_kept,
        "occupation": record.occupation,
        "years_with_diabetes": record.years_with_diabetes_on(fast.date),
        "hba1c_percent": record.hba1c_percent,
        "fasting_glucose_mg_dl": record.fasting_glucose_mg_dl,
        "egfr": record.egfr,
        "creatinine_mg_dl": record.creatinine_mg_dl,
        "weight_kg": record.weight_kg,
        "height_cm": record.height_cm,
        "bmi": record.bmi,
        "blood_pressure": f"{record.systolic_bp}/{record.diastolic_bp} mm Hg",
        "resting_heart_rate": record.resting_heart_rate,
        "conditions": {
            "hypertension": record.hypertension,
            "chronic_kidney_disease": record.chronic_kidney_disease,
            "heart_disease": record.heart_disease.value,
        },
        "medicines": [
            {
                "name": m.name,
                "display": m.display,
                "display_name_hi": get_medicine(m.name).display_name_hi,
                "schedule": [
                    {
                        "time": s.time.strftime("%H:%M"),
                        "dose": s.dose,
                        "unit": get_medicine(m.name).unit,
                    }
                    for s in m.schedule
                ],
            }
            for m in record.medicines
        ],
        "cyp2c9": {
            "genotype": genotype,
            "activity_score": record.cyp2c9_activity_score,
            "clearance_factor": round(record.cyp2c9_clearance_factor, 2),
            "sentence": CYP2C9_SENTENCES["*1/*1" if genotype == "*1/*1" else "reduced"],
        },
        "planned_fast": {
            "template_id": fast.template_id,
            "date": fast.date.isoformat(),
            "date_text": long_date(fast.date),
            "note": fast.note,
        },
        "data_sources": [
            "The health record is synthetic and saved as a FHIR R4 Bundle.",
            f"The twin uses the fitted parameters of the real patient {donor} from open data.",
            "The glucose and smartwatch history is synthetic.",
        ],
    }


@router.get("/patients/{patient_id}/timeseries", summary="Glucose and wearable data with events")
def timeseries(patient_id: str, start: datetime | None = None, end: datetime | None = None):
    _record_or_404(patient_id)
    days = STORE.fasting_days
    rows = days["timeseries"][days["timeseries"].patient_id == patient_id]
    if start is not None:
        rows = rows[rows.timestamp_local >= start]
    if end is not None:
        rows = rows[rows.timestamp_local <= end]
    events = days["events"][days["events"].patient_id == patient_id]
    if start is not None:
        events = events[events.end >= start]
    if end is not None:
        events = events[events.start <= end]
    signals = {}
    for name, group in rows.groupby("signal"):
        signals[name] = {
            "unit": group.unit.iloc[0],
            "times": [t.isoformat(timespec="minutes") for t in group.timestamp_local],
            "values": services._round(group.value.to_numpy()),
        }
    return {
        "patient_id": patient_id,
        "source": "synthetic",
        "signals": signals,
        "events": [
            {
                "type": e.event_type,
                "start": e.start.isoformat(timespec="minutes"),
                "end": e.end.isoformat(timespec="minutes"),
                "details": json.loads(e.details) if isinstance(e.details, str) else e.details,
            }
            for e in events.itertuples()
        ],
    }


@router.get("/patients/{patient_id}/history", summary="A daily summary of the days before the fast")
def history(patient_id: str, days: int = Query(14, ge=7, le=14)):
    _record_or_404(patient_id)
    return services.daily_history(patient_id, days)


@router.get("/patients/{patient_id}/idf-dar", summary="The IDF-DAR 2021 risk score")
def idf_dar(patient_id: str):
    record = _record_or_404(patient_id)
    fast = STORE.fast(patient_id)
    plan = STORE.default_plan(patient_id)
    result = calculate(record.idf_dar_inputs(fast.date, plan))
    return {
        "patient_id": patient_id,
        "total": result.total,
        "category": result.category.value,
        "range": [result.min_total, result.max_total],
        "missing": list(result.missing),
        "items": [
            {
                "key": i.key,
                "label": i.label,
                "points": i.points,
                "max_points": i.max_points,
                "detail": i.detail,
            }
            for i in result.items
        ],
        "note": None if fast.template_id == "ramadan" else NOTE_OTHER_FASTS,
    }


PARAMETER_LABELS = {
    "S_G": "Glucose effectiveness (per minute)",
    "S_I": "Insulin sensitivity (per minute per µU/mL)",
    "beta": "Insulin release in response to glucose",
    "k_abs_factor": "Meal absorption speed factor",
    "meal_factor": "Meal size factor",
    "gamma_su": "Sulfonylurea effect on insulin release",
}


@router.get("/patients/{patient_id}/twin", summary="The twin parameters and the fit quality")
def twin(patient_id: str):
    _record_or_404(patient_id)
    profile = STORE.profile(patient_id)
    donor = STORE.donor(patient_id) or {}
    metrics = donor.get("metrics", {})
    two_hours = metrics.get("forecast_rmse_mg_dl", {}).get("120", {}).get("twin")
    return {
        "patient_id": patient_id,
        "donor": {
            "patient_id": donor.get("patient_id"),
            "dataset": donor.get("dataset"),
            "source": "real_open",
        },
        "parameters": [
            {
                "name": name,
                "label": PARAMETER_LABELS[name],
                "value": float(f"{math.exp(m):.4g}"),
                "log_sd": round(float(profile.log_cov[i][i]) ** 0.5, 3),
            }
            for i, (name, m) in enumerate(zip(profile.names, profile.log_mean, strict=True))
        ],
        "fixed": {
            "fasting_glucose_mg_dl": profile.G_b,
            "fasting_insulin_uu_ml": profile.I_b,
            "body_weight_kg": profile.body_weight,
            "egfr": profile.egfr,
            "cyp2c9_clearance_factor": round(profile.cyp_factor, 2),
        },
        "fit_quality": {
            "held_out_rmse_mg_dl": (metrics.get("test") or {}).get("rmse_mg_dl"),
            "held_out_mard_percent": (metrics.get("test") or {}).get("mard_percent"),
            "two_hour_forecast_rmse_mg_dl": two_hours,
            "sentence": (
                f"This twin uses the parameters of a real patient from "
                f"{donor.get('dataset')}. On that patient's held-out days, the twin's "
                f"2-hour forecasts differed from the measured glucose by {two_hours} "
                "mg/dL (RMSE)."
            )
            if two_hours
            else None,
        },
    }


@router.get("/patients/{patient_id}/plans/default", summary="The usual plan (Plan A)")
def default_plan(patient_id: str):
    _record_or_404(patient_id)
    return STORE.default_plan(patient_id).model_dump(mode="json")


@router.post("/patients/{patient_id}/plans/from-template", summary="Build a plan from a template")
def plan_from_template(patient_id: str, request: TemplateRequest):
    record = _record_or_404(patient_id)
    try:
        plan = build_plan(
            request.template_id, patient_id, request.date, record.city, record.usual_doses()
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    return plan.model_dump(mode="json")


@router.get("/patients/{patient_id}/plans", summary="The doctor's saved plans")
def saved_plans(patient_id: str):
    _record_or_404(patient_id)
    return {
        "status": STORE.plan_status(patient_id),
        "plans": {
            plan_id: plan.model_dump(mode="json")
            for plan_id, plan in STORE.saved_plans(patient_id).items()
        },
    }


@router.put("/patients/{patient_id}/plans/{plan_id}", summary="Save a plan as a draft")
def save_plan(patient_id: str, plan: FastingPlan, plan_id: str = PLAN_ID):
    _record_or_404(patient_id)
    _check(plan)
    return STORE.save_draft(patient_id, plan_id, plan).model_dump(mode="json")


@router.post("/patients/{patient_id}/simulate", summary="Simulate one fasting plan")
def simulate(patient_id: str, plan: FastingPlan):
    _record_or_404(patient_id)
    _check(plan)
    return services.simulate(patient_id, plan)


@router.post("/patients/{patient_id}/compare", summary="Simulate and compare two plans")
def compare(patient_id: str, plans: ComparePlans):
    _record_or_404(patient_id)
    _check(plans.plan_a, plans.plan_b)
    return {
        "plan_a": services.simulate(patient_id, plans.plan_a),
        "plan_b": services.simulate(patient_id, plans.plan_b),
    }


@router.get("/patients/{patient_id}/replay", summary="Replay the recorded fasting day")
def replay(patient_id: str, at: datetime | None = Query(None)):
    _record_or_404(patient_id)
    monitor = services.replay(patient_id)
    return monitor.overview() if at is None else monitor.at(at)


@router.post("/patients/{patient_id}/plans/{plan_id}/approve", summary="Approve a plan")
def approve(patient_id: str, approval: Approval, plan_id: str = PLAN_ID):
    _record_or_404(patient_id)
    doctor = _doctor_name(approval.doctor_name)
    if not doctor:
        raise HTTPException(status_code=422, detail="Please enter the name of the doctor.")
    _check(approval.plan)
    plan = STORE.approve(patient_id, plan_id, approval.plan, doctor, approval.doctor_contact)
    return {
        "plan": plan.model_dump(mode="json"),
        "approval_text": f"Approved by Dr {plan.approved_by} on {long_date(plan.approved_on)}",
    }


@router.get(
    "/patients/{patient_id}/plans/{plan_id}/document",
    response_class=HTMLResponse,
    summary="The printable patient fasting plan",
)
def document(
    patient_id: str,
    plan_id: str = PLAN_ID,
    lang: str = Query("en", pattern="^(en|hi)$"),
    format: str = Query("html", pattern="^(html|text)$"),
):
    record = _record_or_404(patient_id)
    plan = STORE.approved_plan(patient_id, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=409,
            detail=("The doctor must approve this plan before Rozmarra can print it."),
        )
    lowest = services.lowest_glucose_time(patient_id, plan)
    if format == "text":
        return PlainTextResponse(render_message(record, plan, lang, lowest))
    return HTMLResponse(render_plan(record, plan, lang, lowest))

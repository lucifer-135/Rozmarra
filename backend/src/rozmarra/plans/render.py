"""The printable patient fasting plan in English and Hindi (FR-E1 to FR-E5).

Every sentence of the plan comes from the fixed templates in the templates folder. This module
only fills in the patient's own facts: the names, dates, times, doses and the doctor's
approval. Rozmarra does not use AI to write medical advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from rozmarra.ehr.records import PatientRecord
from rozmarra.fasting.plan import FastingPlan
from rozmarra.fasting.templates import get_template, usual_medicines_in_window
from rozmarra.formatting import hindi_date, hindi_time, long_date, patient_time
from rozmarra.medicines import get_medicine
from rozmarra.plans.checks import check_times

LANGUAGES = ("en", "hi")
TEMPLATES = Path(__file__).parent / "templates"

# The form of the patient's word for the fast before "के" or "में" in Hindi.
HINDI_OBLIQUE = {"रोज़ा": "रोज़े"}

_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=lambda name: name is not None and name.endswith(".html.j2"),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
)


@dataclass
class MedicineLine:
    """One dose in the plan, with the information that the template sentence needs."""

    kind: str  # "same", "changed", "added" or "removed"
    name: str
    dose: str
    time: str
    usual_dose: str
    usual_time: str
    dose_changed: bool
    time_changed: bool


class _Words:
    """The formats of one language: times, dates, doses and lists."""

    def __init__(self, language: str, plan: FastingPlan):
        self.language = language
        self.plan = plan

    def date(self, day) -> str:
        return hindi_date(day) if self.language == "hi" else long_date(day)

    def when(self, moment: datetime) -> str:
        clock = hindi_time(moment.time()) if self.language == "hi" else patient_time(moment.time())
        if moment.date() == self.plan.date:
            return clock
        day = self.date(moment.date())
        return f"{day} को {clock}" if self.language == "hi" else f"{clock} on {day}"

    def dose(self, name: str, amount: float) -> str:
        unit = get_medicine(name).unit
        if self.language == "hi" and unit == "units":
            unit = "यूनिट"
        return f"{amount:g} {unit}"

    def medicine(self, name: str) -> str:
        medicine = get_medicine(name)
        return medicine.display_name_hi if self.language == "hi" else medicine.display_name

    def join(self, items: list[str]) -> str:
        word = " और " if self.language == "hi" else " and "
        if len(items) <= 1:
            return "".join(items)
        return ", ".join(items[:-1]) + word + items[-1]


def _medicine_lines(record: PatientRecord, plan: FastingPlan, words: _Words) -> list[MedicineLine]:
    lines: list[tuple[datetime, MedicineLine]] = []
    for dose in plan.medicines:
        usual_dose = dose.usual_dose if dose.usual_dose is not None else dose.dose
        usual_time = dose.usual_time or dose.time
        if dose.usual_dose is None:
            kind = "added"
        elif dose.is_changed:
            kind = "changed"
        else:
            kind = "same"
        lines.append(
            (
                dose.time,
                MedicineLine(
                    kind=kind,
                    name=words.medicine(dose.name),
                    dose=words.dose(dose.name, dose.dose),
                    time=words.when(dose.time),
                    usual_dose=words.dose(dose.name, usual_dose),
                    usual_time=words.when(usual_time),
                    dose_changed=dose.dose != usual_dose,
                    time_changed=dose.time != usual_time,
                ),
            )
        )
    # A usual dose that the plan no longer contains is a dose that the doctor removed.
    for usual in usual_medicines_in_window(plan, record.usual_doses()):
        kept = any(
            dose.name == usual.name and dose.usual_time == usual.usual_time
            for dose in plan.medicines
        )
        if not kept:
            text = words.dose(usual.name, usual.dose)
            lines.append(
                (
                    usual.time,
                    MedicineLine(
                        kind="removed",
                        name=words.medicine(usual.name),
                        dose=text,
                        time=words.when(usual.time),
                        usual_dose=text,
                        usual_time=words.when(usual.time),
                        dose_changed=False,
                        time_changed=False,
                    ),
                )
            )
    return [line for _, line in sorted(lines, key=lambda pair: pair[0])]


def plan_context(
    record: PatientRecord,
    plan: FastingPlan,
    language: str,
    lowest_time: datetime | None = None,
) -> dict:
    """The facts that the templates fill in. The sentences themselves are in the templates."""
    if language not in LANGUAGES:
        raise ValueError(f"The language '{language}' is not available. Please use en or hi.")
    if plan.approved_by is None or plan.approved_on is None:
        raise ValueError("The doctor must approve the plan before Rozmarra can print it.")
    words = _Words(language, plan)
    template = get_template(plan.template_id)
    fast_name = template.name_hi.split(":")[0] if language == "hi" else template.short_name
    word = record.fast_word
    breaking = plan.breaking_meal
    checks = [words.when(moment) for moment in check_times(plan, lowest_time)]
    return {
        "lang": language,
        "patient_name": record.full_name_hi if language == "hi" else record.full_name,
        "age": record.age_on(plan.date),
        "fast_name": fast_name,
        "word": word,
        "word_oblique": HINDI_OBLIQUE.get(word, word),
        "date": words.date(plan.date),
        "fast_start": words.when(plan.fast_start),
        "fast_end": words.when(plan.fast_end),
        "water_allowed": plan.water_allowed,
        "checks": words.join(checks),
        "check_list": checks,
        "meals": [
            {
                "time": words.when(meal.time),
                "label": meal.label_hi if language == "hi" and meal.label_hi else meal.label,
                "carbs": f"{meal.carbs_g:g}",
                "breaks_fast": meal.breaks_fast,
            }
            for meal in sorted(plan.meals, key=lambda meal: meal.time)
        ],
        "breaking_meal_time": words.when(breaking.time) if breaking else None,
        "medicines": _medicine_lines(record, plan, words),
        "doctor": plan.approved_by,
        "contact": (plan.approved_contact or "").strip(),
        "approved_on": words.date(plan.approved_on),
    }


def render_plan(
    record: PatientRecord, plan: FastingPlan, language: str, lowest_time: datetime | None = None
) -> str:
    """The printable plan as a complete HTML page."""
    context = plan_context(record, plan, language, lowest_time)
    return _ENV.get_template(f"{language}/plan.html.j2").render(**context)


def render_message(
    record: PatientRecord, plan: FastingPlan, language: str, lowest_time: datetime | None = None
) -> str:
    """A short version of the plan for SMS or WhatsApp. Rozmarra does not send any messages."""
    context = plan_context(record, plan, language, lowest_time)
    text = _ENV.get_template(f"{language}/message.txt.j2").render(**context)
    return " ".join(text.split())

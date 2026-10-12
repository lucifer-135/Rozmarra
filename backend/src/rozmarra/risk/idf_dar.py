"""The IDF-DAR 2021 fasting risk score.

The calculator follows the risk score table in the IDF-DAR Diabetes and Ramadan
Practical Guidelines 2021, as docs/techstack.md, Section 9, records it. It follows
these rules:

- The calculator never guesses missing information. It marks each missing item,
  scores the available items, and reports the range of totals that the missing
  items could produce.
- If a patient takes more than one treatment, the calculator uses the highest
  treatment score. This is a team assumption, because the guideline asks for one
  treatment type.
- The IDF-DAR score was designed for Ramadan. Rozmarra applies it to other fasts
  as an approximation, and the result says so.

Boundary assumptions, which follow the guideline's own cut-offs: HbA1c from 7.5% to
9.0% inclusive scores 1 point; eGFR from 30 to 44 scores 4 points, from 45 to 59
scores 2 points, and 60 or more scores 0 points; 10 or more years with diabetes
scores 1 point; and 16 or more fasting hours scores 1 point.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from enum import StrEnum

from rozmarra.medicines import MedicineClass, get_medicine


class DiabetesType(StrEnum):
    TYPE_1 = "type_1"
    TYPE_2 = "type_2"


class Hypoglycaemia(StrEnum):
    UNAWARE = "unaware"
    RECENT_SEVERE = "recent_severe"
    SEVERAL_PER_WEEK = "several_per_week"
    LESS_THAN_WEEKLY = "less_than_weekly"
    NONE = "none"


class Treatment(StrEnum):
    MIXED_INSULIN_SEVERAL_DAILY = "mixed_insulin_several_daily"
    BASAL_BOLUS_OR_PUMP = "basal_bolus_or_pump"
    MIXED_INSULIN_ONCE_DAILY = "mixed_insulin_once_daily"
    BASAL_INSULIN = "basal_insulin"
    GLIBENCLAMIDE = "glibenclamide"
    GLICLAZIDE_GLIMEPIRIDE_REPAGLINIDE = "gliclazide_glimepiride_or_repaglinide"
    OTHER = "other"


class SelfMonitoring(StrEnum):
    NEEDED_NOT_DONE = "needed_not_done"
    LESS_THAN_NEEDED = "less_than_needed"
    AS_NEEDED = "as_needed"


class AcuteComplications(StrEnum):
    LAST_3_MONTHS = "last_3_months"
    LAST_6_MONTHS = "last_6_months"
    LAST_12_MONTHS = "last_12_months"
    NONE = "none"


class Macrovascular(StrEnum):
    UNSTABLE = "unstable"
    STABLE = "stable"
    NONE = "none"


class Pregnancy(StrEnum):
    NOT_WITHIN_TARGETS = "not_within_targets"
    WITHIN_TARGETS = "within_targets"
    NOT_PREGNANT = "not_pregnant"


class Frailty(StrEnum):
    IMPAIRED_COGNITION_OR_FRAILTY = "impaired_cognition_or_frailty"
    OVER_70_WITHOUT_SUPPORT = "over_70_without_support"
    NONE = "none"


class PhysicalLabour(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    NONE = "none"


class FastingExperience(StrEnum):
    NEGATIVE = "negative"
    NEUTRAL_OR_POSITIVE = "neutral_or_positive"


class RiskCategory(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


@dataclass(frozen=True)
class IdfDarInputs:
    """The information that the score needs. None means that the information is missing."""

    diabetes_type: DiabetesType | None = None
    years_with_diabetes: float | None = None
    hypoglycaemia: Hypoglycaemia | None = None
    hba1c_percent: float | None = None
    treatments: tuple[Treatment, ...] | None = None
    self_monitoring: SelfMonitoring | None = None
    acute_complications: AcuteComplications | None = None
    macrovascular: Macrovascular | None = None
    egfr: float | None = None
    pregnancy: Pregnancy | None = None
    frailty: Frailty | None = None
    physical_labour: PhysicalLabour | None = None
    previous_fasting: FastingExperience | None = None
    fasting_hours: float | None = None


@dataclass(frozen=True)
class ItemScore:
    key: str
    label: str
    points: float | None  # None means that the information is missing.
    max_points: float
    detail: str

    @property
    def is_missing(self) -> bool:
        return self.points is None


@dataclass(frozen=True)
class IdfDarResult:
    items: tuple[ItemScore, ...]
    total: float
    category: RiskCategory
    min_total: float
    max_total: float
    min_category: RiskCategory
    max_category: RiskCategory

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(item.label for item in self.items if item.is_missing)

    @property
    def is_complete(self) -> bool:
        return not self.missing


MISSING = "Information missing"
NOTE_OTHER_FASTS = (
    "The IDF-DAR score was designed for Ramadan. Rozmarra applies it to other fasts as an "
    "approximation."
)


def category_for(total: float) -> RiskCategory:
    """Turn a total score into a category: 0 to 3 is Low, 3.5 to 6 is Moderate, above 6 is High."""
    if total <= 3:
        return RiskCategory.LOW
    if total <= 6:
        return RiskCategory.MODERATE
    return RiskCategory.HIGH


TREATMENT_POINTS = {
    Treatment.MIXED_INSULIN_SEVERAL_DAILY: 3.0,
    Treatment.BASAL_BOLUS_OR_PUMP: 2.5,
    Treatment.MIXED_INSULIN_ONCE_DAILY: 2.0,
    Treatment.BASAL_INSULIN: 1.5,
    Treatment.GLIBENCLAMIDE: 1.0,
    Treatment.GLICLAZIDE_GLIMEPIRIDE_REPAGLINIDE: 0.5,
    Treatment.OTHER: 0.0,
}

TREATMENT_LABELS = {
    Treatment.MIXED_INSULIN_SEVERAL_DAILY: "Mixed insulin several times a day",
    Treatment.BASAL_BOLUS_OR_PUMP: "Basal-bolus insulin or an insulin pump",
    Treatment.MIXED_INSULIN_ONCE_DAILY: "Mixed insulin once a day",
    Treatment.BASAL_INSULIN: "Basal insulin",
    Treatment.GLIBENCLAMIDE: "Glibenclamide",
    Treatment.GLICLAZIDE_GLIMEPIRIDE_REPAGLINIDE: "Gliclazide MR, glimepiride or repaglinide",
    Treatment.OTHER: "Other treatment",
}


def treatments_from_medicines(medicines: Iterable[tuple[str, int]]) -> tuple[Treatment, ...]:
    """Classify medicines for the treatment item.

    Each medicine is a pair of the catalogue name and the number of doses each day.
    """
    medicines = list(medicines)
    classes = {get_medicine(name).medicine_class for name, _ in medicines}
    has_fast_insulin = bool(classes & {MedicineClass.RAPID_INSULIN, MedicineClass.REGULAR_INSULIN})
    result: list[Treatment] = []
    for name, doses_per_day in medicines:
        medicine = get_medicine(name)
        match medicine.medicine_class:
            case MedicineClass.PREMIXED_INSULIN:
                result.append(
                    Treatment.MIXED_INSULIN_SEVERAL_DAILY
                    if doses_per_day >= 2
                    else Treatment.MIXED_INSULIN_ONCE_DAILY
                )
            case MedicineClass.BASAL_INSULIN:
                result.append(
                    Treatment.BASAL_BOLUS_OR_PUMP if has_fast_insulin else Treatment.BASAL_INSULIN
                )
            case MedicineClass.RAPID_INSULIN | MedicineClass.REGULAR_INSULIN:
                result.append(Treatment.BASAL_BOLUS_OR_PUMP)
            case MedicineClass.SULFONYLUREA if medicine.name == "glibenclamide":
                result.append(Treatment.GLIBENCLAMIDE)
            case MedicineClass.SULFONYLUREA | MedicineClass.GLINIDE:
                result.append(Treatment.GLICLAZIDE_GLIMEPIRIDE_REPAGLINIDE)
            case _ if medicine.is_diabetes_medicine:
                result.append(Treatment.OTHER)
    return tuple(result) if result else (Treatment.OTHER,)


# Each scorer returns the points and a short description, or None when information is missing.
Scorer = Callable[[IdfDarInputs], tuple[float, str] | None]


def _choice(value, table: dict, labels: dict) -> tuple[float, str] | None:
    if value is None:
        return None
    return table[value], labels[value]


def _diabetes_type(x: IdfDarInputs):
    return _choice(
        x.diabetes_type,
        {DiabetesType.TYPE_1: 1.0, DiabetesType.TYPE_2: 0.0},
        {DiabetesType.TYPE_1: "Type 1 Diabetes", DiabetesType.TYPE_2: "Type 2 Diabetes"},
    )


def _years(x: IdfDarInputs):
    if x.years_with_diabetes is None:
        return None
    years = x.years_with_diabetes
    if years >= 10:
        return 1.0, f"{years:g} years with diabetes (10 years or more)"
    return 0.0, f"{years:g} years with diabetes (fewer than 10 years)"


def _hypoglycaemia(x: IdfDarInputs):
    return _choice(
        x.hypoglycaemia,
        {
            Hypoglycaemia.UNAWARE: 6.5,
            Hypoglycaemia.RECENT_SEVERE: 5.5,
            Hypoglycaemia.SEVERAL_PER_WEEK: 3.5,
            Hypoglycaemia.LESS_THAN_WEEKLY: 1.0,
            Hypoglycaemia.NONE: 0.0,
        },
        {
            Hypoglycaemia.UNAWARE: "Unaware of low blood sugar",
            Hypoglycaemia.RECENT_SEVERE: "A recent severe episode of low blood sugar",
            Hypoglycaemia.SEVERAL_PER_WEEK: "Several episodes of low blood sugar a week",
            Hypoglycaemia.LESS_THAN_WEEKLY: "Episodes of low blood sugar less than once a week",
            Hypoglycaemia.NONE: "No episodes of low blood sugar",
        },
    )


def _hba1c(x: IdfDarInputs):
    if x.hba1c_percent is None:
        return None
    value = x.hba1c_percent
    if value > 9.0:
        return 2.0, f"HbA1c {value:g}% (above 9%)"
    if value >= 7.5:
        return 1.0, f"HbA1c {value:g}% (from 7.5% to 9%)"
    return 0.0, f"HbA1c {value:g}% (below 7.5%)"


def _treatment(x: IdfDarInputs):
    if x.treatments is None:
        return None
    treatments = x.treatments or (Treatment.OTHER,)
    top = max(treatments, key=lambda t: TREATMENT_POINTS[t])
    return TREATMENT_POINTS[top], TREATMENT_LABELS[top]


def _self_monitoring(x: IdfDarInputs):
    return _choice(
        x.self_monitoring,
        {
            SelfMonitoring.NEEDED_NOT_DONE: 2.0,
            SelfMonitoring.LESS_THAN_NEEDED: 1.0,
            SelfMonitoring.AS_NEEDED: 0.0,
        },
        {
            SelfMonitoring.NEEDED_NOT_DONE: "Self-monitoring is needed but not done",
            SelfMonitoring.LESS_THAN_NEEDED: "Self-monitoring is done less often than needed",
            SelfMonitoring.AS_NEEDED: "Self-monitoring is done as needed",
        },
    )


def _acute(x: IdfDarInputs):
    return _choice(
        x.acute_complications,
        {
            AcuteComplications.LAST_3_MONTHS: 3.0,
            AcuteComplications.LAST_6_MONTHS: 2.0,
            AcuteComplications.LAST_12_MONTHS: 1.0,
            AcuteComplications.NONE: 0.0,
        },
        {
            AcuteComplications.LAST_3_MONTHS: "DKA or HHS in the last 3 months",
            AcuteComplications.LAST_6_MONTHS: "DKA or HHS in the last 6 months",
            AcuteComplications.LAST_12_MONTHS: "DKA or HHS in the last 12 months",
            AcuteComplications.NONE: "No DKA or HHS in the last 12 months",
        },
    )


def _macrovascular(x: IdfDarInputs):
    return _choice(
        x.macrovascular,
        {Macrovascular.UNSTABLE: 6.5, Macrovascular.STABLE: 2.0, Macrovascular.NONE: 0.0},
        {
            Macrovascular.UNSTABLE: "Unstable heart or blood vessel disease",
            Macrovascular.STABLE: "Stable heart or blood vessel disease",
            Macrovascular.NONE: "No heart or blood vessel disease",
        },
    )


def _egfr(x: IdfDarInputs):
    if x.egfr is None:
        return None
    value = x.egfr
    unit = "mL/min/1.73 m²"
    if value < 30:
        return 6.5, f"eGFR {value:g} {unit} (below 30)"
    if value < 45:
        return 4.0, f"eGFR {value:g} {unit} (from 30 to 44)"
    if value < 60:
        return 2.0, f"eGFR {value:g} {unit} (from 45 to 59)"
    return 0.0, f"eGFR {value:g} {unit} (60 or above)"


def _pregnancy(x: IdfDarInputs):
    return _choice(
        x.pregnancy,
        {
            Pregnancy.NOT_WITHIN_TARGETS: 6.5,
            Pregnancy.WITHIN_TARGETS: 3.5,
            Pregnancy.NOT_PREGNANT: 0.0,
        },
        {
            Pregnancy.NOT_WITHIN_TARGETS: "Pregnant, with glucose not within targets",
            Pregnancy.WITHIN_TARGETS: "Pregnant, with glucose within targets",
            Pregnancy.NOT_PREGNANT: "Not pregnant",
        },
    )


def _frailty(x: IdfDarInputs):
    return _choice(
        x.frailty,
        {
            Frailty.IMPAIRED_COGNITION_OR_FRAILTY: 6.5,
            Frailty.OVER_70_WITHOUT_SUPPORT: 3.5,
            Frailty.NONE: 0.0,
        },
        {
            Frailty.IMPAIRED_COGNITION_OR_FRAILTY: "Impaired cognition or frailty",
            Frailty.OVER_70_WITHOUT_SUPPORT: "Older than 70 years without support at home",
            Frailty.NONE: "No frailty or impaired cognition",
        },
    )


def _labour(x: IdfDarInputs):
    return _choice(
        x.physical_labour,
        {PhysicalLabour.HIGH: 4.0, PhysicalLabour.MODERATE: 2.0, PhysicalLabour.NONE: 0.0},
        {
            PhysicalLabour.HIGH: "Physical work of high intensity",
            PhysicalLabour.MODERATE: "Physical work of moderate intensity",
            PhysicalLabour.NONE: "No intense physical work",
        },
    )


def _previous_fasting(x: IdfDarInputs):
    return _choice(
        x.previous_fasting,
        {FastingExperience.NEGATIVE: 1.0, FastingExperience.NEUTRAL_OR_POSITIVE: 0.0},
        {
            FastingExperience.NEGATIVE: "Previous fasting experience was overall negative",
            FastingExperience.NEUTRAL_OR_POSITIVE: (
                "Previous fasting experience was neutral or positive"
            ),
        },
    )


def _fasting_hours(x: IdfDarInputs):
    if x.fasting_hours is None:
        return None
    hours = x.fasting_hours
    if hours >= 16:
        return 1.0, f"{hours:.1f} fasting hours (16 hours or more)"
    return 0.0, f"{hours:.1f} fasting hours (fewer than 16 hours)"


# The items in the order of the guideline table: key, label, maximum points, scorer.
ITEMS: tuple[tuple[str, str, float, Scorer], ...] = (
    ("diabetes_type", "Type of diabetes", 1.0, _diabetes_type),
    ("years_with_diabetes", "Years with diabetes", 1.0, _years),
    ("hypoglycaemia", "Low blood sugar", 6.5, _hypoglycaemia),
    ("hba1c_percent", "HbA1c", 2.0, _hba1c),
    ("treatments", "Treatment", 3.0, _treatment),
    ("self_monitoring", "Self-monitoring of blood glucose", 2.0, _self_monitoring),
    ("acute_complications", "Acute complications (DKA or HHS)", 3.0, _acute),
    ("macrovascular", "Heart and blood vessel disease", 6.5, _macrovascular),
    ("egfr", "Kidney function (eGFR)", 6.5, _egfr),
    ("pregnancy", "Pregnancy", 6.5, _pregnancy),
    ("frailty", "Frailty and cognition", 6.5, _frailty),
    ("physical_labour", "Physical work", 4.0, _labour),
    ("previous_fasting", "Previous fasting experience", 1.0, _previous_fasting),
    ("fasting_hours", "Fasting hours", 1.0, _fasting_hours),
)

assert {key for key, *_ in ITEMS} == {f.name for f in fields(IdfDarInputs)}


def calculate(inputs: IdfDarInputs) -> IdfDarResult:
    """Calculate the IDF-DAR 2021 risk score, with the points for each item."""
    items: list[ItemScore] = []
    for key, label, max_points, scorer in ITEMS:
        scored = scorer(inputs)
        if scored is None:
            items.append(ItemScore(key, label, None, max_points, MISSING))
        else:
            points, detail = scored
            items.append(ItemScore(key, label, points, max_points, detail))
    total = sum(item.points for item in items if item.points is not None)
    max_total = total + sum(item.max_points for item in items if item.points is None)
    return IdfDarResult(
        items=tuple(items),
        total=total,
        category=category_for(total),
        min_total=total,
        max_total=max_total,
        min_category=category_for(total),
        max_category=category_for(max_total),
    )

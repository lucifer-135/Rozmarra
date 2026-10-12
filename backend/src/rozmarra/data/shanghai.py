"""The loader for the ShanghaiT2DM dataset (Scientific Data, 2023).

Each Excel file holds one recording period of one patient, with CGM readings every
15 minutes, fingerstick glucose, meals as text, and insulin and other medicines as
text. The summary file holds demographics and laboratory results.

The loader maps the medicine names to the Rozmarra catalogue and checks every dose
against a plausible maximum. Some records give a dose in grams where milligrams are
meant, for example "empagliflozin 10 g". The loader reads such a dose as milligrams
and records the correction in the event details.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from rozmarra.data.foods import estimate_meal
from rozmarra.data.harmonise import (
    EVENT_COLUMNS,
    REAL_OPEN,
    TIMESERIES_COLUMNS,
    concat,
    event,
    events_frame,
    long_signal,
)
from rozmarra.medicines import get_medicine

DATASET = "ShanghaiT2DM"
TIMEZONE = "Asia/Shanghai"
CGM_DEVICE = "FreeStyle Libre H"
FINGERSTICK_DEVICE = "Glucose meter"

# HbA1c in mmol/mol is converted to % with the IFCC to NGSP master equation.
HBA1C_MMOL_PER_PERCENT = 10.929
HBA1C_OFFSET = 2.15
# Insulin in pmol/L is converted to µU/mL with the factor 6.0 (an assumption; some
# laboratories use 6.945).
INSULIN_PMOL_PER_UU = 6.0
CREATININE_UMOL_PER_MG_DL = 88.4

# Insulin names in the dataset, in the order in which they are matched.
INSULIN_NAMES: tuple[tuple[str, str], ...] = (
    ("insulin aspart 70/30", "biphasic_insulin_aspart_30"),
    ("insulin aspart 50/50", "biphasic_insulin_aspart_50"),
    ("insulin aspart", "insulin_aspart"),
    ("insulin glulisine", "insulin_glulisine"),
    ("insulin degludec", "insulin_degludec"),
    ("insulin detemir", "insulin_detemir"),
    ("insulin glargine", "insulin_glargine"),
    ("insulin glarigine", "insulin_glargine"),  # A spelling in the dataset.
    ("novolin 30r", "premixed_insulin_30_70"),
    ("humulin 70/30", "premixed_insulin_30_70"),
    ("scilin m30", "premixed_insulin_30_70"),
    ("gansulin 40r", "premixed_insulin_40_60"),
    ("novolin r", "regular_insulin"),
    ("humulin r", "regular_insulin"),
    ("gansulin r", "regular_insulin"),
)
ORAL_NAMES: tuple[tuple[str, str], ...] = (
    ("metformin", "metformin"),
    ("acarbose", "acarbose"),
    ("voglibose", "voglibose"),
    ("sitagliptin", "sitagliptin"),
    ("linagliptin", "linagliptin"),
    ("gliclazide", "gliclazide"),
    ("glimepiride", "glimepiride"),
    ("gliquidone", "gliquidone"),
    ("repaglinide", "repaglinide"),
    ("pioglitazone", "pioglitazone"),
    ("dapagliflozin", "dapagliflozin"),
    ("empagliflozin", "empagliflozin"),
    ("canagliflozin", "canagliflozin"),
    ("liraglutide", "liraglutide"),
)
BETA_BLOCKERS = (
    "bisoprolol",
    "metoprolol",
    "propranolol",
    "atenolol",
    "carvedilol",
    "arotinolol",
    "nebivolol",
)

_INSULIN_ITEM = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9 /\-]*?)[,\s]+(?P<units>\d+(?:\.\d+)?)\s*IU"
)
_IV_ITEM = re.compile(r"(?P<units>\d+(?:\.\d+)?)\s*IU\s+(?P<name>Novolin R|Humulin R|Gansulin R)")
_ORAL_ITEM = re.compile(r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>mg|g)\b")


@dataclass(frozen=True)
class Dose:
    name: str
    amount: float
    unit: str
    original: str
    note: str = ""


def _lookup(text: str, table: tuple[tuple[str, str], ...]) -> str | None:
    lowered = text.lower()
    return next((name for key, name in table if key in lowered), None)


def parse_insulin(text: str) -> list[Dose]:
    """Read subcutaneous insulin doses, for example "insulin glargine, 10 IU"."""
    doses = []
    for match in _INSULIN_ITEM.finditer(str(text)):
        name = _lookup(match["name"], INSULIN_NAMES)
        if name:
            doses.append(Dose(name, float(match["units"]), "units", match.group(0).strip(" ,")))
    return doses


def parse_iv_insulin(text: str) -> list[Dose]:
    """Read insulin added to an intravenous infusion, for example "8 IU Novolin R"."""
    return [
        Dose("regular_insulin", float(m["units"]), "units", m.group(0))
        for m in _IV_ITEM.finditer(str(text))
    ]


def _gliclazide_form(dose_mg: float) -> str:
    # Gliclazide MR comes in multiples of 30 mg. The ordinary tablets come in 40 mg or 80 mg.
    return "gliclazide_mr" if dose_mg % 30 == 0 else "gliclazide"


def _plausible(name: str, dose_mg: float) -> bool:
    """A dose is plausible from a tenth of the standard dose to three times the largest dose."""
    medicine = get_medicine(name)
    return 0.1 * medicine.standard_dose <= dose_mg <= 3 * medicine.max_single_dose


def parse_oral(text: str) -> list[Dose]:
    """Read oral medicines, for example "metformin 0.5 g, acarbose 50 mg"."""
    text = str(text)
    if "sitagliptinphosphate/metforminhydrochloride" in text.replace(" ", "").lower():
        amounts = [float(a) for a in re.findall(r"(\d+(?:\.\d+)?)\s*mg", text)]
        if len(amounts) == 2:
            return [
                Dose("sitagliptin", amounts[0], "mg", text),
                Dose("metformin", amounts[1], "mg", text),
            ]
    doses = []
    for part in text.split(","):
        name = _lookup(part, ORAL_NAMES)
        match = _ORAL_ITEM.search(part)
        if not name or not match:
            continue
        amount = float(match["amount"])
        dose_mg = amount * 1000 if match["unit"] == "g" else amount
        note = ""
        catalogue_name = _gliclazide_form(dose_mg) if name == "gliclazide" else name
        if match["unit"] == "g" and not _plausible(catalogue_name, dose_mg):
            as_mg = _gliclazide_form(amount) if name == "gliclazide" else name
            if _plausible(as_mg, amount):
                dose_mg, catalogue_name = amount, as_mg
                note = "The record gives the dose in grams. Rozmarra reads it as milligrams."
        if not note and not _plausible(catalogue_name, dose_mg):
            note = "The recorded dose is outside the expected range."
        doses.append(Dose(catalogue_name, dose_mg, "mg", part.strip(), note))
    return doses


def _column(frame: pd.DataFrame, *prefixes: str) -> str | None:
    for column in frame.columns:
        if any(str(column).strip().startswith(prefix) for prefix in prefixes):
            return column
    return None


def patient_id_for(stem: str) -> str:
    """Turn a file name such as "2010_0_20220111" into the identifier "SH-2010-0"."""
    number, period, _ = stem.split("_")
    return f"SH-{number}-{period}"


def load_period(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Load one recording period. Return the time series, the events and some flags."""
    frame = pd.read_excel(path)
    patient_id = patient_id_for(path.stem)
    times = pd.to_datetime(frame["Date"], errors="coerce")
    common = {"dataset": DATASET, "timezone": TIMEZONE}

    signals = []
    for prefix, signal, unit, device in (
        ("CGM", "glucose_cgm", "mg/dL", CGM_DEVICE),
        ("CBG", "glucose_fingerstick", "mg/dL", FINGERSTICK_DEVICE),
        ("Blood Ketone", "blood_ketone", "mmol/L", FINGERSTICK_DEVICE),
    ):
        column = _column(frame, prefix)
        if column is not None:
            signals.append(
                long_signal(
                    patient_id,
                    times,
                    frame[column],
                    signal=signal,
                    unit=unit,
                    device=device,
                    **common,
                )
            )

    rows = []
    meal_column = _column(frame, "Dietary intake")
    if meal_column is not None:
        for when, text in zip(times, frame[meal_column], strict=True):
            if pd.isna(when) or pd.isna(text) or not str(text).strip():
                continue
            estimate = estimate_meal(text)
            rows.append(
                event(
                    patient_id,
                    when,
                    "meal",
                    {
                        "text": str(text).strip(),
                        "carbs_g": estimate.carbs_g,
                        "carbs_source": estimate.source,
                        "food_items": estimate.items,
                        "unknown_food_items": estimate.unknown_items,
                    },
                )
            )

    def add_doses(column_prefixes, parser, event_type, route):
        column = _column(frame, *column_prefixes)
        if column is None:
            return 0
        count = 0
        for when, text in zip(times, frame[column], strict=True):
            if pd.isna(when) or pd.isna(text):
                continue
            for dose in parser(text):
                details = {
                    "name": dose.name,
                    "dose": dose.amount,
                    "unit": dose.unit,
                    "route": route,
                    "original": dose.original,
                }
                if dose.note:
                    details["note"] = dose.note
                rows.append(event(patient_id, when, event_type, details))
                count += 1
        return count

    add_doses(("Insulin dose - s.c",), parse_insulin, "insulin", "subcutaneous")
    iv_count = add_doses(("Insulin dose - i.v",), parse_iv_insulin, "insulin", "intravenous")
    add_doses(("Non-insulin",), parse_oral, "medicine", "oral")

    pump_doses = 0
    bolus = _column(frame, "CSII - bolus")
    basal = _column(frame, "CSII - basal", "胰岛素泵基础量")
    for column, event_type, unit in (
        (bolus, "insulin", "units"),
        (basal, "insulin_pump_basal_rate", "units per hour"),
    ):
        if column is None:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        for when, value in zip(times, values, strict=True):
            if pd.isna(when) or pd.isna(value):
                continue
            details = {
                "name": "regular_insulin",
                "dose": float(value),
                "unit": unit,
                "route": "insulin_pump",
            }
            rows.append(event(patient_id, when, event_type, details))
            pump_doses += 1

    flags = {
        "uses_insulin_pump": pump_doses > 0,
        "has_intravenous_insulin": iv_count > 0,
    }
    timeseries = concat(signals, TIMESERIES_COLUMNS)
    return timeseries, events_frame(rows), flags


def load_summary(path: Path) -> pd.DataFrame:
    summary = pd.read_excel(path)
    summary.columns = [" ".join(str(c).split()) for c in summary.columns]

    def column(prefix: str) -> pd.Series:
        name = next(c for c in summary.columns if c.startswith(prefix))
        return summary[name]

    def numeric(prefix: str) -> pd.Series:
        return pd.to_numeric(column(prefix), errors="coerce")

    other_agents = column("Other Agents").astype(str).str.lower()
    macro = column("Diabetic Macrovascular").astype(str).str.lower()
    return pd.DataFrame(
        {
            "patient_id": [patient_id_for(str(s).strip()) for s in column("Patient Number")],
            "dataset": DATASET,
            "source": REAL_OPEN,
            "timezone": TIMEZONE,
            "sex": numeric("Gender").map({1: "female", 2: "male"}),
            "age": numeric("Age"),
            "height_cm": numeric("Height") * 100,
            "weight_kg": numeric("Weight"),
            "bmi": numeric("BMI").round(1),
            "diabetes_status": "type_2_diabetes",
            "years_with_diabetes": numeric("Duration of diabetes").round(1),
            "hba1c_percent": (numeric("HbA1c") / HBA1C_MMOL_PER_PERCENT + HBA1C_OFFSET).round(1),
            "fasting_glucose_mg_dl": numeric("Fasting Plasma Glucose").round(1),
            "fasting_insulin_uu_ml": (numeric("Fasting Insulin") / INSULIN_PMOL_PER_UU).round(1),
            "creatinine_mg_dl": (numeric("Creatinine") / CREATININE_UMOL_PER_MG_DL).round(2),
            "egfr": numeric("Estimated Glomerular Filtration Rate"),
            "medicines_text": column("Hypoglycemic Agents").astype(str).str.strip(),
            "takes_beta_blocker": other_agents.apply(lambda s: any(b in s for b in BETA_BLOCKERS)),
            "heart_disease": macro.str.contains("coronary"),
            "hypoglycaemia_history": column("Hypoglycemia").astype(str).str.strip().str.lower()
            == "yes",
        }
    )


def load(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load every recording period. Return the time series, the events and the patients."""
    root = raw_dir / "shanghai_t2dm"
    patients = load_summary(root / "Shanghai_T2DM_Summary.xlsx")
    series, events, flags = [], [], {}
    for path in sorted((root / "Shanghai_T2DM").glob("*.xls*")):
        timeseries, period_events, period_flags = load_period(path)
        series.append(timeseries)
        events.append(period_events)
        flags[patient_id_for(path.stem)] = period_flags
    flag_frame = (
        pd.DataFrame.from_dict(flags, orient="index").rename_axis("patient_id").reset_index()
    )
    patients = patients.merge(flag_frame, on="patient_id", how="left")
    return concat(series, TIMESERIES_COLUMNS), concat(events, EVENT_COLUMNS), patients

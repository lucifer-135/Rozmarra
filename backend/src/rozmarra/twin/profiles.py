"""Twin profiles for synthetic patients and the average patient.

A synthetic patient's fixed values come from the health record: fasting glucose, fasting
insulin, body weight, eGFR, the CYP2C9 clearance factor and the counter-regulation factor.
The fitted parameters start from the population values. The virtual patients will later
receive parameters sampled from the twins fitted on real patients.

The average patient uses the median parameters of the fitted twins, with the patient's own
fixed values, plan and medicines (docs/techstack.md, Section 5.8).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np

from rozmarra.config import MODELS_DIR
from rozmarra.ehr.records import PatientRecord
from rozmarra.risk.idf_dar import Hypoglycaemia
from rozmarra.twin.model import CR_REDUCED, FITTED_NAMES
from rozmarra.twin.simulate import TwinProfile

TWINS_FILE = MODELS_DIR / "twins.json"


def counter_regulation_factor(record: PatientRecord, day: date) -> float:
    """Counter-regulation is weaker with unawareness of low blood sugar.

    It is also weaker after more than 15 years of diabetes.
    """
    unaware = record.hypoglycaemia is Hypoglycaemia.UNAWARE
    return CR_REDUCED if unaware or record.years_with_diabetes_on(day) > 15 else 1.0


def profile_for_record(record: PatientRecord, day: date) -> TwinProfile:
    return TwinProfile.population(
        G_b=record.fasting_glucose_mg_dl,
        I_b=record.fasting_insulin_uu_ml,
        body_weight=record.weight_kg,
        egfr=record.egfr,
        cr_factor=counter_regulation_factor(record, day),
        cyp_factor=record.cyp2c9_clearance_factor,
    )


def load_twins(path: Path = TWINS_FILE) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["twins"]


def average_parameters(twins: list[dict]) -> dict[str, float]:
    """The median of each fitted parameter across the given twins."""
    values = {}
    for name in FITTED_NAMES:
        fitted = [t["fitted"][name] for t in twins if name in t["fitted"]]
        if fitted:
            values[name] = float(np.median(fitted))
    return values


def average_profile(profile: TwinProfile, twins: list[dict]) -> TwinProfile | None:
    if not twins:
        return None
    return profile.with_parameters(average_parameters(twins), source="average patient")

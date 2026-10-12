"""Simple safety rules that Rozmarra checks when the doctor tests a plan.

These rules are cautions, not predictions. A clinical expert should review them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rozmarra.medicines import MedicineClass, get_medicine

# The dehydration caution (C1) in docs/prd.md, Section 10.
C1_MIN_HOURS = 12
C1_EGFR_LIMIT = 60
C1_AGE_LIMIT = 65


@dataclass(frozen=True)
class Caution:
    code: str
    title: str
    message: str
    reasons: tuple[str, ...]


def dehydration_caution(
    water_allowed: bool,
    fast_hours: float,
    medicines: Iterable[str],
    egfr: float | None,
    age: float | None,
) -> Caution | None:
    """Return the dehydration caution when its rule applies, or None.

    The rule applies when a fast without water lasts 12 hours or more and at least one
    of these is true: the patient takes an SGLT2 inhibitor or a diuretic, the eGFR is
    below 60, or the patient is older than 65 years.
    """
    if water_allowed or fast_hours < C1_MIN_HOURS:
        return None
    reasons: list[str] = []
    for name in sorted(set(medicines)):
        medicine = get_medicine(name)
        if medicine.medicine_class is MedicineClass.SGLT2_INHIBITOR:
            reasons.append(
                f"The patient takes {medicine.display_name.lower()}, an SGLT2 inhibitor."
            )
        elif medicine.medicine_class is MedicineClass.DIURETIC:
            reasons.append(f"The patient takes {medicine.display_name.lower()}, a diuretic.")
    if egfr is not None and egfr < C1_EGFR_LIMIT:
        reasons.append(f"The eGFR is {egfr:g} mL/min/1.73 m², which is below 60.")
    if age is not None and age > C1_AGE_LIMIT:
        reasons.append(f"The patient is {age:g} years old, which is older than 65 years.")
    if not reasons:
        return None
    return Caution(
        code="C1",
        title="Dehydration caution",
        message=(
            f"This fast allows no water for {fast_hours:.1f} hours. The risk of dehydration "
            "may be higher for this patient. Please review the medicines and the plan for "
            "drinking water before and after the fast."
        ),
        reasons=tuple(reasons),
    )

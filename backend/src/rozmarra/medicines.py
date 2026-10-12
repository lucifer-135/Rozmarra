"""The catalogue of medicines that Rozmarra knows about.

The health record generator, the dataset loaders, the IDF-DAR calculator, the
physiology twin and the patient plans all read medicine facts from this one
catalogue.

The activity curve settings (time to peak, half-life and maximum duration) come
from docs/techstack.md, Section 5.3, where that section lists the medicine. The
other values are starting values from product information. The team will check
all of them against pharmacology references. The Hindi names are
transliterations for the patient plan, and a native Hindi speaker will review them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MedicineClass(StrEnum):
    SULFONYLUREA = "sulfonylurea"
    GLINIDE = "glinide"
    BIGUANIDE = "biguanide"
    DPP4_INHIBITOR = "dpp4_inhibitor"
    SGLT2_INHIBITOR = "sglt2_inhibitor"
    ALPHA_GLUCOSIDASE_INHIBITOR = "alpha_glucosidase_inhibitor"
    THIAZOLIDINEDIONE = "thiazolidinedione"
    GLP1_AGONIST = "glp1_agonist"
    BASAL_INSULIN = "basal_insulin"
    PREMIXED_INSULIN = "premixed_insulin"
    RAPID_INSULIN = "rapid_insulin"
    REGULAR_INSULIN = "regular_insulin"
    DIURETIC = "diuretic"
    BETA_BLOCKER = "beta_blocker"
    OTHER = "other"


INSULIN_CLASSES = frozenset(
    {
        MedicineClass.BASAL_INSULIN,
        MedicineClass.PREMIXED_INSULIN,
        MedicineClass.RAPID_INSULIN,
        MedicineClass.REGULAR_INSULIN,
    }
)
NON_DIABETES_CLASSES = frozenset(
    {MedicineClass.DIURETIC, MedicineClass.BETA_BLOCKER, MedicineClass.OTHER}
)


class InsulinAction(StrEnum):
    """The action profiles that the twin uses for injected insulin (techstack, Section 5.3)."""

    RAPID = "rapid"
    REGULAR = "regular"
    NPH = "nph"
    BASAL = "basal"


@dataclass(frozen=True)
class ActivityCurve:
    """The settings of the activity curve for a medicine taken by mouth, in minutes."""

    t_peak_min: float
    half_life_min: float
    t_max_min: float


@dataclass(frozen=True)
class Medicine:
    name: str
    display_name: str
    display_name_hi: str
    medicine_class: MedicineClass
    atc_code: str | None
    unit: str
    standard_dose: float
    # The largest plausible single dose. The loaders use it to detect unit errors.
    max_single_dose: float
    curve: ActivityCurve | None = None
    # For insulin: the share of each dose that follows each action profile.
    insulin_parts: tuple[tuple[InsulinAction, float], ...] = ()

    @property
    def is_insulin(self) -> bool:
        return self.medicine_class in INSULIN_CLASSES

    @property
    def is_diabetes_medicine(self) -> bool:
        return self.medicine_class not in NON_DIABETES_CLASSES


def _hours(t_peak: float, half_life: float, t_max: float) -> ActivityCurve:
    return ActivityCurve(t_peak * 60, half_life * 60, t_max * 60)


_RAPID = ((InsulinAction.RAPID, 1.0),)
_REGULAR = ((InsulinAction.REGULAR, 1.0),)
_BASAL = ((InsulinAction.BASAL, 1.0),)
SU = MedicineClass.SULFONYLUREA
DPP4 = MedicineClass.DPP4_INHIBITOR
SGLT2 = MedicineClass.SGLT2_INHIBITOR

_CATALOGUE = [
    # Sulfonylureas and glinides
    Medicine(
        "glimepiride", "Glimepiride", "ग्लिमेपिराइड", SU, "A10BB12", "mg", 2, 8, _hours(3, 8, 24)
    ),
    Medicine(
        "gliclazide_mr",
        "Gliclazide MR",
        "ग्लिक्लाज़ाइड एमआर",
        SU,
        "A10BB09",
        "mg",
        60,
        120,
        _hours(6, 16, 36),
    ),
    Medicine(
        "gliclazide", "Gliclazide", "ग्लिक्लाज़ाइड", SU, "A10BB09", "mg", 80, 160, _hours(3, 12, 24)
    ),
    Medicine(
        "glibenclamide",
        "Glibenclamide",
        "ग्लिबेनक्लामाइड",
        SU,
        "A10BB01",
        "mg",
        5,
        10,
        _hours(3, 10, 30),
    ),
    Medicine(
        "gliquidone", "Gliquidone", "ग्लिक्विडोन", SU, "A10BB08", "mg", 30, 60, _hours(2, 1.5, 10)
    ),
    Medicine(
        "repaglinide",
        "Repaglinide",
        "रेपाग्लिनाइड",
        MedicineClass.GLINIDE,
        "A10BX02",
        "mg",
        1,
        4,
        _hours(1, 1, 6),
    ),
    # Metformin
    Medicine(
        "metformin",
        "Metformin",
        "मेटफ़ॉर्मिन",
        MedicineClass.BIGUANIDE,
        "A10BA02",
        "mg",
        1000,
        1000,
        _hours(3, 6, 24),
    ),
    # DPP-4 inhibitors. Vildagliptin, teneligliptin and linagliptin reuse the sitagliptin curve.
    Medicine(
        "sitagliptin",
        "Sitagliptin",
        "सिटाग्लिप्टिन",
        DPP4,
        "A10BH01",
        "mg",
        100,
        100,
        _hours(2, 12, 24),
    ),
    Medicine(
        "vildagliptin",
        "Vildagliptin",
        "विल्डाग्लिप्टिन",
        DPP4,
        "A10BH02",
        "mg",
        50,
        50,
        _hours(2, 12, 24),
    ),
    Medicine(
        "teneligliptin",
        "Teneligliptin",
        "टेनेलिग्लिप्टिन",
        DPP4,
        "A10BH08",
        "mg",
        20,
        40,
        _hours(2, 12, 24),
    ),
    Medicine(
        "linagliptin", "Linagliptin", "लिनाग्लिप्टिन", DPP4, "A10BH05", "mg", 5, 5, _hours(2, 12, 24)
    ),
    # SGLT2 inhibitors. Canagliflozin reuses the dapagliflozin curve.
    Medicine(
        "dapagliflozin",
        "Dapagliflozin",
        "डैपाग्लिफ़्लोज़िन",
        SGLT2,
        "A10BK01",
        "mg",
        10,
        10,
        _hours(1.5, 13, 24),
    ),
    Medicine(
        "empagliflozin",
        "Empagliflozin",
        "एम्पाग्लिफ़्लोज़िन",
        SGLT2,
        "A10BK03",
        "mg",
        10,
        25,
        _hours(1.5, 13, 24),
    ),
    Medicine(
        "canagliflozin",
        "Canagliflozin",
        "कैनाग्लिफ़्लोज़िन",
        SGLT2,
        "A10BK02",
        "mg",
        100,
        300,
        _hours(1.5, 13, 24),
    ),
    # Medicines that the twin does not model in this phase. Acarbose and voglibose
    # act in the gut, pioglitazone acts over weeks, and liraglutide is an injection.
    Medicine(
        "acarbose",
        "Acarbose",
        "एकार्बोज़",
        MedicineClass.ALPHA_GLUCOSIDASE_INHIBITOR,
        "A10BF01",
        "mg",
        50,
        100,
    ),
    Medicine(
        "voglibose",
        "Voglibose",
        "वोग्लिबोज़",
        MedicineClass.ALPHA_GLUCOSIDASE_INHIBITOR,
        "A10BF03",
        "mg",
        0.2,
        0.3,
    ),
    Medicine(
        "pioglitazone",
        "Pioglitazone",
        "पियोग्लिटाज़ोन",
        MedicineClass.THIAZOLIDINEDIONE,
        "A10BG03",
        "mg",
        15,
        45,
    ),
    Medicine(
        "liraglutide",
        "Liraglutide",
        "लिराग्लूटाइड",
        MedicineClass.GLP1_AGONIST,
        "A10BJ02",
        "mg",
        1.2,
        1.8,
    ),
    # Insulin. The premixed insulins split each dose into a fast part and an NPH-like part.
    Medicine(
        "insulin_glargine",
        "Insulin glargine",
        "इंसुलिन ग्लार्जिन",
        MedicineClass.BASAL_INSULIN,
        "A10AE04",
        "units",
        10,
        80,
        insulin_parts=_BASAL,
    ),
    Medicine(
        "insulin_degludec",
        "Insulin degludec",
        "इंसुलिन डेग्लुडेक",
        MedicineClass.BASAL_INSULIN,
        "A10AE06",
        "units",
        10,
        80,
        insulin_parts=_BASAL,
    ),
    Medicine(
        "insulin_detemir",
        "Insulin detemir",
        "इंसुलिन डिटेमिर",
        MedicineClass.BASAL_INSULIN,
        "A10AE05",
        "units",
        10,
        80,
        insulin_parts=_BASAL,
    ),
    Medicine(
        "premixed_insulin_30_70",
        "Premixed human insulin 30/70",
        "प्रीमिक्स इंसुलिन 30/70",
        MedicineClass.PREMIXED_INSULIN,
        "A10AD01",
        "units",
        10,
        60,
        insulin_parts=((InsulinAction.REGULAR, 0.3), (InsulinAction.NPH, 0.7)),
    ),
    Medicine(
        "premixed_insulin_40_60",
        "Premixed human insulin 40/60",
        "प्रीमिक्स इंसुलिन 40/60",
        MedicineClass.PREMIXED_INSULIN,
        "A10AD01",
        "units",
        10,
        60,
        insulin_parts=((InsulinAction.REGULAR, 0.4), (InsulinAction.NPH, 0.6)),
    ),
    Medicine(
        "biphasic_insulin_aspart_30",
        "Biphasic insulin aspart 30",
        "बाइफ़ेज़िक इंसुलिन एस्पार्ट 30",
        MedicineClass.PREMIXED_INSULIN,
        "A10AD05",
        "units",
        10,
        60,
        insulin_parts=((InsulinAction.RAPID, 0.3), (InsulinAction.NPH, 0.7)),
    ),
    Medicine(
        "biphasic_insulin_aspart_50",
        "Biphasic insulin aspart 50",
        "बाइफ़ेज़िक इंसुलिन एस्पार्ट 50",
        MedicineClass.PREMIXED_INSULIN,
        "A10AD05",
        "units",
        10,
        60,
        insulin_parts=((InsulinAction.RAPID, 0.5), (InsulinAction.NPH, 0.5)),
    ),
    Medicine(
        "insulin_aspart",
        "Insulin aspart",
        "इंसुलिन एस्पार्ट",
        MedicineClass.RAPID_INSULIN,
        "A10AB05",
        "units",
        4,
        40,
        insulin_parts=_RAPID,
    ),
    Medicine(
        "insulin_glulisine",
        "Insulin glulisine",
        "इंसुलिन ग्लूलिसिन",
        MedicineClass.RAPID_INSULIN,
        "A10AB06",
        "units",
        4,
        40,
        insulin_parts=_RAPID,
    ),
    Medicine(
        "regular_insulin",
        "Regular human insulin",
        "रेगुलर इंसुलिन",
        MedicineClass.REGULAR_INSULIN,
        "A10AB01",
        "units",
        4,
        40,
        insulin_parts=_REGULAR,
    ),
    # Medicines that matter for the safety rules and the heart rate model
    Medicine(
        "hydrochlorothiazide",
        "Hydrochlorothiazide",
        "हाइड्रोक्लोरोथियाज़ाइड",
        MedicineClass.DIURETIC,
        "C03AA03",
        "mg",
        12.5,
        50,
    ),
    Medicine(
        "metoprolol",
        "Metoprolol",
        "मेटोप्रोलोल",
        MedicineClass.BETA_BLOCKER,
        "C07AB02",
        "mg",
        50,
        200,
    ),
    Medicine(
        "bisoprolol", "Bisoprolol", "बिसोप्रोलोल", MedicineClass.BETA_BLOCKER, "C07AB07", "mg", 5, 10
    ),
    Medicine(
        "telmisartan", "Telmisartan", "टेल्मिसार्टन", MedicineClass.OTHER, "C09CA07", "mg", 40, 80
    ),
    Medicine(
        "atorvastatin", "Atorvastatin", "एटोरवास्टेटिन", MedicineClass.OTHER, "C10AA05", "mg", 10, 80
    ),
    Medicine("aspirin", "Aspirin", "एस्पिरिन", MedicineClass.OTHER, "B01AC06", "mg", 75, 325),
]

MEDICINES: dict[str, Medicine] = {medicine.name: medicine for medicine in _CATALOGUE}


def get_medicine(name: str) -> Medicine:
    try:
        return MEDICINES[name]
    except KeyError:
        known = ", ".join(sorted(MEDICINES))
        raise KeyError(f"The medicine '{name}' is not in the catalogue. Known: {known}.") from None

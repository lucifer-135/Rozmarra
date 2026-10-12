"""The four synthetic demo patients in docs/prd.md, Section 6.3.

All demo patients are synthetic. The team created them for the demonstration, and
they do not represent real people. Their records follow the summaries in the
requirements, and the details that the requirements leave open are team choices
that give the IDF-DAR totals in docs/techstack.md, Section 9.

The risks that each demo is designed to illustrate are described in the
requirements. The actual numbers will come from the model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from rozmarra.ehr.records import MedicineStatement, PatientRecord, ScheduledDose
from rozmarra.risk.idf_dar import (
    FastingExperience,
    Hypoglycaemia,
    Macrovascular,
    PhysicalLabour,
    SelfMonitoring,
)


def _medicine(name: str, *doses: tuple[int, int, float]) -> MedicineStatement:
    return MedicineStatement(
        name=name,
        schedule=[
            ScheduledDose(time=time(hour, minute), dose=dose) for hour, minute, dose in doses
        ],
    )


@dataclass(frozen=True)
class DemoFast:
    """The fast that a demo patient plans to keep."""

    template_id: str
    date: date
    note: str = ""


SUNITA = PatientRecord(
    patient_id="SY-0001",
    given_name="Sunita",
    family_name="Sharma",
    sex="female",
    birth_date=date(1972, 3, 14),
    city="Delhi",
    language="hi",
    fast_word="व्रत",
    fasts_kept=["karva_chauth", "navratri_phalahar"],
    occupation="Homemaker",
    diagnosis_date=date(2018, 9, 10),
    hba1c_percent=8.4,
    fasting_glucose_mg_dl=158,
    fasting_insulin_uu_ml=12,
    creatinine_mg_dl=0.8,
    egfr=86,
    weight_kg=68,
    height_cm=156,
    systolic_bp=132,
    diastolic_bp=84,
    resting_heart_rate=76,
    medicines=[
        _medicine("glimepiride", (8, 0, 2)),
        _medicine("metformin", (8, 0, 500), (20, 30, 500)),
        _medicine("dapagliflozin", (8, 0, 10)),
    ],
    cyp2c9="*1/*3",
    hypoglycaemia=Hypoglycaemia.NONE,
    self_monitoring=SelfMonitoring.LESS_THAN_NEEDED,
)

RAMESH = PatientRecord(
    patient_id="SY-0002",
    given_name="Ramesh",
    family_name="Patel",
    sex="male",
    birth_date=date(1964, 6, 2),
    city="Ahmedabad",
    language="hi",
    fast_word="उपवास",
    fasts_kept=["navratri_one_meal"],
    occupation="Retired textile trader",
    diagnosis_date=date(2011, 5, 20),
    hba1c_percent=7.9,
    fasting_glucose_mg_dl=142,
    fasting_insulin_uu_ml=9,
    creatinine_mg_dl=1.45,
    egfr=52,
    weight_kg=74,
    height_cm=168,
    systolic_bp=138,
    diastolic_bp=82,
    resting_heart_rate=72,
    hypertension=True,
    chronic_kidney_disease=True,
    heart_disease=Macrovascular.STABLE,
    medicines=[
        _medicine("premixed_insulin_30_70", (8, 0, 18), (20, 0, 12)),
        _medicine("gliclazide_mr", (8, 0, 60)),
        _medicine("telmisartan", (8, 0, 40)),
        _medicine("atorvastatin", (21, 0, 20)),
        _medicine("aspirin", (13, 0, 75)),
    ],
    cyp2c9="*1/*1",
    hypoglycaemia=Hypoglycaemia.LESS_THAN_WEEKLY,
    self_monitoring=SelfMonitoring.AS_NEEDED,
)

ABDUL = PatientRecord(
    patient_id="SY-0003",
    given_name="Abdul",
    family_name="Rahman",
    sex="male",
    birth_date=date(1968, 8, 21),
    city="Hyderabad",
    language="en",
    fast_word="रोज़ा",
    fasts_kept=["ramadan"],
    occupation="Shopkeeper who stands for most of the day",
    diagnosis_date=date(2016, 6, 15),
    hba1c_percent=7.6,
    fasting_glucose_mg_dl=138,
    fasting_insulin_uu_ml=10,
    creatinine_mg_dl=1.0,
    egfr=82,
    weight_kg=76,
    height_cm=170,
    systolic_bp=128,
    diastolic_bp=80,
    resting_heart_rate=74,
    medicines=[
        _medicine("insulin_glargine", (22, 0, 18)),
        _medicine("metformin", (8, 0, 1000), (20, 0, 1000)),
    ],
    cyp2c9="*1/*1",
    hypoglycaemia=Hypoglycaemia.LESS_THAN_WEEKLY,
    self_monitoring=SelfMonitoring.LESS_THAN_NEEDED,
    physical_labour=PhysicalLabour.MODERATE,
    previous_fasting=FastingExperience.NEGATIVE,
)

KAMLA = PatientRecord(
    patient_id="SY-0004",
    given_name="Kamla",
    family_name="Devi",
    sex="female",
    birth_date=date(1955, 1, 10),
    city="Varanasi",
    language="hi",
    fast_word="व्रत",
    fasts_kept=["ekadashi_phalahar"],
    occupation="Retired schoolteacher",
    diagnosis_date=date(2006, 4, 5),
    hba1c_percent=7.2,
    fasting_glucose_mg_dl=130,
    fasting_insulin_uu_ml=8,
    creatinine_mg_dl=1.15,
    egfr=48,
    weight_kg=58,
    height_cm=152,
    systolic_bp=142,
    diastolic_bp=78,
    resting_heart_rate=70,
    hypertension=True,
    chronic_kidney_disease=True,
    medicines=[
        _medicine("glibenclamide", (8, 0, 5)),
        _medicine("telmisartan", (8, 0, 40)),
    ],
    cyp2c9="*1/*2",
    hypoglycaemia=Hypoglycaemia.NONE,
    self_monitoring=SelfMonitoring.AS_NEEDED,
    support_at_home=False,
)

DEMO_PATIENTS: tuple[PatientRecord, ...] = (SUNITA, RAMESH, ABDUL, KAMLA)

DEMO_FASTS: dict[str, DemoFast] = {
    "SY-0001": DemoFast("karva_chauth", date(2026, 10, 28)),
    "SY-0002": DemoFast(
        "navratri_one_meal", date(2026, 10, 15), "This day falls in Sharad Navratri 2026."
    ),
    "SY-0003": DemoFast(
        "ramadan",
        date(2027, 2, 20),
        "Ramadan 2027 is expected to run from about 9 February to 9 March in India.",
    ),
    "SY-0004": DemoFast(
        "ekadashi_phalahar",
        date(2026, 11, 5),
        "This date is an example. Please check the local calendar for the exact Ekadashi date.",
    ),
}

# The IDF-DAR totals that the demo records must give (docs/techstack.md, Section 9).
EXPECTED_IDF_DAR_TOTALS = {"SY-0001": 2.5, "SY-0002": 11.0, "SY-0003": 8.5, "SY-0004": 7.5}

"""The generator of synthetic health records for Indian adults with Type 2 Diabetes.

The starting distributions follow docs/techstack.md, Section 6.1. Every proportion
in this module is a starting value and a modelling assumption, and the data card
records each one. The generator ties related values together: for example, the
eGFR falls with age and with years of diabetes, and insulin becomes more likely
when HbA1c is high and diabetes is long-standing.

The generator links fasting patterns to communities with simple probabilities.
Real practice varies widely between families and regions, and the doctor can
change every plan.

Every record is synthetic and does not represent a real person.
"""

from __future__ import annotations

from datetime import date, time, timedelta

import numpy as np

from rozmarra.config import RANDOM_SEED
from rozmarra.ehr.records import MedicineStatement, PatientRecord, ScheduledDose
from rozmarra.fasting.calendar import CITIES
from rozmarra.risk.idf_dar import (
    AcuteComplications,
    FastingExperience,
    Hypoglycaemia,
    Macrovascular,
    PhysicalLabour,
    SelfMonitoring,
)

RECORD_DATE = date(2026, 10, 1)

# CYP2C9 allele frequencies in South Asian populations. Published Indian studies report
# about 4% to 7% for *2 and about 8% to 13% for *3 (see the data card for the sources).
CYP2C9_FREQUENCIES = {"*1": 0.85, "*2": 0.05, "*3": 0.10}

NAMES = {
    "hindu": {
        "female": [
            "Sunita",
            "Anita",
            "Kavita",
            "Meena",
            "Rekha",
            "Pooja",
            "Lakshmi",
            "Geeta",
            "Savita",
            "Neha",
            "Usha",
            "Asha",
            "Radha",
            "Shobha",
            "Kiran",
            "Manju",
            "Saroj",
            "Pushpa",
            "Nirmala",
            "Lata",
        ],
        "male": [
            "Ramesh",
            "Suresh",
            "Rajesh",
            "Mahesh",
            "Anil",
            "Vijay",
            "Sanjay",
            "Harish",
            "Prakash",
            "Dinesh",
            "Ashok",
            "Rakesh",
            "Mukesh",
            "Arun",
            "Gopal",
            "Mohan",
            "Shankar",
            "Naresh",
            "Vinod",
            "Kishore",
        ],
        "family": [
            "Sharma",
            "Verma",
            "Gupta",
            "Patel",
            "Reddy",
            "Iyer",
            "Nair",
            "Yadav",
            "Mishra",
            "Tiwari",
            "Pandey",
            "Rao",
            "Joshi",
            "Kulkarni",
            "Desai",
            "Chauhan",
            "Das",
            "Banerjee",
            "Pillai",
            "Srivastava",
        ],
    },
    "muslim": {
        "female": [
            "Fatima",
            "Ayesha",
            "Shabana",
            "Farida",
            "Nasreen",
            "Rukhsana",
            "Zainab",
            "Salma",
            "Rehana",
            "Naseem",
            "Shazia",
            "Yasmin",
        ],
        "male": [
            "Abdul",
            "Imran",
            "Salim",
            "Arif",
            "Mohammed",
            "Iqbal",
            "Rashid",
            "Javed",
            "Akhtar",
            "Farooq",
            "Shahid",
            "Naseer",
        ],
        "family": [
            "Khan",
            "Ahmed",
            "Qureshi",
            "Shaikh",
            "Ansari",
            "Siddiqui",
            "Hussain",
            "Rahman",
            "Pathan",
            "Mirza",
        ],
    },
    "jain": {
        "female": ["Sunanda", "Pramila", "Kusum", "Manisha", "Rajul", "Hema"],
        "male": ["Mahendra", "Rajendra", "Sunil", "Dilip", "Pankaj", "Nitin"],
        "family": ["Jain", "Shah", "Mehta", "Doshi", "Sanghvi", "Kothari"],
    },
    "sikh": {
        "female": ["Jaspreet", "Harpreet", "Manjeet", "Simran", "Kuldeep", "Rajinder"],
        "male": ["Gurpreet", "Harjeet", "Jaswinder", "Balwinder", "Manpreet", "Sukhdev"],
        "family": ["Kaur", "Singh", "Gill", "Sandhu", "Grewal", "Bedi"],
    },
    "christian": {
        "female": ["Mary", "Grace", "Elizabeth", "Teresa", "Rosy", "Agnes"],
        "male": ["Joseph", "Thomas", "George", "Peter", "Francis", "Paul"],
        "family": ["D'Souza", "Fernandes", "Thomas", "Mathew", "Varghese", "Pereira"],
    },
}
COMMUNITY_WEIGHTS = {"hindu": 0.72, "muslim": 0.17, "jain": 0.03, "sikh": 0.04, "christian": 0.04}

# Occupation and the matching level of physical work for the IDF-DAR score.
OCCUPATIONS = [
    ("Homemaker", PhysicalLabour.NONE, "female"),
    ("Office worker", PhysicalLabour.NONE, None),
    ("Schoolteacher", PhysicalLabour.NONE, None),
    ("Shopkeeper", PhysicalLabour.MODERATE, None),
    ("Tailor", PhysicalLabour.MODERATE, None),
    ("Driver", PhysicalLabour.MODERATE, "male"),
    ("Factory worker", PhysicalLabour.HIGH, None),
    ("Farmer", PhysicalLabour.HIGH, None),
    ("Vegetable vendor", PhysicalLabour.HIGH, None),
]


class _Generator:
    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)

    def choice(self, options, p=None):
        index = self.rng.choice(len(options), p=p)
        return options[index]

    def chance(self, probability: float) -> bool:
        return bool(self.rng.random() < probability)

    def normal(self, mean: float, sd: float, low: float, high: float) -> float:
        return float(np.clip(self.rng.normal(mean, sd), low, high))


def _creatinine_from_egfr(egfr: float, age: int, sex: str) -> float:
    """Invert the CKD-EPI 2021 creatinine equation by bisection, in mg/dL."""
    kappa, alpha, factor = (0.7, -0.241, 1.012) if sex == "female" else (0.9, -0.302, 1.0)

    def ckd_epi(scr: float) -> float:
        ratio = scr / kappa
        return 142 * min(ratio, 1) ** alpha * max(ratio, 1) ** -1.2 * 0.9938**age * factor

    low, high = 0.2, 10.0
    for _ in range(60):
        middle = (low + high) / 2
        if ckd_epi(middle) > egfr:
            low = middle
        else:
            high = middle
    return round((low + high) / 2, 2)


def _dose(name: str, *doses: tuple[time, float]) -> MedicineStatement:
    return MedicineStatement(
        name=name, schedule=[ScheduledDose(time=t, dose=dose) for t, dose in doses]
    )


MORNING, EVENING, NIGHT = time(8, 0), time(20, 30), time(22, 0)


def _medicines(
    g: _Generator, hba1c: float, years: float, egfr: float, hypertension: bool, heart: Macrovascular
) -> list[MedicineStatement]:
    medicines: list[MedicineStatement] = []
    # Insulin becomes more likely with a higher HbA1c and a longer duration of diabetes.
    # With the average HbA1c and duration, about a quarter of the patients take insulin.
    p_insulin = 1 / (1 + np.exp(-(-1.2 + 0.6 * (hba1c - 8.0) + 0.1 * (years - 8))))
    insulin = None
    if g.chance(p_insulin):
        insulin = "premixed" if g.chance(0.6) else "basal"
    if insulin == "premixed":
        morning = float(g.rng.integers(8, 25))
        evening = float(max(4, round(morning * g.normal(0.7, 0.1, 0.5, 0.9))))
        name = "premixed_insulin_30_70" if g.chance(0.6) else "biphasic_insulin_aspart_30"
        medicines.append(_dose(name, (MORNING, morning), (time(20, 0), evening)))
    elif insulin == "basal":
        name = "insulin_glargine" if g.chance(0.7) else "insulin_degludec"
        medicines.append(_dose(name, (NIGHT, float(g.rng.integers(10, 31)))))

    if egfr >= 30 and g.chance(0.88):
        dose = float(g.choice([500, 1000], p=[0.55, 0.45]))
        medicines.append(_dose("metformin", (MORNING, dose), (EVENING, dose)))

    if g.chance(0.3 if insulin == "premixed" else 0.55):
        kind = g.choice(["glimepiride", "gliclazide_mr", "glibenclamide"], p=[0.6, 0.33, 0.07])
        if kind == "glibenclamide" and egfr < 60:
            kind = "gliclazide_mr"
        dose = {
            "glimepiride": float(g.choice([1, 2, 3, 4], p=[0.3, 0.4, 0.1, 0.2])),
            "gliclazide_mr": float(g.choice([30, 60, 90, 120], p=[0.3, 0.45, 0.1, 0.15])),
            "glibenclamide": float(g.choice([2.5, 5, 10], p=[0.3, 0.5, 0.2])),
        }[kind]
        medicines.append(_dose(kind, (MORNING, dose)))

    if g.chance(0.35):
        kind = g.choice(["teneligliptin", "sitagliptin", "vildagliptin"], p=[0.5, 0.3, 0.2])
        if kind == "vildagliptin":
            medicines.append(_dose(kind, (MORNING, 50.0), (EVENING, 50.0)))
        else:
            medicines.append(_dose(kind, (MORNING, 20.0 if kind == "teneligliptin" else 100.0)))

    if egfr >= 30 and g.chance(0.25):
        if g.chance(0.6):
            medicines.append(_dose("dapagliflozin", (MORNING, 10.0)))
        else:
            medicines.append(_dose("empagliflozin", (MORNING, float(g.choice([10, 25])))))

    if not medicines:
        medicines.append(_dose("metformin", (MORNING, 500.0), (EVENING, 500.0)))

    if hypertension:
        medicines.append(_dose("telmisartan", (MORNING, float(g.choice([40, 80])))))
        if g.chance(0.2):
            medicines.append(_dose("hydrochlorothiazide", (MORNING, 12.5)))
    if heart is not Macrovascular.NONE:
        medicines.append(_dose("atorvastatin", (time(21, 0), float(g.choice([10, 20, 40])))))
        medicines.append(_dose("aspirin", (time(13, 0), 75.0)))
    if (heart is not Macrovascular.NONE and g.chance(0.5)) or (hypertension and g.chance(0.1)):
        medicines.append(_dose("metoprolol", (MORNING, float(g.choice([25, 50])))))
    return medicines


def _fasts(g: _Generator, community: str, sex: str) -> tuple[list[str], str]:
    fasts: list[str] = []
    if community == "hindu":
        word = "व्रत" if g.chance(0.7) else "उपवास"
        if g.chance(0.5):
            fasts.append("navratri_one_meal" if g.chance(0.4) else "navratri_phalahar")
        if sex == "female" and g.chance(0.6):
            fasts.append("karva_chauth")
        if g.chance(0.3):
            fasts.append("nirjala_ekadashi" if g.chance(0.1) else "ekadashi_phalahar")
        if g.chance(0.05):
            fasts.append("chhath")
    elif community == "muslim":
        word = "रोज़ा"
        if g.chance(0.85):
            fasts.append("ramadan")
    elif community == "jain":
        word = "उपवास"
        fasts.append("jain_upvas" if g.chance(0.5) else "jain_ekasana")
    else:
        word = "उपवास"
        if g.chance(0.3):
            fasts.append("custom")
    return fasts, word


def generate_record(g: _Generator, patient_id: str, record_date: date = RECORD_DATE):
    community = g.choice(list(COMMUNITY_WEIGHTS), p=list(COMMUNITY_WEIGHTS.values()))
    sex = "female" if g.chance(0.5) else "male"
    names = NAMES[community]
    given = g.choice(names[sex])
    family = g.choice(names["family"])
    if community == "sikh":
        family = "Kaur" if sex == "female" else "Singh"

    age = int(round(g.normal(56, 10, 35, 80)))
    birth_date = record_date - timedelta(days=int(age * 365.25 + g.rng.integers(30, 330)))
    years = g.normal(min(8.0, age - 30) if age < 45 else 9.0, 5.5, 1, min(25, age - 25))
    diagnosis_date = record_date - timedelta(days=int(years * 365.25))

    height = g.normal(166, 6, 150, 185) if sex == "male" else g.normal(153, 6, 140, 170)
    bmi = g.normal(26, 4, 18.5, 40)
    weight = round(bmi * (height / 100) ** 2, 1)
    hba1c = round(g.normal(8.0, 1.1, 6.5, 11.0), 1)
    fasting_glucose = round(g.normal(0.85 * (28.7 * hba1c - 46.7), 15, 90, 300))
    fasting_insulin = round(float(np.clip(g.rng.lognormal(np.log(10), 0.4), 3, 30)), 1)
    egfr = round(g.normal(110 - 0.8 * (age - 35) - 0.5 * years, 12, 30, 115))
    creatinine = _creatinine_from_egfr(egfr, age, sex)

    hypertension = g.chance(0.35 + 0.006 * (age - 35))
    heart = g.choice(
        [Macrovascular.NONE, Macrovascular.STABLE, Macrovascular.UNSTABLE],
        p=[0.83 - 0.003 * (age - 35), 0.15 + 0.0025 * (age - 35), 0.02 + 0.0005 * (age - 35)],
    )
    medicines = _medicines(g, hba1c, years, egfr, hypertension, heart)
    names_taken = {m.name for m in medicines}
    on_insulin_or_su = bool(
        names_taken
        & {
            "premixed_insulin_30_70",
            "biphasic_insulin_aspart_30",
            "insulin_glargine",
            "insulin_degludec",
            "glimepiride",
            "gliclazide_mr",
            "glibenclamide",
        }
    )
    hypo_p = [0.55, 0.32, 0.07, 0.04, 0.02] if on_insulin_or_su else [0.7, 0.22, 0.04, 0.025, 0.015]
    hypoglycaemia = g.choice(
        [
            Hypoglycaemia.NONE,
            Hypoglycaemia.LESS_THAN_WEEKLY,
            Hypoglycaemia.SEVERAL_PER_WEEK,
            Hypoglycaemia.RECENT_SEVERE,
            Hypoglycaemia.UNAWARE,
        ],
        p=hypo_p,
    )
    occupations = [o for o in OCCUPATIONS if o[2] in (None, sex)]
    if age >= 62 and g.chance(0.7):
        occupation, labour = "Retired", PhysicalLabour.NONE
    else:
        occupation, labour, _ = occupations[g.rng.integers(len(occupations))]
    fasts, word = _fasts(g, community, sex)
    resting_hr = int(round(g.normal(76, 8, 55, 100)))
    if "metoprolol" in names_taken:
        resting_hr = max(52, resting_hr - 8)
    alleles = list(CYP2C9_FREQUENCIES)
    genotype = sorted(
        g.rng.choice(alleles, size=2, p=list(CYP2C9_FREQUENCIES.values())).tolist(),
        key=alleles.index,
    )

    return PatientRecord(
        patient_id=patient_id,
        record_date=record_date,
        given_name=given,
        family_name=family,
        sex=sex,
        birth_date=birth_date,
        city=g.choice([c for c in CITIES if c != "Dhanbad"]),
        language="hi" if g.chance(0.65) else "en",
        fast_word=word,
        fasts_kept=fasts,
        occupation=occupation,
        diagnosis_date=diagnosis_date,
        hba1c_percent=hba1c,
        fasting_glucose_mg_dl=fasting_glucose,
        fasting_insulin_uu_ml=fasting_insulin,
        creatinine_mg_dl=creatinine,
        egfr=egfr,
        weight_kg=weight,
        height_cm=round(height, 1),
        systolic_bp=int(round(g.normal(142 if hypertension else 124, 10, 100, 190))),
        diastolic_bp=int(round(g.normal(86 if hypertension else 78, 7, 60, 110))),
        resting_heart_rate=resting_hr,
        hypertension=hypertension,
        chronic_kidney_disease=egfr < 60,
        heart_disease=heart,
        medicines=medicines,
        cyp2c9="/".join(genotype),
        hypoglycaemia=hypoglycaemia,
        self_monitoring=g.choice(
            [
                SelfMonitoring.AS_NEEDED,
                SelfMonitoring.LESS_THAN_NEEDED,
                SelfMonitoring.NEEDED_NOT_DONE,
            ],
            p=[0.3, 0.5, 0.2],
        ),
        physical_labour=labour,
        frail_or_impaired_cognition=age > 70 and g.chance(0.1),
        support_at_home=not (age > 65 and g.chance(0.2)),
        previous_fasting=FastingExperience.NEGATIVE
        if g.chance(0.12)
        else FastingExperience.NEUTRAL_OR_POSITIVE,
        acute_complications=g.choice(
            [
                AcuteComplications.NONE,
                AcuteComplications.LAST_12_MONTHS,
                AcuteComplications.LAST_6_MONTHS,
                AcuteComplications.LAST_3_MONTHS,
            ],
            p=[0.97, 0.02, 0.007, 0.003],
        ),
    )


def generate_records(
    count: int, seed: int = RANDOM_SEED, first_number: int = 1001, record_date: date = RECORD_DATE
) -> list[PatientRecord]:
    """Generate synthetic health records with identifiers SY-1001, SY-1002 and so on."""
    g = _Generator(seed)
    return [generate_record(g, f"SY-{first_number + i:04d}", record_date) for i in range(count)]

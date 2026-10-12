"""The health record that Rozmarra keeps for each synthetic patient.

The record holds the static data stream: demographics, diagnoses, laboratory
results, vital signs, medicines, the CYP2C9 genotype and the inputs for the
IDF-DAR score. The module ehr.fhir turns a record into a FHIR R4 Bundle and back.

Every record in this prototype is synthetic and does not represent a real person.
"""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field

from rozmarra.fasting.plan import FastingPlan
from rozmarra.fasting.templates import UsualDose
from rozmarra.formatting import clock_12h
from rozmarra.medicines import MedicineClass, get_medicine
from rozmarra.risk.idf_dar import (
    AcuteComplications,
    DiabetesType,
    FastingExperience,
    Frailty,
    Hypoglycaemia,
    IdfDarInputs,
    Macrovascular,
    PhysicalLabour,
    Pregnancy,
    SelfMonitoring,
    treatments_from_medicines,
)

# The CPIC activity score of each CYP2C9 allele (docs/techstack.md, Section 5.3).
CYP2C9_ALLELE_SCORES = {"*1": 1.0, "*2": 0.5, "*3": 0.0}


class ScheduledDose(BaseModel):
    time: time
    dose: float = Field(gt=0)


class MedicineStatement(BaseModel):
    """One medicine that the patient takes every day, with the time and size of each dose."""

    name: str
    schedule: list[ScheduledDose]

    @property
    def doses_per_day(self) -> int:
        return len(self.schedule)

    def describe_dose(self, scheduled: ScheduledDose) -> str:
        unit = get_medicine(self.name).unit
        return f"{scheduled.dose:g} {unit} at {clock_12h(scheduled.time)}"

    @property
    def display(self) -> str:
        parts = [self.describe_dose(scheduled) for scheduled in self.schedule]
        joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        return f"{get_medicine(self.name).display_name}: {joined}"


class PatientRecord(BaseModel):
    patient_id: str
    source: str = "synthetic"
    # The date of the latest laboratory results and vital signs.
    record_date: date = date(2026, 10, 1)
    given_name: str
    family_name: str
    sex: str  # "female" or "male"
    birth_date: date
    city: str
    language: str  # "en" or "hi", the preferred language for the patient plan
    fast_word: str  # The patient's own word for the fast, such as व्रत, उपवास or रोज़ा
    fasts_kept: list[str]  # Fasting template identifiers
    occupation: str
    diagnosis_date: date
    hba1c_percent: float
    fasting_glucose_mg_dl: float
    fasting_insulin_uu_ml: float
    creatinine_mg_dl: float
    egfr: float
    weight_kg: float
    height_cm: float
    systolic_bp: int
    diastolic_bp: int
    resting_heart_rate: int
    hypertension: bool = False
    chronic_kidney_disease: bool = False
    heart_disease: Macrovascular = Macrovascular.NONE
    medicines: list[MedicineStatement]
    cyp2c9: str = "*1/*1"
    hypoglycaemia: Hypoglycaemia = Hypoglycaemia.NONE
    self_monitoring: SelfMonitoring = SelfMonitoring.AS_NEEDED
    physical_labour: PhysicalLabour = PhysicalLabour.NONE
    frail_or_impaired_cognition: bool = False
    support_at_home: bool = True
    previous_fasting: FastingExperience = FastingExperience.NEUTRAL_OR_POSITIVE
    acute_complications: AcuteComplications = AcuteComplications.NONE
    pregnancy: Pregnancy = Pregnancy.NOT_PREGNANT

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"

    def age_on(self, day: date) -> int:
        before_birthday = (day.month, day.day) < (self.birth_date.month, self.birth_date.day)
        return day.year - self.birth_date.year - before_birthday

    def years_with_diabetes_on(self, day: date) -> float:
        return round((day - self.diagnosis_date).days / 365.25, 1)

    def label_on(self, day: date) -> str:
        """The name with the age, as the writing standard asks: "Sunita Sharma, Age 54"."""
        return f"{self.full_name}, Age {self.age_on(day)}"

    @property
    def bmi(self) -> float:
        return round(self.weight_kg / (self.height_cm / 100) ** 2, 1)

    @property
    def cyp2c9_activity_score(self) -> float:
        return sum(CYP2C9_ALLELE_SCORES[allele] for allele in self.cyp2c9.split("/"))

    @property
    def cyp2c9_clearance_factor(self) -> float:
        """The sulfonylurea clearance factor c_cyp = 0.3 + 0.35 × activity score (an assumption)."""
        return 0.3 + 0.35 * self.cyp2c9_activity_score

    def usual_doses(self) -> list[UsualDose]:
        """The usual daily doses, in the form that the fasting plan builder uses."""
        return [
            UsualDose(m.name, scheduled.dose, scheduled.time)
            for m in self.medicines
            for scheduled in m.schedule
        ]

    def medicine_classes(self) -> set[MedicineClass]:
        return {get_medicine(m.name).medicine_class for m in self.medicines}

    @property
    def takes_beta_blocker(self) -> bool:
        return MedicineClass.BETA_BLOCKER in self.medicine_classes()

    def frailty_on(self, day: date) -> Frailty:
        if self.frail_or_impaired_cognition:
            return Frailty.IMPAIRED_COGNITION_OR_FRAILTY
        if self.age_on(day) > 70 and not self.support_at_home:
            return Frailty.OVER_70_WITHOUT_SUPPORT
        return Frailty.NONE

    def idf_dar_inputs(
        self, day: date, plan: FastingPlan | None = None, fasting_hours: float | None = None
    ) -> IdfDarInputs:
        """Collect the IDF-DAR inputs. The fasting hours come from the plan when one is given."""
        if plan is not None:
            fasting_hours = plan.longest_gap_without_food_hours
        return IdfDarInputs(
            diabetes_type=DiabetesType.TYPE_2,
            years_with_diabetes=self.years_with_diabetes_on(day),
            hypoglycaemia=self.hypoglycaemia,
            hba1c_percent=self.hba1c_percent,
            treatments=treatments_from_medicines((m.name, m.doses_per_day) for m in self.medicines),
            self_monitoring=self.self_monitoring,
            acute_complications=self.acute_complications,
            macrovascular=self.heart_disease,
            egfr=self.egfr,
            pregnancy=self.pregnancy,
            frailty=self.frailty_on(day),
            physical_labour=self.physical_labour,
            previous_fasting=self.previous_fasting,
            fasting_hours=fasting_hours,
        )

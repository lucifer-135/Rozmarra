"""Conversion between Rozmarra health records and FHIR R4 Bundles.

Each synthetic patient has one FHIR R4 Bundle of type "collection"
(docs/techstack.md, Section 4.2). Every resource carries the HL7 security tag
HTEST ("test health data"), so the synthetic label travels with the data.

Standard codes: SNOMED CT for conditions, LOINC for observations, UCUM for units,
the WHO ATC classification for medicines and HGNC for the CYP2C9 gene. The genotype
follows the HL7 Genomics Reporting guidance in a simplified form. The IDF-DAR inputs
have no standard codes, so they use Rozmarra's own code system.
"""

from __future__ import annotations

import uuid
from datetime import date, time
from typing import Any

from rozmarra.ehr.records import MedicineStatement, PatientRecord, ScheduledDose
from rozmarra.medicines import get_medicine
from rozmarra.risk.idf_dar import (
    AcuteComplications,
    FastingExperience,
    Hypoglycaemia,
    Macrovascular,
    PhysicalLabour,
    Pregnancy,
    SelfMonitoring,
)

SNOMED = "http://snomed.info/sct"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"
ATC = "http://www.whocc.no/atc"
HGNC = "http://www.genenames.org/geneId"
# The standard FHIR extension that states the language of one element, such as a name.
EXT_LANGUAGE = "http://hl7.org/fhir/StructureDefinition/language"
BCP47 = "urn:ietf:bcp:47"
OBSERVATION_CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
CONDITION_CLINICAL = "http://terminology.hl7.org/CodeSystem/condition-clinical"
ACT_REASON = "http://terminology.hl7.org/CodeSystem/v3-ActReason"

PATIENT_ID_SYSTEM = "urn:rozmarra:patient-id"
MEDICINE_SYSTEM = "urn:rozmarra:medicine"
IDF_DAR_INPUT = "urn:rozmarra:idf-dar-input"
IDF_DAR_ANSWER = "urn:rozmarra:idf-dar-answer"
EXT_FAST_WORD = "urn:rozmarra:extension:fast-word"
EXT_FASTS_KEPT = "urn:rozmarra:extension:fasts-kept"

SYNTHETIC_TAG = {"system": ACT_REASON, "code": "HTEST", "display": "test health data"}
_NAMESPACE = uuid.UUID("6f2b8a1e-3c4d-4e5f-9a0b-1c2d3e4f5a6b")

CONDITIONS = {
    "type_2_diabetes": ("44054006", "Diabetes mellitus type 2"),
    "hypertension": ("38341003", "Hypertensive disorder"),
    "chronic_kidney_disease": ("709044004", "Chronic kidney disease"),
    "heart_disease": ("53741008", "Coronary arteriosclerosis"),
}

# Laboratory results and vital signs: record field, LOINC code, display, UCUM unit, category.
MEASUREMENTS = (
    ("hba1c_percent", "4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%", "laboratory"),
    (
        "fasting_glucose_mg_dl",
        "1558-6",
        "Fasting glucose [Mass/volume] in Serum or Plasma",
        "mg/dL",
        "laboratory",
    ),
    (
        "fasting_insulin_uu_ml",
        "20448-7",
        "Insulin [Units/volume] in Serum or Plasma",
        "u[IU]/mL",
        "laboratory",
    ),
    (
        "creatinine_mg_dl",
        "2160-0",
        "Creatinine [Mass/volume] in Serum or Plasma",
        "mg/dL",
        "laboratory",
    ),
    (
        "egfr",
        "98979-8",
        "Glomerular filtration rate/1.73 sq M.predicted (CKD-EPI 2021)",
        "mL/min/{1.73_m2}",
        "laboratory",
    ),
    ("weight_kg", "29463-7", "Body weight", "kg", "vital-signs"),
    ("height_cm", "8302-2", "Body height", "cm", "vital-signs"),
    ("resting_heart_rate", "8867-4", "Heart rate", "/min", "vital-signs"),
)
BMI_CODE = ("39156-5", "Body mass index (BMI) [Ratio]")
BP_PANEL = ("85354-9", "Blood pressure panel with all children optional")
SYSTOLIC = ("8480-6", "Systolic blood pressure")
DIASTOLIC = ("8462-4", "Diastolic blood pressure")
OCCUPATION = ("11341-5", "History of Occupation")
GENOTYPE = ("84413-4", "Genotype display name")
GENE_STUDIED = ("48018-6", "Gene studied [ID]")
CYP2C9_GENE = ("HGNC:2623", "CYP2C9")

# The IDF-DAR inputs: record field, code, display, and the enum type (None for yes or no).
IDF_DAR_ITEMS = (
    ("hypoglycaemia", "hypoglycaemia", "History of low blood sugar", Hypoglycaemia),
    ("self_monitoring", "self-monitoring", "Self-monitoring of blood glucose", SelfMonitoring),
    ("physical_labour", "physical-labour", "Physical work", PhysicalLabour),
    ("previous_fasting", "previous-fasting", "Previous fasting experience", FastingExperience),
    (
        "acute_complications",
        "acute-complications",
        "DKA or HHS in the last 12 months",
        AcuteComplications,
    ),
    ("heart_disease", "macrovascular", "Heart and blood vessel disease", Macrovascular),
    ("pregnancy", "pregnancy", "Pregnancy", Pregnancy),
    ("frail_or_impaired_cognition", "frailty", "Frailty or impaired cognition", None),
    ("support_at_home", "support-at-home", "Support at home", None),
)


def _id(patient_id: str, name: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{patient_id}/{name}"))


def _meta() -> dict[str, Any]:
    return {"tag": [SYNTHETIC_TAG]}


def _concept(system: str, code: str, display: str) -> dict[str, Any]:
    return {"coding": [{"system": system, "code": code, "display": display}], "text": display}


def _category(code: str) -> list[dict[str, Any]]:
    return [{"coding": [{"system": OBSERVATION_CATEGORY, "code": code}]}]


def _quantity(value: float, unit: str) -> dict[str, Any]:
    return {"value": value, "unit": unit, "system": UCUM, "code": unit}


def to_bundle(record: PatientRecord) -> dict[str, Any]:
    """Turn a health record into a FHIR R4 Bundle (a JSON-ready dictionary)."""
    pid = record.patient_id
    patient_ref = {"reference": f"urn:uuid:{_id(pid, 'patient')}"}
    effective = record.record_date.isoformat()
    resources: list[tuple[str, dict[str, Any]]] = []

    resources.append(
        (
            "patient",
            {
                "resourceType": "Patient",
                "meta": _meta(),
                "identifier": [{"system": PATIENT_ID_SYSTEM, "value": pid}],
                "name": _names(record),
                "gender": record.sex,
                "birthDate": record.birth_date.isoformat(),
                "address": [{"city": record.city, "country": "IN"}],
                "communication": [
                    {
                        "language": _concept(BCP47, record.language, record.language),
                        "preferred": True,
                    }
                ],
                "extension": [{"url": EXT_FAST_WORD, "valueString": record.fast_word}]
                + [{"url": EXT_FASTS_KEPT, "valueCode": fast} for fast in record.fasts_kept],
            },
        )
    )

    present = {
        "type_2_diabetes": True,
        "hypertension": record.hypertension,
        "chronic_kidney_disease": record.chronic_kidney_disease,
        "heart_disease": record.heart_disease is not Macrovascular.NONE,
    }
    for key, (code, display) in CONDITIONS.items():
        if not present[key]:
            continue
        condition = {
            "resourceType": "Condition",
            "meta": _meta(),
            "clinicalStatus": _concept(CONDITION_CLINICAL, "active", "Active"),
            "code": _concept(SNOMED, code, display),
            "subject": patient_ref,
        }
        if key == "type_2_diabetes":
            condition["onsetDateTime"] = record.diagnosis_date.isoformat()
        if key == "heart_disease":
            condition["note"] = [{"text": f"The disease is {record.heart_disease.value}."}]
        resources.append((f"condition-{key}", condition))

    for field, code, display, unit, category in MEASUREMENTS:
        resources.append(
            (
                f"observation-{field}",
                {
                    "resourceType": "Observation",
                    "meta": _meta(),
                    "status": "final",
                    "category": _category(category),
                    "code": _concept(LOINC, code, display),
                    "subject": patient_ref,
                    "effectiveDateTime": effective,
                    "valueQuantity": _quantity(getattr(record, field), unit),
                },
            )
        )
    resources.append(
        (
            "observation-bmi",
            {
                "resourceType": "Observation",
                "meta": _meta(),
                "status": "final",
                "category": _category("vital-signs"),
                "code": _concept(LOINC, *BMI_CODE),
                "subject": patient_ref,
                "effectiveDateTime": effective,
                "valueQuantity": _quantity(record.bmi, "kg/m2"),
            },
        )
    )
    resources.append(
        (
            "observation-blood-pressure",
            {
                "resourceType": "Observation",
                "meta": _meta(),
                "status": "final",
                "category": _category("vital-signs"),
                "code": _concept(LOINC, *BP_PANEL),
                "subject": patient_ref,
                "effectiveDateTime": effective,
                "component": [
                    {
                        "code": _concept(LOINC, *SYSTOLIC),
                        "valueQuantity": _quantity(record.systolic_bp, "mm[Hg]"),
                    },
                    {
                        "code": _concept(LOINC, *DIASTOLIC),
                        "valueQuantity": _quantity(record.diastolic_bp, "mm[Hg]"),
                    },
                ],
            },
        )
    )
    resources.append(
        (
            "observation-occupation",
            {
                "resourceType": "Observation",
                "meta": _meta(),
                "status": "final",
                "category": _category("social-history"),
                "code": _concept(LOINC, *OCCUPATION),
                "subject": patient_ref,
                "valueString": record.occupation,
            },
        )
    )
    resources.append(
        (
            "observation-cyp2c9",
            {
                "resourceType": "Observation",
                "meta": _meta(),
                "status": "final",
                "category": _category("laboratory"),
                "code": _concept(LOINC, *GENOTYPE),
                "subject": patient_ref,
                "effectiveDateTime": effective,
                "valueCodeableConcept": {"text": f"CYP2C9 {record.cyp2c9}"},
                "component": [
                    {
                        "code": _concept(LOINC, *GENE_STUDIED),
                        "valueCodeableConcept": _concept(HGNC, *CYP2C9_GENE),
                    }
                ],
            },
        )
    )
    for field, code, display, kind in IDF_DAR_ITEMS:
        value = getattr(record, field)
        observation: dict[str, Any] = {
            "resourceType": "Observation",
            "meta": _meta(),
            "status": "final",
            "category": _category("survey"),
            "code": _concept(IDF_DAR_INPUT, code, display),
            "subject": patient_ref,
            "effectiveDateTime": effective,
        }
        if kind is None:
            observation["valueBoolean"] = bool(value)
        else:
            observation["valueCodeableConcept"] = _concept(IDF_DAR_ANSWER, value.value, value.value)
        resources.append((f"observation-idf-dar-{code}", observation))

    for medicine in record.medicines:
        info = get_medicine(medicine.name)
        coding = [{"system": MEDICINE_SYSTEM, "code": info.name, "display": info.display_name}]
        if info.atc_code:
            coding.insert(0, {"system": ATC, "code": info.atc_code, "display": info.display_name})
        unit = "[IU]" if info.unit == "units" else info.unit
        resources.append(
            (
                f"medication-{medicine.name}",
                {
                    "resourceType": "MedicationStatement",
                    "meta": _meta(),
                    "status": "active",
                    "medicationCodeableConcept": {"coding": coding, "text": info.display_name},
                    "subject": patient_ref,
                    # One dosage entry for each daily dose, because the doses can differ.
                    "dosage": [
                        {
                            "text": f"{info.display_name} {medicine.describe_dose(scheduled)}",
                            "timing": {
                                "repeat": {
                                    "frequency": 1,
                                    "period": 1,
                                    "periodUnit": "d",
                                    "timeOfDay": [scheduled.time.strftime("%H:%M:%S")],
                                }
                            },
                            "doseAndRate": [
                                {
                                    "doseQuantity": {
                                        "value": scheduled.dose,
                                        "unit": info.unit,
                                        "system": UCUM,
                                        "code": unit,
                                    }
                                }
                            ],
                        }
                        for scheduled in medicine.schedule
                    ],
                },
            )
        )

    entries = []
    for name, resource in resources:
        resource_id = _id(pid, name)
        resource["id"] = resource_id
        entries.append({"fullUrl": f"urn:uuid:{resource_id}", "resource": resource})
    return {
        "resourceType": "Bundle",
        "id": _id(pid, "bundle"),
        "meta": _meta(),
        "type": "collection",
        "timestamp": f"{effective}T00:00:00+05:30",
        "entry": entries,
    }


def _code_of(concept: dict[str, Any], system: str) -> str | None:
    return next((c["code"] for c in concept.get("coding", []) if c.get("system") == system), None)


def _names(record: PatientRecord) -> list[dict[str, Any]]:
    """The Latin name first, and the Devanagari name, when the record has one, tagged as Hindi."""
    names: list[dict[str, Any]] = [{"family": record.family_name, "given": [record.given_name]}]
    if record.given_name_hi and record.family_name_hi:
        names.append(
            {
                "extension": [{"url": EXT_LANGUAGE, "valueCode": "hi"}],
                "family": record.family_name_hi,
                "given": [record.given_name_hi],
            }
        )
    return names


def _hindi_name(names: list[dict[str, Any]]) -> dict[str, str]:
    for name in names:
        tags = name.get("extension", [])
        if any(e["url"] == EXT_LANGUAGE and e["valueCode"] == "hi" for e in tags):
            return {"given_name_hi": name["given"][0], "family_name_hi": name["family"]}
    return {}


def from_bundle(bundle: dict[str, Any]) -> PatientRecord:
    """Read a health record back from a FHIR R4 Bundle that to_bundle created."""
    resources = [entry["resource"] for entry in bundle["entry"]]
    patient = next(r for r in resources if r["resourceType"] == "Patient")
    values: dict[str, Any] = {
        "patient_id": next(
            i["value"] for i in patient["identifier"] if i["system"] == PATIENT_ID_SYSTEM
        ),
        "given_name": patient["name"][0]["given"][0],
        "family_name": patient["name"][0]["family"],
        **_hindi_name(patient["name"]),
        "sex": patient["gender"],
        "birth_date": date.fromisoformat(patient["birthDate"]),
        "city": patient["address"][0]["city"],
        "language": _code_of(patient["communication"][0]["language"], BCP47),
        "fast_word": next(
            e["valueString"] for e in patient["extension"] if e["url"] == EXT_FAST_WORD
        ),
        "fasts_kept": [e["valueCode"] for e in patient["extension"] if e["url"] == EXT_FASTS_KEPT],
        "medicines": [],
    }
    measurement_fields = {code: field for field, code, *_ in MEASUREMENTS}
    idf_dar_fields = {code: (field, kind) for field, code, _, kind in IDF_DAR_ITEMS}
    condition_keys = {code: key for key, (code, _) in CONDITIONS.items()}

    for resource in resources:
        kind = resource["resourceType"]
        if kind == "Condition":
            key = condition_keys.get(_code_of(resource["code"], SNOMED))
            if key == "type_2_diabetes":
                values["diagnosis_date"] = date.fromisoformat(resource["onsetDateTime"])
            elif key in {"hypertension", "chronic_kidney_disease"}:
                values[key] = True
        elif kind == "Observation":
            loinc = _code_of(resource["code"], LOINC)
            local = _code_of(resource["code"], IDF_DAR_INPUT)
            if loinc in measurement_fields:
                values[measurement_fields[loinc]] = resource["valueQuantity"]["value"]
                values["record_date"] = date.fromisoformat(resource["effectiveDateTime"])
            elif loinc == BP_PANEL[0]:
                for component in resource["component"]:
                    code = _code_of(component["code"], LOINC)
                    field = "systolic_bp" if code == SYSTOLIC[0] else "diastolic_bp"
                    values[field] = int(component["valueQuantity"]["value"])
            elif loinc == OCCUPATION[0]:
                values["occupation"] = resource["valueString"]
            elif loinc == GENOTYPE[0]:
                values["cyp2c9"] = resource["valueCodeableConcept"]["text"].split(" ", 1)[1]
            elif local in idf_dar_fields:
                field, enum_type = idf_dar_fields[local]
                if enum_type is None:
                    values[field] = resource["valueBoolean"]
                else:
                    code = _code_of(resource["valueCodeableConcept"], IDF_DAR_ANSWER)
                    values[field] = enum_type(code)
        elif kind == "MedicationStatement":
            values["medicines"].append(
                MedicineStatement(
                    name=_code_of(resource["medicationCodeableConcept"], MEDICINE_SYSTEM),
                    schedule=[
                        ScheduledDose(
                            time=time.fromisoformat(dosage["timing"]["repeat"]["timeOfDay"][0]),
                            dose=dosage["doseAndRate"][0]["doseQuantity"]["value"],
                        )
                        for dosage in resource["dosage"]
                    ],
                )
            )
    return PatientRecord(**values)

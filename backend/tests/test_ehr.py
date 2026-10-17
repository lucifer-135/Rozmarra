from datetime import date

import pytest

from rozmarra.ehr.demo_patients import (
    DEMO_FASTS,
    DEMO_PATIENTS,
    EXPECTED_IDF_DAR_TOTALS,
    SUNITA,
)
from rozmarra.ehr.fhir import SYNTHETIC_TAG, from_bundle, to_bundle
from rozmarra.ehr.generator import generate_records
from rozmarra.fasting.templates import TEMPLATES_BY_ID, build_plan
from rozmarra.medicines import get_medicine
from rozmarra.risk.idf_dar import calculate
from rozmarra.risk.rules import dehydration_caution

GENERATED = generate_records(60, seed=7)


def demo_plan(record):
    fast = DEMO_FASTS[record.patient_id]
    plan = build_plan(
        fast.template_id, record.patient_id, fast.date, record.city, record.usual_doses()
    )
    return fast, plan


@pytest.mark.parametrize("record", DEMO_PATIENTS, ids=lambda r: r.full_name)
def test_demo_patients_give_the_expected_idf_dar_totals(record):
    fast, plan = demo_plan(record)
    result = calculate(record.idf_dar_inputs(fast.date, plan))
    assert result.is_complete
    assert result.total == EXPECTED_IDF_DAR_TOTALS[record.patient_id]


@pytest.mark.parametrize(
    "record", DEMO_PATIENTS + tuple(GENERATED[:20]), ids=lambda r: r.patient_id
)
def test_records_survive_a_round_trip_through_fhir(record):
    assert from_bundle(to_bundle(record)) == record


@pytest.mark.parametrize("record", DEMO_PATIENTS, ids=lambda r: r.patient_id)
def test_bundles_are_tagged_as_synthetic_and_references_resolve(record):
    bundle = to_bundle(record)
    assert bundle["type"] == "collection"
    full_urls = {entry["fullUrl"] for entry in bundle["entry"]}
    for entry in bundle["entry"]:
        resource = entry["resource"]
        assert SYNTHETIC_TAG in resource["meta"]["tag"]
        if "subject" in resource:
            assert resource["subject"]["reference"] in full_urls
    kinds = {entry["resource"]["resourceType"] for entry in bundle["entry"]}
    assert kinds == {"Patient", "Condition", "Observation", "MedicationStatement"}


def test_sunita_carries_one_reduced_function_cyp2c9_variant():
    assert SUNITA.cyp2c9 == "*1/*3"
    assert SUNITA.cyp2c9_activity_score == 1.0
    assert SUNITA.cyp2c9_clearance_factor == pytest.approx(0.65)
    assert SUNITA.label_on(date(2026, 10, 28)) == "Sunita Sharma, Age 54"


def test_sunita_receives_the_dehydration_caution_on_karva_chauth():
    fast, plan = demo_plan(SUNITA)
    caution = dehydration_caution(
        plan.water_allowed,
        plan.fast_hours,
        [m.name for m in SUNITA.medicines],
        SUNITA.egfr,
        SUNITA.age_on(fast.date),
    )
    assert caution is not None
    assert "dapagliflozin" in caution.reasons[0]


def test_ramesh_takes_premixed_insulin_twice_a_day_with_different_doses():
    ramesh = DEMO_PATIENTS[1]
    insulin = next(m for m in ramesh.medicines if m.name == "premixed_insulin_30_70")
    assert [d.dose for d in insulin.schedule] == [18, 12]
    assert insulin.display == (
        "Premixed human insulin 30/70: 18 units at 8:00 am and 12 units at 8:00 pm"
    )


def test_the_generator_is_reproducible():
    assert generate_records(5, seed=11) == generate_records(5, seed=11)
    assert generate_records(5, seed=11) != generate_records(5, seed=12)


def test_generated_records_stay_within_the_planned_ranges():
    for record in GENERATED:
        age = record.age_on(record.record_date)
        assert 35 <= age <= 80
        assert 6.5 <= record.hba1c_percent <= 11
        assert 30 <= record.egfr <= 115
        assert 1 <= record.years_with_diabetes_on(record.record_date) <= 25
        assert any(get_medicine(m.name).is_diabetes_medicine for m in record.medicines)
        assert all(fast in TEMPLATES_BY_ID for fast in record.fasts_kept)
        assert record.cyp2c9.count("/") == 1
        if record.egfr < 30:
            assert "metformin" not in {m.name for m in record.medicines}
        assert calculate(record.idf_dar_inputs(record.record_date, fasting_hours=14)).is_complete


def test_fasting_patterns_follow_the_generator_rules():
    for record in generate_records(300, seed=3):
        if "karva_chauth" in record.fasts_kept:
            assert record.sex == "female"
        if "ramadan" in record.fasts_kept:
            assert record.fast_word == "रोज़ा"


def test_a_record_without_a_hindi_name_falls_back_to_the_latin_name():
    record = SUNITA.model_copy(update={"given_name_hi": None, "family_name_hi": None})
    assert record.full_name_hi == "Sunita Sharma"
    assert len(to_bundle(record)["entry"][0]["resource"]["name"]) == 1
    assert from_bundle(to_bundle(record)).full_name_hi == "Sunita Sharma"

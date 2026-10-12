from dataclasses import replace

import pytest

from rozmarra.risk.idf_dar import (
    MISSING,
    TREATMENT_POINTS,
    AcuteComplications,
    DiabetesType,
    FastingExperience,
    Frailty,
    Hypoglycaemia,
    IdfDarInputs,
    Macrovascular,
    PhysicalLabour,
    Pregnancy,
    RiskCategory,
    SelfMonitoring,
    Treatment,
    calculate,
    category_for,
    treatments_from_medicines,
)

# A complete record that scores 0 points on every item. Each test changes one item.
BASELINE = IdfDarInputs(
    diabetes_type=DiabetesType.TYPE_2,
    years_with_diabetes=5,
    hypoglycaemia=Hypoglycaemia.NONE,
    hba1c_percent=7.0,
    treatments=(Treatment.OTHER,),
    self_monitoring=SelfMonitoring.AS_NEEDED,
    acute_complications=AcuteComplications.NONE,
    macrovascular=Macrovascular.NONE,
    egfr=90,
    pregnancy=Pregnancy.NOT_PREGNANT,
    frailty=Frailty.NONE,
    physical_labour=PhysicalLabour.NONE,
    previous_fasting=FastingExperience.NEUTRAL_OR_POSITIVE,
    fasting_hours=14,
)


def points(result, key):
    return next(item.points for item in result.items if item.key == key)


def test_baseline_scores_zero_and_is_complete():
    result = calculate(BASELINE)
    assert result.total == 0
    assert result.category is RiskCategory.LOW
    assert result.is_complete


# The four demo patients in docs/techstack.md, Section 9.
SUNITA = replace(
    BASELINE,
    years_with_diabetes=8,
    hba1c_percent=8.4,
    treatments=treatments_from_medicines(
        [("glimepiride", 1), ("metformin", 2), ("dapagliflozin", 1)]
    ),
    self_monitoring=SelfMonitoring.LESS_THAN_NEEDED,
    fasting_hours=15.25,
)
RAMESH = replace(
    BASELINE,
    years_with_diabetes=15,
    hypoglycaemia=Hypoglycaemia.LESS_THAN_WEEKLY,
    hba1c_percent=7.9,
    treatments=treatments_from_medicines([("premixed_insulin_30_70", 2), ("gliclazide_mr", 1)]),
    macrovascular=Macrovascular.STABLE,
    egfr=52,
    fasting_hours=20,
)
ABDUL = replace(
    BASELINE,
    years_with_diabetes=10,
    hypoglycaemia=Hypoglycaemia.LESS_THAN_WEEKLY,
    hba1c_percent=7.6,
    treatments=treatments_from_medicines([("insulin_glargine", 1), ("metformin", 2)]),
    self_monitoring=SelfMonitoring.LESS_THAN_NEEDED,
    physical_labour=PhysicalLabour.MODERATE,
    previous_fasting=FastingExperience.NEGATIVE,
    fasting_hours=13.5,
)
KAMLA = replace(
    BASELINE,
    years_with_diabetes=20,
    hba1c_percent=7.2,
    treatments=treatments_from_medicines([("glibenclamide", 1)]),
    egfr=48,
    frailty=Frailty.OVER_70_WITHOUT_SUPPORT,
)


@pytest.mark.parametrize(
    ("inputs", "total", "category"),
    [
        (SUNITA, 2.5, RiskCategory.LOW),
        (RAMESH, 11.0, RiskCategory.HIGH),
        (ABDUL, 8.5, RiskCategory.HIGH),
        (KAMLA, 7.5, RiskCategory.HIGH),
    ],
    ids=["Sunita Sharma", "Ramesh Patel", "Abdul Rahman", "Kamla Devi"],
)
def test_demo_patients_match_the_expected_totals(inputs, total, category):
    result = calculate(inputs)
    assert result.total == total
    assert result.category is category
    assert result.is_complete


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("years_with_diabetes", 9.9, 0),
        ("years_with_diabetes", 10, 1),
        ("hba1c_percent", 7.4, 0),
        ("hba1c_percent", 7.5, 1),
        ("hba1c_percent", 9.0, 1),
        ("hba1c_percent", 9.1, 2),
        ("egfr", 29.9, 6.5),
        ("egfr", 30, 4),
        ("egfr", 44.9, 4),
        ("egfr", 45, 2),
        ("egfr", 59.9, 2),
        ("egfr", 60, 0),
        ("fasting_hours", 15.9, 0),
        ("fasting_hours", 16, 1),
    ],
)
def test_numeric_boundaries(key, value, expected):
    assert points(calculate(replace(BASELINE, **{key: value})), key) == expected


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("diabetes_type", DiabetesType.TYPE_1, 1),
        ("hypoglycaemia", Hypoglycaemia.UNAWARE, 6.5),
        ("hypoglycaemia", Hypoglycaemia.RECENT_SEVERE, 5.5),
        ("hypoglycaemia", Hypoglycaemia.SEVERAL_PER_WEEK, 3.5),
        ("hypoglycaemia", Hypoglycaemia.LESS_THAN_WEEKLY, 1),
        ("self_monitoring", SelfMonitoring.NEEDED_NOT_DONE, 2),
        ("acute_complications", AcuteComplications.LAST_3_MONTHS, 3),
        ("acute_complications", AcuteComplications.LAST_6_MONTHS, 2),
        ("acute_complications", AcuteComplications.LAST_12_MONTHS, 1),
        ("macrovascular", Macrovascular.UNSTABLE, 6.5),
        ("pregnancy", Pregnancy.NOT_WITHIN_TARGETS, 6.5),
        ("pregnancy", Pregnancy.WITHIN_TARGETS, 3.5),
        ("frailty", Frailty.IMPAIRED_COGNITION_OR_FRAILTY, 6.5),
        ("physical_labour", PhysicalLabour.HIGH, 4),
    ],
)
def test_choice_items(key, value, expected):
    assert points(calculate(replace(BASELINE, **{key: value})), key) == expected


@pytest.mark.parametrize(
    ("total", "category"),
    [
        (0, RiskCategory.LOW),
        (3, RiskCategory.LOW),
        (3.5, RiskCategory.MODERATE),
        (6, RiskCategory.MODERATE),
        (6.5, RiskCategory.HIGH),
    ],
)
def test_category_boundaries(total, category):
    assert category_for(total) is category


def test_the_highest_treatment_score_is_used():
    inputs = replace(
        BASELINE, treatments=(Treatment.GLIBENCLAMIDE, Treatment.BASAL_INSULIN, Treatment.OTHER)
    )
    assert points(calculate(inputs), "treatments") == 1.5


@pytest.mark.parametrize(
    ("medicines", "expected"),
    [
        ([("premixed_insulin_30_70", 2)], Treatment.MIXED_INSULIN_SEVERAL_DAILY),
        ([("biphasic_insulin_aspart_30", 1)], Treatment.MIXED_INSULIN_ONCE_DAILY),
        ([("insulin_glargine", 1)], Treatment.BASAL_INSULIN),
        ([("insulin_glargine", 1), ("insulin_aspart", 3)], Treatment.BASAL_BOLUS_OR_PUMP),
        ([("glibenclamide", 1)], Treatment.GLIBENCLAMIDE),
        ([("gliclazide_mr", 1)], Treatment.GLICLAZIDE_GLIMEPIRIDE_REPAGLINIDE),
        ([("repaglinide", 3)], Treatment.GLICLAZIDE_GLIMEPIRIDE_REPAGLINIDE),
        ([("metformin", 2), ("sitagliptin", 1)], Treatment.OTHER),
        ([("metformin", 2), ("telmisartan", 1)], Treatment.OTHER),
    ],
)
def test_medicines_are_classified_for_the_treatment_item(medicines, expected):
    treatments = treatments_from_medicines(medicines)
    assert expected in treatments
    result = calculate(replace(BASELINE, treatments=treatments))
    assert points(result, "treatments") == TREATMENT_POINTS[expected]


def test_missing_information_is_shown_and_not_guessed():
    inputs = replace(BASELINE, hba1c_percent=None, egfr=None, hypoglycaemia=Hypoglycaemia.NONE)
    result = calculate(inputs)
    assert not result.is_complete
    assert result.missing == ("HbA1c", "Kidney function (eGFR)")
    assert all(item.detail == MISSING for item in result.items if item.is_missing)
    assert result.total == 0
    assert result.min_total == 0
    assert result.max_total == 2 + 6.5
    assert result.min_category is RiskCategory.LOW
    assert result.max_category is RiskCategory.HIGH


def test_an_empty_record_reports_every_item_as_missing():
    result = calculate(IdfDarInputs())
    assert len(result.missing) == 14
    assert result.max_total == sum(item.max_points for item in result.items)

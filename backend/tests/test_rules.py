import pytest

from rozmarra.risk.rules import dehydration_caution


def test_caution_for_sglt2_inhibitor_in_a_long_fast_without_water():
    caution = dehydration_caution(
        water_allowed=False,
        fast_hours=15.3,
        medicines=["dapagliflozin", "metformin"],
        egfr=85,
        age=54,
    )
    assert caution is not None
    assert caution.code == "C1"
    assert caution.reasons == ("The patient takes dapagliflozin, an SGLT2 inhibitor.",)


@pytest.mark.parametrize(
    ("kwargs", "expected_reason"),
    [
        ({"medicines": ["hydrochlorothiazide"]}, "a diuretic"),
        ({"egfr": 48}, "below 60"),
        ({"age": 71}, "older than 65 years"),
    ],
)
def test_each_risk_factor_triggers_the_caution(kwargs, expected_reason):
    args = {"water_allowed": False, "fast_hours": 13, "medicines": [], "egfr": 90, "age": 50}
    args.update(kwargs)
    caution = dehydration_caution(**args)
    assert caution is not None
    assert any(expected_reason in reason for reason in caution.reasons)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"water_allowed": True},
        {"fast_hours": 11.9},
        {"medicines": ["metformin"], "egfr": 90, "age": 65},
        {"egfr": None, "age": None, "medicines": []},
    ],
)
def test_no_caution_when_the_rule_does_not_apply(kwargs):
    args = {"water_allowed": False, "fast_hours": 15, "medicines": [], "egfr": 90, "age": 50}
    args.update(kwargs)
    assert dehydration_caution(**args) is None

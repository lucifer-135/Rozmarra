from datetime import date, datetime, time, timedelta

import pytest

from rozmarra.ehr.demo_patients import DEMO_FASTS, DEMO_PATIENTS
from rozmarra.fasting.templates import build_plan
from rozmarra.formatting import hindi_date, hindi_time, patient_time
from rozmarra.plans.checks import check_times
from rozmarra.plans.render import plan_context, render_message, render_plan

RECORDS = {r.patient_id: r for r in DEMO_PATIENTS}


def _plan(patient_id: str, **changes):
    record = RECORDS[patient_id]
    fast = DEMO_FASTS[patient_id]
    plan = build_plan(fast.template_id, patient_id, fast.date, record.city, record.usual_doses())
    approval = {"approved_by": "Meera Iyer", "approved_on": date(2026, 10, 13)}
    return plan.model_copy(update={**approval, **changes})


def test_times_for_patients_use_the_12_hour_clock_and_hindi_parts_of_the_day():
    assert patient_time(time(12, 0)) == "12 noon"
    assert patient_time(time(8, 0)) == "8 am"
    assert patient_time(time(20, 14)) == "8:14 pm"
    assert hindi_time(time(8, 0)) == "सुबह 8 बजे"
    assert hindi_time(time(12, 0)) == "दोपहर 12 बजे"
    assert hindi_time(time(17, 30)) == "शाम 5:30 बजे"
    assert hindi_time(time(20, 14)) == "रात 8:14 बजे"
    assert hindi_date(date(2026, 10, 28)) == "28 अक्टूबर 2026"


def test_check_times_follow_the_rules():
    plan = _plan("SY-0001")  # Karva Chauth from 5:00 am to 8:14 pm, with a meal at 8:24 pm
    lowest = datetime(2026, 10, 28, 12, 46)
    checks = check_times(plan, lowest)
    assert checks == sorted(checks)
    assert all(c.minute in (0, 30) for c in checks)
    assert datetime(2026, 10, 28, 7, 0) in checks, "The first check is 2 hours after the start."
    assert datetime(2026, 10, 28, 19, 0) in checks, "One check is 1 hour before the end."
    assert datetime(2026, 10, 28, 12, 30) in checks, "One check is 30 minutes before the lowest."
    assert datetime(2026, 10, 28, 22, 30) in checks, "One check is 2 hours after the meal."
    gaps = [b - a for a, b in zip(checks, checks[1:], strict=False)]
    assert min(gaps) >= timedelta(minutes=75)


def test_no_check_wakes_the_patient_at_night():
    plan = _plan("SY-0004")  # Ekadashi until the next morning
    for moment in check_times(plan, None):
        is_meal_check = moment == check_times(plan, None)[-1]
        assert time(6, 0) <= moment.time() <= time(22, 0) or is_meal_check


@pytest.mark.parametrize("patient_id", sorted(RECORDS))
@pytest.mark.parametrize("language", ["en", "hi"])
def test_both_templates_render_without_missing_values(patient_id, language):
    plan = _plan(patient_id)
    html = render_plan(RECORDS[patient_id], plan, language)
    assert "Dr Meera Iyer" in html and RECORDS[patient_id].fast_word in html
    message = render_message(RECORDS[patient_id], plan, language)
    assert "70 mg/dL" in message and "{{" not in message


def test_the_plan_states_the_doctors_medicine_changes():
    usual = _plan("SY-0001")
    medicines = []
    for dose in usual.medicines:
        if dose.name == "glimepiride":
            dose = dose.model_copy(update={"dose": 1.0})
        if dose.name == "dapagliflozin":
            continue
        medicines.append(dose)
    plan = usual.model_copy(update={"medicines": medicines, "approved_contact": "City clinic"})
    english = render_plan(RECORDS["SY-0001"], plan, "en")
    assert "take Glimepiride 1 mg at" in english and "instead of 2 mg" in english
    assert "not to take Dapagliflozin 10 mg" in english
    assert "The contact details are: City clinic." in english
    hindi = render_plan(RECORDS["SY-0001"], plan, "hi")
    assert "ग्लिमेपिराइड 2 mg की जगह 1 mg लें" in hindi
    assert "करवा चौथ के व्रत के लिए आपकी योजना" in hindi


def test_the_hindi_plan_uses_the_correct_form_of_roza():
    hindi = render_plan(RECORDS["SY-0003"], _plan("SY-0003"), "hi")
    assert "रमज़ान के रोज़े के लिए" in hindi and "तुरंत रोज़ा खोल दें" in hindi


def test_an_unapproved_plan_cannot_be_printed():
    plan = _plan("SY-0001", approved_by=None, approved_on=None)
    with pytest.raises(ValueError, match="must approve"):
        plan_context(RECORDS["SY-0001"], plan, "en")
    with pytest.raises(ValueError, match="language"):
        plan_context(RECORDS["SY-0001"], _plan("SY-0001"), "fr")

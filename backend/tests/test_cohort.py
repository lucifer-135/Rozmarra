from datetime import timedelta

import numpy as np
import pytest

from rozmarra.ehr.demo_patients import DEMO_FASTS, RAMESH, SUNITA
from rozmarra.ehr.generator import generate_records
from rozmarra.synth.cohort import EPISODES, build_timeline, chunk_tables
from rozmarra.synth.split import fold_of, is_test
from rozmarra.twin.model import CENTRES, FITTED
from rozmarra.twin.profiles import load_twins
from rozmarra.twin.virtual_patients import demo_twin, held_out_twins, training_twins, virtual_twin

TWINS = load_twins()
pytestmark = pytest.mark.skipif(not TWINS, reason="The fitted twins are missing.")


def test_two_periods_of_the_same_person_share_a_fold():
    assert fold_of("SH-2001-0") == fold_of("SH-2001-1")
    assert all(is_test(t["patient_id"]) for t in held_out_twins(TWINS))
    assert not any(is_test(t["patient_id"]) for t in training_twins(TWINS))


def test_virtual_twins_use_the_population_sulfonylurea_effect_and_stay_in_range():
    rng = np.random.default_rng(3)
    bounds = {p.name: (p.low, p.high) for p in FITTED}
    for record in generate_records(20, seed=5):
        twin = virtual_twin(record, training_twins(TWINS), record.record_date, rng)
        assert twin.estimated_values["gamma_su"] == pytest.approx(CENTRES["gamma_su"])
        for name, value in twin.true_values.items():
            low, high = bounds[name]
            assert low * 0.999 <= value <= high * 1.001
        assert not is_test(twin.donor_id)


def test_the_demo_twin_is_the_same_every_time():
    fast = DEMO_FASTS[SUNITA.patient_id]
    first = demo_twin(SUNITA, TWINS, fast.date)
    second = demo_twin(SUNITA, TWINS, fast.date)
    assert first.donor_id == second.donor_id
    assert first.true_values == second.true_values


def test_a_timeline_has_normal_days_before_three_fasting_episodes():
    record = generate_records(1, seed=9)[0]
    twin = virtual_twin(record, training_twins(TWINS), record.record_date, np.random.default_rng(1))
    timeline = build_timeline(twin, "training", seed=11)
    assert len(timeline.episodes) == EPISODES
    first_window = timeline.episodes[0].plan.window_start
    assert first_window - timeline.start >= timedelta(days=7)
    windows = [(e.plan.window_start, e.plan.window_end) for e in timeline.episodes]
    usual = [m for m in timeline.logged_meals if m["episode"] is None]
    assert not any(a <= m["time"] <= b for m in usual for a, b in windows), (
        "Usual meals never fall inside a plan window."
    )


def test_a_patient_without_risky_medicines_never_gets_a_plan_change():
    record = generate_records(40, seed=13)
    safe = [
        r
        for r in record
        if not any(
            m.name.startswith(("gli", "insulin", "premixed", "biphasic")) for m in r.medicines
        )
    ][0]
    twin = virtual_twin(safe, training_twins(TWINS), safe.record_date, np.random.default_rng(2))
    timeline = build_timeline(twin, "training", seed=17)
    assert not any(e.medicine_changed for e in timeline.episodes)


def test_the_tables_of_a_small_cohort_are_synthetic_and_complete():
    fast = DEMO_FASTS[RAMESH.patient_id]
    twin = demo_twin(RAMESH, TWINS, fast.date)
    timeline = build_timeline(
        twin,
        "demo",
        5,
        templates=[fast.template_id],
        fast_dates=[fast.date],
        history_days=7,
        allow_plan_change=False,
    )
    tables = chunk_tables([timeline])
    series = tables["timeseries"]
    assert set(series["signal"]) == {
        "glucose_cgm",
        "heart_rate",
        "hrv_rmssd",
        "mets",
        "steps",
        "sleep_stage",
    }
    assert set(series["source"]) == {"synthetic"}
    assert set(series["timezone"]) == {"Asia/Kolkata"}
    cgm = series[series["signal"] == "glucose_cgm"]["value"]
    assert cgm.between(40, 400).all()
    assert (tables["events"]["event_type"] == "fast").sum() == 1
    assert len(tables["labels_e2"]) == 1
    assert set(tables["labels_e1"]["label"].unique()) <= {0, 1}

import json

import pandas as pd
import pytest

from rozmarra.config import RAW_DIR
from rozmarra.data import cgmacros, shanghai
from rozmarra.data.foods import estimate_meal
from rozmarra.data.harmonise import TIMESERIES_COLUMNS


def names_and_doses(doses):
    return [(d.name, d.amount) for d in doses]


def test_insulin_text_with_two_insulins_is_read():
    doses = shanghai.parse_insulin("insulin glargine, 10 IU, Humulin 70/30, 8 IU")
    assert names_and_doses(doses) == [("insulin_glargine", 10), ("premixed_insulin_30_70", 8)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Humulin 70/30  8 IU", [("premixed_insulin_30_70", 8)]),
        ("insulin glarigine, 12 IU", [("insulin_glargine", 12)]),
        ("insulin aspart 70/30, 14 IU", [("biphasic_insulin_aspart_30", 14)]),
        ("insulin aspart, 4 IU", [("insulin_aspart", 4)]),
        ("Gansulin 40R, 6 IU", [("premixed_insulin_40_60", 6)]),
    ],
)
def test_insulin_names_map_to_the_catalogue(text, expected):
    assert names_and_doses(shanghai.parse_insulin(text)) == expected


def test_intravenous_insulin_is_read_from_the_infusion_text():
    text = "500ml 0.9% sodium chloride, 15 IU Novolin R, 10 ml 10% potassium chloride"
    assert names_and_doses(shanghai.parse_iv_insulin(text)) == [("regular_insulin", 15)]


def test_oral_doses_in_grams_are_converted_to_milligrams():
    doses = shanghai.parse_oral("metformin 0.5 g, acarbose 50 mg")
    assert names_and_doses(doses) == [("metformin", 500), ("acarbose", 50)]
    assert all(d.note == "" for d in doses)


def test_an_implausible_unit_is_corrected_and_recorded():
    (dose,) = shanghai.parse_oral("empagliflozin 10 g")
    assert (dose.name, dose.amount) == ("empagliflozin", 10)
    assert "reads it as milligrams" in dose.note


def test_a_dose_that_stays_implausible_is_kept_and_flagged():
    (dose,) = shanghai.parse_oral("linagliptin 0.1 g")
    assert dose.amount == 100
    assert dose.note == "The recorded dose is outside the expected range."


def test_the_combination_tablet_gives_two_medicines():
    text = "sitagliptinphosphate/metforminhydrochloride tablets 50 mg / 500 mg"
    assert names_and_doses(shanghai.parse_oral(text)) == [("sitagliptin", 50), ("metformin", 500)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [("gliclazide 30 mg", "gliclazide_mr"), ("gliclazide 80 mg", "gliclazide")],
)
def test_gliclazide_form_follows_the_dose(text, expected):
    assert shanghai.parse_oral(text)[0].name == expected


def test_hba1c_conversion_from_mmol_per_mol():
    percent = 59.568 / shanghai.HBA1C_MMOL_PER_PERCENT + shanghai.HBA1C_OFFSET
    assert round(percent, 1) == 7.6


@pytest.mark.parametrize(
    ("text", "carbs"),
    [
        ("Rice 100 g\nVegetable 150 g", 32.0),
        ("Steamed egg custard 100 g", 1.0),
        ("Eggplant 100 g", 6.0),
        ("Yellow rice wine 100 ml", 4.0),
        # A line without a gram amount counts as 100 g.
        ("Boiled eggs", 1.0),
    ],
)
def test_meal_carbohydrates_are_estimated_from_whole_words(text, carbs):
    assert estimate_meal(text).carbs_g == carbs


def test_an_unrecorded_meal_has_no_estimate():
    estimate = estimate_meal("data not available")
    assert estimate.carbs_g is None
    assert estimate.source == "not recorded"


def minute_frame(activity_column: str, activity_values) -> pd.DataFrame:
    times = pd.date_range("2020-05-01 08:00", periods=20, freq="1min")
    frame = pd.DataFrame(
        {
            "Timestamp": times.astype(str),
            "Libre GL": 100.0,
            "Dexcom GL": [100.0 + i for i in range(20)],
            "HR": 70.0,
            activity_column: activity_values,
            "Meal Type": [None] * 20,
            "Carbs": [None] * 20,
            "Amount Consumed": [None] * 20,
        }
    )
    frame.loc[3, ["Meal Type", "Carbs", "Amount Consumed"]] = ["Lunch", 80, 50]
    return frame


def test_cgmacros_minutes_become_five_minute_signals():
    series, events = cgmacros.convert_participant("CG-999", minute_frame("METs", 20))
    assert list(series.columns) == TIMESERIES_COLUMNS
    glucose = series[series["signal"] == "glucose_cgm"]
    assert len(glucose) == 4
    assert glucose["value"].iloc[0] == pytest.approx(102.0)
    assert set(series[series["signal"] == "mets"]["value"]) == {2.0}
    meal = json.loads(events.iloc[0]["details"])
    assert meal["carbs_g"] == 40.0, "The carbohydrates follow the share of the meal that was eaten."


def test_cgmacros_intensity_levels_become_approximate_mets():
    series, _ = cgmacros.convert_participant("CG-999", minute_frame("Intensity", 2))
    assert set(series[series["signal"] == "mets"]["value"]) == {4.5}


@pytest.mark.parametrize(
    ("hba1c", "status"),
    [(5.6, "healthy"), (5.7, "prediabetes"), (6.4, "prediabetes"), (6.5, "type_2_diabetes")],
)
def test_cgmacros_groups_follow_hba1c(hba1c, status):
    assert cgmacros.diabetes_status(hba1c) == status


SHANGHAI_FILE = RAW_DIR / "shanghai_t2dm" / "Shanghai_T2DM" / "2000_0_20201230.xlsx"


@pytest.mark.skipif(not SHANGHAI_FILE.exists(), reason="The ShanghaiT2DM files are not downloaded.")
def test_a_real_shanghai_period_loads():
    series, events, _ = shanghai.load_period(SHANGHAI_FILE)
    glucose = series[series["signal"] == "glucose_cgm"]
    assert len(glucose) > 1000
    assert glucose["patient_id"].unique().tolist() == ["SH-2000-0"]
    assert (events["event_type"] == "meal").any()

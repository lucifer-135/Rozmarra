import math

import pytest

from rozmarra.ml.explain import TEMPLATES, sentence
from rozmarra.ml.train import risk_word


def test_reasons_are_full_polite_sentences_in_both_languages():
    en, hi = sentence("minutes_since_last_meal", 660)
    assert en == "No food has been eaten for 11 hours."
    assert hi.endswith("।")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-18.4, "Glucose has fallen by 18 mg/dL in the last 30 minutes."),
        (12.0, "Glucose has risen by 12 mg/dL in the last 30 minutes."),
    ],
)
def test_glucose_changes_use_the_right_direction(value, expected):
    assert sentence("cgm_change_30", value)[0] == expected


def test_sentences_that_do_not_fit_the_value_are_left_out():
    assert sentence("water_allowed", 1.0) is None
    assert sentence("hr_delta_from_usual", -3.0) is None
    assert sentence("takes_insulin", 0.0) is None
    assert sentence("cgm_now", math.nan) is None
    assert sentence("an_unknown_feature", 1.0) is None


def test_every_template_avoids_shorthand_and_ends_with_a_full_stop():
    banned = ("hypo ", "meds", "BG ", " pt ")
    for en, hi in TEMPLATES.values():
        assert en.endswith("."), en
        assert hi.endswith("।"), hi
        assert not any(word in f" {en} " for word in banned), en


@pytest.mark.parametrize(
    ("chance", "word"),
    [(0.05, "Low"), (0.2, "Moderate"), (0.49, "Moderate"), (0.5, "High"), (0.95, "High")],
)
def test_risk_words_follow_the_starting_thresholds(chance, word):
    assert risk_word(chance) == word

"""Plain-language reasons for each prediction (docs/techstack.md, Section 7.3).

Rozmarra uses the SHAP TreeExplainer to find the features that raised the estimated chance
the most. Each feature becomes a sentence from a fixed template in English and Hindi. No
AI writes these sentences. A native Hindi speaker will review the Hindi templates.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd

from rozmarra.ml.train import TrainedModel


def _hours(minutes: float) -> str:
    return f"{minutes / 60:.1f}".rstrip("0").rstrip(".")


def _int(value: float) -> str:
    return f"{value:.0f}"


# Each entry gives the English and Hindi sentence, and a test of whether the sentence fits
# the value. When the test fails, the generic sentence is used.
TEMPLATES: dict[str, tuple[str, str]] = {
    "minutes_since_last_meal": (
        "No food has been eaten for {hours} hours.",
        "{hours} घंटे से कुछ नहीं खाया गया है।",
    ),
    "minutes_since_fast_start": (
        "The fast started {hours} hours ago.",
        "उपवास {hours} घंटे पहले शुरू हुआ था।",
    ),
    "minutes_until_fast_end": ("The fast ends in {hours} hours.", "उपवास {hours} घंटे में पूरा होगा।"),
    "minutes_fasted_at_prediction": (
        "The patient will have fasted for {hours} hours.",
        "मरीज़ का उपवास {hours} घंटे का हो चुका होगा।",
    ),
    "cgm_now": ("The current glucose is {value} mg/dL.", "अभी शुगर {value} mg/dL है।"),
    "cgm_min_2h": (
        "The lowest glucose in the last 2 hours was {value} mg/dL.",
        "पिछले 2 घंटों में सबसे कम शुगर {value} mg/dL थी।",
    ),
    "cgm_sd_2h": (
        "Glucose has varied a lot in the last 2 hours.",
        "पिछले 2 घंटों में शुगर बहुत ऊपर-नीचे हुई है।",
    ),
    "twin_min_120": (
        "The twin predicts a lowest value of {value} mg/dL in the next 2 hours.",
        "ट्विन के अनुसार अगले 2 घंटों में शुगर {value} mg/dL तक गिर सकती है।",
    ),
    "twin_30": (
        "The twin predicts {value} mg/dL in 30 minutes.",
        "ट्विन के अनुसार 30 मिनट बाद शुगर {value} mg/dL हो सकती है।",
    ),
    "twin_60": (
        "The twin predicts {value} mg/dL in 60 minutes.",
        "ट्विन के अनुसार 60 मिनट बाद शुगर {value} mg/dL हो सकती है।",
    ),
    "twin_120": (
        "The twin predicts {value} mg/dL in 2 hours.",
        "ट्विन के अनुसार 2 घंटे बाद शुगर {value} mg/dL हो सकती है।",
    ),
    "twin_60_p10": (
        "The twin's lower estimate for 60 minutes from now is {value} mg/dL.",
        "ट्विन का 60 मिनट बाद का कम अनुमान {value} mg/dL है।",
    ),
    "twin_insulin": (
        "The twin estimates that insulin levels are raised.",
        "ट्विन के अनुसार शरीर में इंसुलिन का स्तर बढ़ा हुआ है।",
    ),
    "twin_su_effect": (
        "The sulfonylurea taken earlier is still acting strongly.",
        "पहले ली गई सल्फ़ोनिलयूरिया दवा अभी भी तेज़ी से असर कर रही है।",
    ),
    "twin_fasting_factor": (
        "Glucose production by the liver has fallen during the long fast.",
        "लंबे उपवास के दौरान लिवर कम ग्लूकोज़ बना रहा है।",
    ),
    "twin_carbs_absorbing": (
        "Little food is still being absorbed.",
        "पेट में अब बहुत कम भोजन पच रहा है।",
    ),
    "hr_delta_from_usual": (
        "The heart rate is {value} beats per minute higher than usual for this time of day.",
        "दिल की धड़कन इस समय के सामान्य स्तर से {value} धड़कन प्रति मिनट ज़्यादा है।",
    ),
    "hr_slope_30": (
        "The heart rate has risen in the last 30 minutes.",
        "पिछले 30 मिनट में दिल की धड़कन बढ़ी है।",
    ),
    "rmssd_ratio": (
        "Heart rate variability is lower than usual.",
        "दिल की धड़कन की परिवर्तनशीलता सामान्य से कम है।",
    ),
    "steps_last_60": (
        "The patient has walked {value} steps in the last hour.",
        "मरीज़ पिछले एक घंटे में {value} कदम चले हैं।",
    ),
    "steps_last_30": (
        "The patient has walked {value} steps in the last 30 minutes.",
        "मरीज़ पिछले 30 मिनट में {value} कदम चले हैं।",
    ),
    "mets_now": ("The patient is physically active now.", "मरीज़ अभी शारीरिक रूप से सक्रिय हैं।"),
    "water_allowed": ("This fast allows no water.", "इस उपवास में पानी नहीं पिया जाता।"),
    "hist_lows_14d": (
        "There were {value} episodes of low blood sugar in the last 14 days.",
        "पिछले 14 दिनों में {value} बार शुगर कम हुई।",
    ),
    "hist_lows_7d": (
        "There were {value} episodes of low blood sugar in the last 7 days.",
        "पिछले 7 दिनों में {value} बार शुगर कम हुई।",
    ),
    "hist_tbr_14d": (
        "Glucose was below 70 mg/dL for {percent}% of the time in the last 14 days.",
        "पिछले 14 दिनों में {percent}% समय शुगर 70 mg/dL से कम रही।",
    ),
    "hist_tbr_7d": (
        "Glucose was below 70 mg/dL for {percent}% of the time in the last 7 days.",
        "पिछले 7 दिनों में {percent}% समय शुगर 70 mg/dL से कम रही।",
    ),
    "takes_insulin": ("The patient takes insulin.", "मरीज़ इंसुलिन लेते हैं।"),
    "takes_premixed": ("The patient takes premixed insulin.", "मरीज़ प्रीमिक्स इंसुलिन लेते हैं।"),
    "takes_basal": ("The patient takes basal insulin.", "मरीज़ बेसल इंसुलिन लेते हैं।"),
    "takes_sulfonylurea": ("The patient takes a sulfonylurea.", "मरीज़ सल्फ़ोनिलयूरिया दवा लेते हैं।"),
    "su_dose_ratio": (
        "The sulfonylurea dose is relatively high.",
        "सल्फ़ोनिलयूरिया दवा की खुराक अपेक्षाकृत ज़्यादा है।",
    ),
    "insulin_daily_units": (
        "The patient takes {value} units of insulin each day.",
        "मरीज़ रोज़ {value} यूनिट इंसुलिन लेते हैं।",
    ),
    "cyp2c9_activity": (
        "The patient carries a CYP2C9 variant that slows the clearance of sulfonylureas.",
        "मरीज़ में CYP2C9 का ऐसा प्रकार है जिससे सल्फ़ोनिलयूरिया दवा शरीर में ज़्यादा देर रहती है।",
    ),
    "hypo_history": (
        "The patient has had low blood sugar before.",
        "मरीज़ की शुगर पहले भी कम हो चुकी है।",
    ),
    "hypo_unaware": (
        "The patient may not feel the signs of low blood sugar.",
        "मरीज़ को शुगर कम होने के लक्षण शायद महसूस न हों।",
    ),
    "beta_blocker": (
        "The patient takes a beta-blocker, which can hide a fast heart rate.",
        "मरीज़ बीटा-ब्लॉकर लेते हैं, जिससे तेज़ धड़कन का पता नहीं चलता।",
    ),
    "age": ("The patient is {value} years old.", "मरीज़ की उम्र {value} वर्ष है।"),
    "egfr": ("The eGFR is {value} mL/min/1.73 m².", "eGFR {value} mL/min/1.73 m² है।"),
    "hba1c": ("The HbA1c is {decimal}%.", "HbA1c {decimal}% है।"),
    "idf_dar_total": ("The IDF-DAR score is {decimal}.", "IDF-DAR स्कोर {decimal} है।"),
    "planned_carbs": (
        "The planned meal that breaks the fast has {value} g of carbohydrate.",
        "उपवास खोलने के भोजन में {value} ग्राम कार्बोहाइड्रेट है।",
    ),
    "twin_peak_after_meal": (
        "The twin predicts a peak of {value} mg/dL after the meal.",
        "ट्विन के अनुसार भोजन के बाद शुगर {value} mg/dL तक जा सकती है।",
    ),
    "twin_peak_p90": (
        "The twin's higher estimate of the peak after the meal is {value} mg/dL.",
        "ट्विन का भोजन के बाद का ऊँचा अनुमान {value} mg/dL है।",
    ),
    "planned_category": (
        "The planned meal contains fast-absorbing food, such as sweets or dates.",
        "उपवास खोलने के भोजन में जल्दी पचने वाली चीज़ें हैं, जैसे मिठाई या खजूर।",
    ),
}
CHANGE_TEMPLATES = {
    "falling": (
        "Glucose has fallen by {value} mg/dL in the last {window} minutes.",
        "पिछले {window} मिनट में शुगर {value} mg/dL कम हुई है।",
    ),
    "rising": (
        "Glucose has risen by {value} mg/dL in the last {window} minutes.",
        "पिछले {window} मिनट में शुगर {value} mg/dL बढ़ी है।",
    ),
}
SLOPE_TEMPLATES = {
    "falling": (
        "Glucose is falling by about {value} mg/dL every 10 minutes.",
        "शुगर हर 10 मिनट में लगभग {value} mg/dL कम हो रही है।",
    ),
    "rising": (
        "Glucose is rising by about {value} mg/dL every 10 minutes.",
        "शुगर हर 10 मिनट में लगभग {value} mg/dL बढ़ रही है।",
    ),
}
# Features that give almost the same message. At most one reason comes from each group.
SIMILAR = {
    "twin_forecast": {
        "twin_30",
        "twin_60",
        "twin_120",
        "twin_60_p10",
        "twin_min_120",
        "twin_min_60",
        "twin_peak_after_meal",
        "twin_peak_p90",
    },
    "glucose_change": {"cgm_change_15", "cgm_change_30", "cgm_change_60", "cgm_slope_30"},
    "glucose_level": {"cgm_now", "cgm_min_2h"},
    "history": {"hist_lows_7d", "hist_lows_14d", "hist_tbr_7d", "hist_tbr_14d"},
    "fast_timing": {
        "minutes_since_fast_start",
        "minutes_until_fast_end",
        "minutes_fasted_at_prediction",
    },
    "insulin": {"takes_insulin", "takes_premixed", "takes_basal", "insulin_daily_units"},
    "sulfonylurea": {"takes_sulfonylurea", "su_dose_ratio", "twin_su_effect"},
    "steps": {"steps_last_30", "steps_last_60"},
}
GENERIC = (
    "Another factor in the patient's data raised the estimated chance.",
    "मरीज़ के डेटा के एक और कारण से अनुमानित संभावना बढ़ी।",
)
# A sentence only fits some values. For example, "This fast allows no water" fits only 0.
FITS = {
    "water_allowed": lambda v: v == 0,
    "planned_category": lambda v: v == 0,
    "hr_delta_from_usual": lambda v: v > 2,
    "hr_slope_30": lambda v: v > 0,
    "rmssd_ratio": lambda v: v < 0.95,
    "mets_now": lambda v: v >= 2,
    "cyp2c9_activity": lambda v: v < 2,
    "twin_carbs_absorbing": lambda v: v < 100,
    "twin_fasting_factor": lambda v: v < 0.97,
    "hist_lows_14d": lambda v: v >= 1,
    "hist_lows_7d": lambda v: v >= 1,
    "hist_tbr_14d": lambda v: v > 0,
    "hist_tbr_7d": lambda v: v > 0,
    "minutes_since_last_meal": lambda v: v >= 180,
    "steps_last_60": lambda v: v >= 500,
    "steps_last_30": lambda v: v >= 300,
}
for _flag in (
    "takes_insulin",
    "takes_premixed",
    "takes_basal",
    "takes_sulfonylurea",
    "hypo_history",
    "hypo_unaware",
    "beta_blocker",
):
    FITS[_flag] = lambda v: v >= 1


def sentence(feature: str, value: float) -> tuple[str, str] | None:
    """Turn one feature and its value into an English and a Hindi sentence."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if feature in FITS and not FITS[feature](value):
        return None
    if feature.startswith("cgm_change_"):
        window = feature.rsplit("_", 1)[1]
        direction = "falling" if value < 0 else "rising"
        en, hi = CHANGE_TEMPLATES[direction]
        return (
            en.format(value=_int(abs(value)), window=window),
            hi.format(value=_int(abs(value)), window=window),
        )
    if feature == "cgm_slope_30":
        direction = "falling" if value < 0 else "rising"
        en, hi = SLOPE_TEMPLATES[direction]
        return en.format(value=_int(abs(value) * 10)), hi.format(value=_int(abs(value) * 10))
    if feature not in TEMPLATES:
        return None
    en, hi = TEMPLATES[feature]
    values = {
        "value": _int(value),
        "hours": _hours(value),
        "percent": f"{value * 100:.1f}",
        "decimal": f"{value:g}",
    }
    return en.format(**values), hi.format(**values)


def explain(model: TrainedModel, row: pd.DataFrame, count: int = 3) -> list[dict]:
    """The main reasons that raised the estimated chance for one time point."""
    import shap

    explainer = shap.TreeExplainer(model.model.booster_)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # A notice about the output format of SHAP
        values = np.asarray(explainer.shap_values(row[model.features]))
    if values.ndim == 3:
        values = values[1]
    contributions = values.reshape(-1)
    order = np.argsort(-contributions)
    reasons, used_groups = [], set()
    for i in order:
        if contributions[i] <= 0 or len(reasons) >= count:
            break
        feature = model.features[i]
        group = next((g for g, members in SIMILAR.items() if feature in members), feature)
        if group in used_groups:
            continue  # Similar reasons repeat the same message, so only the strongest one shows.
        text = sentence(feature, float(row[feature].iloc[0]))
        if text is None:
            continue
        used_groups.add(group)
        reasons.append(
            {
                "feature": feature,
                "contribution": round(float(contributions[i]), 4),
                "en": text[0],
                "hi": text[1],
            }
        )
    if not reasons:
        reasons.append({"feature": None, "contribution": 0.0, "en": GENERIC[0], "hi": GENERIC[1]})
    return reasons

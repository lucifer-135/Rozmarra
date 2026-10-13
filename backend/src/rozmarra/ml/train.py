"""Training of the LightGBM models (docs/techstack.md, Section 7.2).

- One binary LightGBM classifier for each target, with 300 trees and a learning rate of
  0.05, as in the technical design. The technical design starts with 31 leaves. A
  comparison on the validation patients of the training group (never the test group)
  showed better results with stronger regularisation: 15 leaves, at least 200 time points
  in each leaf, 60% of the features for each tree and an L2 penalty of 5.
- The training patients are split 80/20 by patient. The model learns on the 80% part.
  Isotonic regression calibrates the probabilities on the 20% part.
- Two alert thresholds come from the calibrated probabilities on the 20% part: the first
  detects 80% of the positive time points, and the second is the point where sensitivity
  equals specificity.
- Risk words: an estimated chance below 20% is Low, 20% to 50% is Moderate, and above
  50% is High. A clinical expert should review these thresholds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from rozmarra.config import MODELS_DIR, RANDOM_SEED
from rozmarra.ml.alerts import threshold_for_events

LGB_SETTINGS = dict(
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=15,
    min_child_samples=200,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.6,
    reg_lambda=5.0,
    random_state=RANDOM_SEED,
    verbose=-1,
    n_jobs=4,
)
VALIDATION_SHARE = 0.2
TARGET_SENSITIVITY = 0.8
RISK_WORDS = ((0.2, "Low"), (0.5, "Moderate"), (1.01, "High"))


def risk_word(chance: float) -> str:
    return next(word for limit, word in RISK_WORDS if chance < limit)


def alert_risk_word(chance: float, alert_threshold: float) -> str:
    """Risk words for the 60-minute alert, tied to the alert level.

    Low blood sugar within the next 60 minutes is rare, so the alert level is a small chance
    (about 3.5%). With the general words, an alert could show the word "Low", which would
    confuse a doctor. For the alert, the words are therefore: below the alert level, Low;
    from the alert level to 20%, Moderate; and 20% or more, High. A clinical expert should
    review these words.
    """
    if chance < alert_threshold:
        return "Low"
    return "Moderate" if chance < 0.2 else "High"


def split_patients(
    patients: pd.Series, share: float = VALIDATION_SHARE, seed: int = RANDOM_SEED
) -> tuple[np.ndarray, np.ndarray]:
    """Return masks for the fitting part and the validation part, split by patient."""
    unique = np.array(sorted(patients.unique()))
    rng = np.random.default_rng(seed)
    validation = set(
        rng.choice(unique, size=max(1, int(round(share * len(unique)))), replace=False)
    )
    is_validation = patients.isin(validation).to_numpy()
    return ~is_validation, is_validation


def threshold_for_sensitivity(y: np.ndarray, p: np.ndarray, target: float) -> float:
    positives = np.sort(p[y == 1])
    if len(positives) == 0:
        return 0.5
    index = int(np.floor((1 - target) * len(positives)))
    return float(positives[min(index, len(positives) - 1)])


def threshold_balanced(y: np.ndarray, p: np.ndarray) -> float:
    """The threshold where sensitivity is closest to specificity."""
    candidates = np.unique(np.quantile(p, np.linspace(0.5, 0.9999, 400)))
    best, gap = 0.5, np.inf
    pos, neg = y == 1, y == 0
    for t in candidates:
        sensitivity = np.mean(p[pos] >= t) if pos.any() else 0
        specificity = np.mean(p[neg] < t) if neg.any() else 0
        if abs(sensitivity - specificity) < gap:
            best, gap = float(t), abs(sensitivity - specificity)
    return best


@dataclass
class TrainedModel:
    target: str
    features: list[str]
    model: lgb.LGBMClassifier
    calibration_x: list[float]
    calibration_y: list[float]
    threshold_sensitivity: float
    threshold_balanced: float
    info: dict = field(default_factory=dict)

    def raw(self, table: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(table[self.features])[:, 1]

    def predict(self, table: pd.DataFrame) -> np.ndarray:
        """The calibrated estimated chance of the event.

        Isotonic calibration is a step function, so many time points would share exactly the
        same chance, and these ties would hide the ranking of the model. One millionth of the
        raw score breaks the ties. It changes each chance by at most 0.000001.
        """
        raw = self.raw(table)
        calibrated = np.interp(raw, self.calibration_x, self.calibration_y)
        return np.clip(calibrated + 1e-6 * raw, 0.0, 1.0)

    def save(self, folder: Path = MODELS_DIR) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        self.model.booster_.save_model(str(folder / f"{self.target}.txt"))
        meta = {
            "target": self.target,
            "features": self.features,
            "calibration_x": self.calibration_x,
            "calibration_y": self.calibration_y,
            "threshold_sensitivity": self.threshold_sensitivity,
            "threshold_balanced": self.threshold_balanced,
            "info": self.info,
        }
        path = folder / f"{self.target}.json"
        path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return path

    @classmethod
    def load(cls, target: str, folder: Path = MODELS_DIR) -> TrainedModel:
        meta = json.loads((folder / f"{target}.json").read_text(encoding="utf-8"))
        booster = lgb.Booster(model_file=str(folder / f"{target}.txt"))
        return cls(
            target,
            meta["features"],
            _BoosterWrapper(booster),
            meta["calibration_x"],
            meta["calibration_y"],
            meta["threshold_sensitivity"],
            meta["threshold_balanced"],
            meta.get("info", {}),
        )


class _BoosterWrapper:
    """Gives a saved booster the predict_proba method of a trained classifier."""

    def __init__(self, booster: lgb.Booster):
        self.booster_ = booster

    def predict_proba(self, X):
        p = self.booster_.predict(X)
        return np.column_stack([1 - p, p])


def fit_model(
    train: pd.DataFrame,
    features: list[str],
    label: str,
    target: str,
    patient_column: str = "patient_id",
    seed: int = RANDOM_SEED,
    event_step=None,
) -> TrainedModel:
    """Train, calibrate and choose the alert levels on the validation patients.

    When event_step is given (the minutes between time points, for all rows or for each row),
    alert level A is the highest level that detects at least 80% of the events of the
    validation patients (ml/alerts.py). Otherwise, it is the level that flags 80% of the
    positive time points.
    """
    fit_mask, validation_mask = split_patients(train[patient_column], seed=seed)
    fitting, validation = train[fit_mask], train[validation_mask]
    model = lgb.LGBMClassifier(**LGB_SETTINGS)
    model.fit(fitting[features], fitting[label].astype(int))
    raw = model.predict_proba(validation[features])[:, 1]
    y = validation[label].astype(int).to_numpy()
    isotonic = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    isotonic.fit(raw, y)
    calibration_x = list(map(float, isotonic.X_thresholds_))
    calibration_y = list(map(float, isotonic.y_thresholds_))
    p = np.interp(raw, calibration_x, calibration_y)
    point_threshold = threshold_for_sensitivity(y, p, TARGET_SENSITIVITY)
    threshold_a, rule = point_threshold, "80% of the positive time points"
    if event_step is not None:
        step = event_step[validation_mask] if np.ndim(event_step) else event_step
        # The same tie-break as predict(), so that the level matches the predicted chances.
        chosen = threshold_for_events(validation, y, p + 1e-6 * raw, step)
        if chosen is not None:
            threshold_a, rule = chosen, "80% of the events"
    return TrainedModel(
        target=target,
        features=features,
        model=model,
        calibration_x=calibration_x,
        calibration_y=calibration_y,
        threshold_sensitivity=threshold_a,
        threshold_balanced=threshold_balanced(y, p),
        info={
            "alert_level_rule": f"The highest level that detects {rule} of the validation set",
            "point_threshold_80": round(point_threshold, 4),
            "fitting_rows": int(len(fitting)),
            "validation_rows": int(len(validation)),
            "fitting_positives": int(fitting[label].sum()),
            "validation_positives": int(y.sum()),
            "settings": {k: v for k, v in LGB_SETTINGS.items() if k != "verbose"},
        },
    )

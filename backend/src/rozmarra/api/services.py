"""The calculations behind the API: plan simulations and the replay of a fasting day."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from rozmarra.api.store import STORE
from rozmarra.fasting.plan import FastingPlan
from rozmarra.formatting import clock_12h, long_date
from rozmarra.medicines import get_medicine
from rozmarra.ml.datasets import record_features, synthetic_series
from rozmarra.ml.episodes import history_features, plan_features, twin_outcomes
from rozmarra.ml.explain import explain
from rozmarra.ml.features import TwinForecaster, point_features
from rozmarra.ml.labels import COMPLETENESS, completeness
from rozmarra.ml.train import alert_risk_word, risk_word
from rozmarra.risk.idf_dar import NOTE_OTHER_FASTS, calculate
from rozmarra.risk.rules import dehydration_caution
from rozmarra.twin.simulate import simulate_plan
from rozmarra.twin.virtual_patients import demo_twin

CURVE_STEP = 5
NOT_ENOUGH_DATA = (
    "There is not enough recent CGM data to make a prediction. Please check that "
    "the sensor is working."
)
SYNTHETIC_NOTE = "Synthetic data. This patient does not represent a real person."
REPEAT_RISE = 0.1  # An alert repeats within 30 minutes only if the chance rises by 10 points.


def _round(values) -> list[float | None]:
    return [None if not math.isfinite(v) else round(float(v), 1) for v in values]


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="minutes")


def chance(value: float) -> dict:
    return {
        "value": round(float(value), 3),
        "percent": int(round(100 * value)),
        "word": risk_word(value),
    }


def plan_markers(plan: FastingPlan) -> dict:
    return {
        "fast": {
            "start": _iso(plan.fast_start),
            "end": _iso(plan.fast_end),
            "water_allowed": plan.water_allowed,
            "hours": round(plan.fast_hours, 1),
        },
        "meals": [
            {
                "time": _iso(m.time),
                "label": m.label,
                "label_hi": m.label_hi,
                "carbs_g": m.carbs_g,
                "food_category": m.food_category.value,
                "breaks_fast": m.breaks_fast,
            }
            for m in plan.meals
        ],
        "medicines": [
            {
                "time": _iso(d.time),
                "name": d.name,
                "display_name": get_medicine(d.name).display_name,
                "display_name_hi": get_medicine(d.name).display_name_hi,
                "dose": d.dose,
                "unit": get_medicine(d.name).unit,
                "usual_dose": d.usual_dose,
                "changed": d.is_changed,
            }
            for d in plan.medicines
        ],
        "activities": [
            {"start": _iso(a.start), "end": _iso(a.end), "label": a.label, "mets": a.mets}
            for a in plan.activities
        ],
    }


@lru_cache(maxsize=8)
def _history(patient_id: str) -> dict:
    """CGM history from the 14 days of the demo history before the planned fast."""
    days = STORE.fasting_days
    cgm = days["timeseries"]
    cgm = cgm[(cgm.patient_id == patient_id) & (cgm.signal == "glucose_cgm")]
    fast = days["events"]
    fast = fast[(fast.patient_id == patient_id) & (fast.event_type == "fast")].iloc[0]
    start = cgm.timestamp_local.min()
    minutes = ((cgm.timestamp_local - start) / pd.Timedelta(minutes=1)).to_numpy()
    at = (fast.start - start) / pd.Timedelta(minutes=1)
    return history_features(minutes, cgm.value.to_numpy(), at)


MAX_WINDOW_HOURS = 60


def plan_problems(plan: FastingPlan) -> list[str]:
    """Problems that stop Rozmarra from simulating a plan, written for the doctor."""
    problems = []
    if plan.fast_end <= plan.fast_start:
        problems.append("The end of the fast must be later than the start of the fast.")
    elif (plan.window_end - plan.window_start) / timedelta(hours=1) > MAX_WINDOW_HOURS:
        problems.append(
            f"The plan covers more than {MAX_WINDOW_HOURS} hours. Please check the dates of "
            "the fast and the meals."
        )
    for dose in plan.medicines:
        try:
            medicine = get_medicine(dose.name)
        except KeyError:
            problems.append(f'Rozmarra does not know the medicine "{dose.name}".')
            continue
        if dose.dose > medicine.max_single_dose:
            problems.append(
                f"The dose of {medicine.display_name} ({dose.dose:g} {medicine.unit}) is above "
                f"the largest single dose that Rozmarra accepts "
                f"({medicine.max_single_dose:g} {medicine.unit})."
            )
    for activity in plan.activities:
        if activity.end <= activity.start:
            problems.append(f'The activity "{activity.label}" must end after it starts.')
    return problems


def simulate(patient_id: str, plan: FastingPlan, samples: int = 100) -> dict:
    record = STORE.record(patient_id)
    profile = STORE.profile(patient_id)
    simulation = simulate_plan(
        plan,
        profile,
        record.usual_doses(),
        samples=samples,
        average=STORE.average_profile(patient_id),
        keep_curves=True,
    )
    outcomes = twin_outcomes(simulation, plan)
    values = record_features(record, plan.date)
    table = pd.DataFrame([{**outcomes, **_history(patient_id), **plan_features(plan, values)}])
    models = STORE.episode_models
    low = (
        float(models["f1_low"].predict(table)[0])
        if "f1_low" in models
        else outcomes["twin_low_share"]
    )
    high = None
    if plan.breaking_meal is not None:
        high = (
            float(models["f1_high"].predict(table)[0])
            if "f1_high" in models
            else outcomes.get("twin_high_share")
        )
    lowest_minute = outcomes["twin_lowest_minute"]
    lowest_time = simulation.time_at(lowest_minute) if lowest_minute is not None else None
    caution = dehydration_caution(
        plan.water_allowed,
        plan.fast_hours,
        [d.name for d in plan.medicines] + [m.name for m in record.medicines],
        record.egfr,
        record.age_on(plan.date),
    )
    score = calculate(record.idf_dar_inputs(plan.date, plan))
    steps = range(0, simulation.minutes + 1, CURVE_STEP)
    return {
        "patient_id": patient_id,
        "source": "synthetic",
        "plan": plan.model_dump(mode="json"),
        "curve": {
            "times": [_iso(simulation.time_at(m)) for m in steps],
            "p10": _round(simulation.p10[::CURVE_STEP]),
            "p50": _round(simulation.p50[::CURVE_STEP]),
            "p90": _round(simulation.p90[::CURVE_STEP]),
            "most_likely": _round(simulation.point[::CURVE_STEP]),
            "average_patient": _round(simulation.average[::CURVE_STEP])
            if simulation.average is not None
            else None,
            "samples": samples,
        },
        "markers": plan_markers(plan),
        "summary": {
            "chance_of_low_during_fast": chance(low),
            "lowest_glucose_mg_dl": round(outcomes["twin_lowest_p50"], 0),
            "lowest_glucose_time": _iso(lowest_time) if lowest_time else None,
            "lowest_glucose_time_text": clock_12h(lowest_time.time()) if lowest_time else None,
            "expected_minutes_below_70": round(outcomes["twin_minutes_below_70"]),
            "chance_of_high_after_fast": chance(high) if high is not None else None,
        },
        "dehydration_caution": None
        if caution is None
        else {"title": caution.title, "message": caution.message, "reasons": list(caution.reasons)},
        "idf_dar": {"total": score.total, "category": score.category.value},
        "notes": [SYNTHETIC_NOTE] + ([] if plan.fast_type == "ramadan" else [NOTE_OTHER_FASTS]),
    }


# --- Replay of a recorded fasting day ----------------------------------------------------


class Replay:
    """The live fasting monitor for one demo patient, computed once and then cached."""

    def __init__(self, patient_id: str):
        days = STORE.fasting_days
        record = STORE.record(patient_id)
        fast = STORE.fast(patient_id)
        self.twin = demo_twin(record, STORE.fitted_twins, fast.date)
        series = days["timeseries"][days["timeseries"].patient_id == patient_id]
        events = days["events"][days["events"].patient_id == patient_id]
        patient = days["virtual_patients"].set_index("patient_id").loc[patient_id]
        self.ps = synthetic_series(self.twin, series, events, patient)
        self.series = series
        window = self.ps.fasts[0]
        self.window = window
        first = int(np.ceil(window.start / 5) * 5)
        self.points = np.arange(first, window.end + 1, 5)
        self.forecaster = TwinForecaster(self.ps)
        self.features = point_features(self.ps, self.points, self.forecaster)
        self.model = STORE.point_models["e1"]
        self.chances = self.model.predict(self.features)
        # A prediction needs a current CGM reading and 70% of the readings in the last 2 hours,
        # the same rules as the labels in training.
        has_current = np.isfinite(self.features["cgm_now"].to_numpy())
        self.enough = has_current & np.array(
            [completeness(self.ps.cgm_minutes, t - 120, t, 5) >= COMPLETENESS for t in self.points]
        )
        self.alerts = self._alerts()

    def _alerts(self) -> list[int]:
        alerts, last_minute, last_chance = [], -np.inf, 0.0
        threshold = self.model.threshold_sensitivity
        for i, t in enumerate(self.points):
            p = self.chances[i]
            if not self.enough[i] or p < threshold:
                continue
            if t - last_minute >= 30 or p >= last_chance + REPEAT_RISE:
                alerts.append(i)
                last_minute, last_chance = t, p
        return alerts

    def time(self, minute: float) -> datetime:
        return (self.ps.start + pd.Timedelta(minutes=float(minute))).to_pydatetime()

    def overview(self) -> dict:
        return {
            "fast_start": _iso(self.time(self.window.start)),
            "fast_end": _iso(self.time(self.window.end)),
            "times": [_iso(self.time(t)) for t in self.points],
            "chances": [round(float(p), 3) for p in self.chances],
            "enough_data": self.enough.tolist(),
            "alert_threshold": round(self.model.threshold_sensitivity, 3),
            "alerts": [self._alert_payload(i) for i in self.alerts],
        }

    def alert_chance(self, value: float) -> dict:
        word = alert_risk_word(value, self.model.threshold_sensitivity)
        return {**chance(value), "word": word}

    def _alert_payload(self, i: int) -> dict:
        return {
            "time": _iso(self.time(self.points[i])),
            "chance": self.alert_chance(self.chances[i]),
        }

    def _signal(self, name: str, until: datetime, hours: int = 12) -> dict:
        rows = self.series[
            (self.series.signal == name)
            & (self.series.timestamp_local <= until)
            & (self.series.timestamp_local > until - timedelta(hours=hours))
        ]
        return {
            "times": [_iso(t) for t in rows.timestamp_local],
            "values": _round(rows.value.to_numpy()),
        }

    def at(self, moment: datetime) -> dict:
        minute = (pd.Timestamp(moment) - self.ps.start) / pd.Timedelta(minutes=1)
        i = int(
            np.clip(np.searchsorted(self.points, minute, side="right") - 1, 0, len(self.points) - 1)
        )
        t = self.points[i]
        now = self.time(t)
        row = self.features.iloc[[i]]
        result = {
            "patient_id": self.ps.patient_id,
            "source": "synthetic",
            "time": _iso(now),
            "time_text": f"{clock_12h(now.time())} on {long_date(now.date())}",
            "enough_data": bool(self.enough[i]),
            "glucose": self._signal("glucose_cgm", now),
            "heart_rate": self._signal("heart_rate", now),
            "hrv_rmssd": self._signal("hrv_rmssd", now),
            "steps": self._signal("steps", now),
            "alerts_so_far": [self._alert_payload(j) for j in self.alerts if self.points[j] <= t],
        }
        if not self.enough[i]:
            result["message"] = NOT_ENOUGH_DATA
            return result
        p = float(self.chances[i])
        glucose = float(row.cgm_now.iloc[0])
        G = self.forecaster.run(
            np.array([t]),
            np.array([glucose]),
            np.array([float(row.cgm_slope_30.fillna(0).iloc[0])]),
            120,
        )[0]
        p50 = np.percentile(G, 50, axis=0)
        lowest = int(np.argmin(p50))
        result.update(
            {
                "chance_of_low_next_60_min": self.alert_chance(p),
                "alert": i in self.alerts,
                "above_alert_threshold": p >= self.model.threshold_sensitivity,
                "forecast": {
                    "times": [_iso(now + timedelta(minutes=m)) for m in range(0, 121, 5)],
                    "p10": _round(np.percentile(G, 10, axis=0)[::5]),
                    "p50": _round(p50[::5]),
                    "p90": _round(np.percentile(G, 90, axis=0)[::5]),
                },
                "predicted_lowest_mg_dl": round(float(p50[lowest])),
                "predicted_lowest_time": _iso(now + timedelta(minutes=lowest)),
                "predicted_lowest_time_text": clock_12h((now + timedelta(minutes=lowest)).time()),
                "reasons": explain(self.model, row) if p >= 0.2 or i in self.alerts else [],
            }
        )
        return result


@lru_cache(maxsize=8)
def replay(patient_id: str) -> Replay:
    return Replay(patient_id)


def daily_history(patient_id: str, days: int = 14) -> dict:
    """A summary of each of the last days before the planned fast, for the virtual patient page.

    Sleep is counted for the night that ends on the morning of each day.
    """
    fast = STORE.fast(patient_id)
    series = STORE.fasting_days["timeseries"]
    series = series[series.patient_id == patient_id]
    first = fast.date - timedelta(days=days)
    stamps = series.timestamp_local
    day_of = stamps.dt.date
    night_of = (stamps + pd.Timedelta(hours=12)).dt.date

    def signal(name: str) -> pd.DataFrame:
        return series[series.signal == name]

    glucose, steps = signal("glucose_cgm"), signal("steps")
    heart, sleep = signal("heart_rate"), signal("sleep_stage")
    rows = []
    for offset in range(days):
        day = first + timedelta(days=offset)
        g = glucose.value[day_of[glucose.index] == day].to_numpy()
        s = steps.value[day_of[steps.index] == day].to_numpy()
        h = heart.value[day_of[heart.index] == day].to_numpy()
        asleep = sleep.value[(night_of[sleep.index] == day) & (sleep.value >= 1)]
        rows.append(
            {
                "date": day.isoformat(),
                "date_text": long_date(day),
                "glucose_readings": int(len(g)),
                "mean_glucose_mg_dl": round(float(g.mean()), 0) if len(g) else None,
                "lowest_glucose_mg_dl": round(float(g.min()), 0) if len(g) else None,
                "time_in_range_percent": round(100 * float(((g >= 70) & (g <= 180)).mean()), 0)
                if len(g)
                else None,
                "time_below_70_percent": round(100 * float((g < 70).mean()), 1) if len(g) else None,
                "steps": int(s.sum()) if len(s) else None,
                "mean_heart_rate": round(float(h.mean()), 0) if len(h) else None,
                "sleep_hours": round(len(asleep) * 5 / 60, 1),
            }
        )
    window = glucose[(day_of[glucose.index] >= first) & (day_of[glucose.index] < fast.date)]
    values = window.value.to_numpy()
    with_steps = [r["steps"] for r in rows if r["steps"] is not None]
    return {
        "patient_id": patient_id,
        "source": "synthetic",
        "start": datetime.combine(first, datetime.min.time()).isoformat(timespec="minutes"),
        "end": datetime.combine(fast.date, datetime.min.time()).isoformat(timespec="minutes"),
        "days": rows,
        "summary": {
            "days": days,
            "mean_glucose_mg_dl": round(float(values.mean()), 0) if len(values) else None,
            "time_in_range_percent": round(
                100 * float(((values >= 70) & (values <= 180)).mean()), 0
            )
            if len(values)
            else None,
            "time_below_70_percent": round(100 * float((values < 70).mean()), 1)
            if len(values)
            else None,
            "mean_daily_steps": round(float(np.mean(with_steps)), -1) if with_steps else None,
            "mean_sleep_hours": round(float(np.mean([r["sleep_hours"] for r in rows])), 1),
        },
    }


@lru_cache(maxsize=8)
def default_summary(patient_id: str) -> dict:
    """The simulation of the usual plan (Plan A), used by the patient list."""
    return simulate(patient_id, STORE.default_plan(patient_id), samples=50)["summary"]

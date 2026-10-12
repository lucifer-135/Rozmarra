"""The synthetic cohort: virtual patients with normal days and fasting days (FR-A3).

Each virtual patient has one timeline (docs/techstack.md, Section 6.2):
- 7 to 14 normal days with a usual Indian meal routine and the usual medicines;
- then three fasting episodes, with two normal days between them. The episodes come from
  the fasts that the patient keeps, and other fasting patterns fill the remaining places,
  so that every pattern has enough data;
- on some fasting days, a doctor's plan B lowers the sulfonylurea or insulin dose, so that
  the data shows how dose changes affect risk.

The "true" twin generates the glucose. The generated data also contains things that the
prediction twin will not know: meal times and portions that vary, logged carbohydrates
that differ from the real amount, unrecorded snacks, a slowly varying disturbance of
glucose, CGM sensor delay and noise, and gaps in the data. Every one of these settings is
an assumption, and the data card lists them.

Every record, signal and label in the cohort is synthetic.
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from rozmarra.config import PROCESSED_DIR, RANDOM_SEED, REPORTS_DIR
from rozmarra.ehr.generator import generate_records
from rozmarra.ehr.records import PatientRecord
from rozmarra.ehr.store import write_bundles
from rozmarra.fasting.calendar import sun_times
from rozmarra.fasting.meals import FoodCategory
from rozmarra.fasting.plan import FastingPlan
from rozmarra.fasting.templates import TEMPLATES, build_plan
from rozmarra.medicines import MedicineClass, get_medicine
from rozmarra.ml.labels import breaking_meal_labels, point_labels
from rozmarra.risk.idf_dar import Hypoglycaemia
from rozmarra.synth import wearables
from rozmarra.twin.medicines import Dose, Meal
from rozmarra.twin.model import Forcing, Parameters, calibrate_production, steady_start
from rozmarra.twin.profiles import load_twins
from rozmarra.twin.simulate import USUAL_MEALS, build_forcing, morning_inputs
from rozmarra.twin.solver import integrate
from rozmarra.twin.virtual_patients import (
    VirtualTwin,
    demo_twin,
    held_out_twins,
    training_twins,
    virtual_twin,
)

TIMEZONE = "Asia/Kolkata"
DATASET = "Rozmarra synthetic"
DEVICE = "simulated"
SOURCE = "synthetic"
OUT_DIR = PROCESSED_DIR / "synthetic"

TEST_SHARE = 0.2
EPISODES = 3
HISTORY_DAYS = (7, 14)
GAP_DAYS = 2
MEAL_TIME_SD_MIN = 15.0
PORTION_LOG_SD = 0.25
LOGGED_CARBS_LOG_SD = 0.2
SNACK_PROBABILITY = 0.3
SNACK_CARBS_G = 15.0
# A slowly varying disturbance of glucose stands for everything that the twin does not
# model, such as stress or food that nobody recorded. It moves glucose by about 15 to
# 20 mg/dL, which is smaller than the twin's error on real data (about 30 mg/dL).
DISTURBANCE_SD = 0.35  # mg/dL per minute
DISTURBANCE_TAU_MIN = 60.0
PLAN_CHANGE_PROBABILITY = 0.35
CHUNK = 40
DAY = 1440

FAST_TEMPLATE_IDS = [t.id for t in TEMPLATES]


@dataclass
class Episode:
    number: int
    plan: FastingPlan
    medicine_changed: bool


@dataclass
class Timeline:
    twin: VirtualTwin
    group: str
    start: datetime
    minutes: int
    meals: list[Meal]
    logged_meals: list[dict]
    doses: list[Dose]
    dose_events: list[dict]
    activities: list[tuple[int, int, float, str]]
    sleep_windows: list[tuple[int, int]]
    episodes: list[Episode]
    seed: int
    signals: wearables.SignalProfile | None = None
    extra: dict = field(default_factory=dict)

    def minute(self, moment: datetime) -> float:
        return (moment - self.start) / timedelta(minutes=1)


# --- Building one timeline ---------------------------------------------------------------


def _is_secretagogue(name: str) -> bool:
    return get_medicine(name).medicine_class in {MedicineClass.SULFONYLUREA, MedicineClass.GLINIDE}


def _vary_plan(plan: FastingPlan, rng: np.random.Generator, change_medicines: bool):
    for meal in plan.meals:
        meal.time = meal.time + timedelta(minutes=float(rng.normal(0, MEAL_TIME_SD_MIN)))
        spread = 0.3 if meal.breaks_fast else PORTION_LOG_SD
        meal.carbs_g = round(float(meal.carbs_g * rng.lognormal(0, spread)), 1)
    plan.meals.sort(key=lambda m: m.time)
    changed = False
    if change_medicines:
        kept = []
        for dose in plan.medicines:
            medicine = get_medicine(dose.name)
            inside = plan.fast_start - timedelta(hours=3) <= dose.time <= plan.fast_end
            if inside and _is_secretagogue(dose.name):
                changed = True
                if rng.random() < 0.2:
                    continue  # The doctor omits the dose on the day of the fast.
                dose.dose = dose.dose / 2
            elif inside and medicine.medicine_class is MedicineClass.PREMIXED_INSULIN:
                dose.dose, changed = round(dose.dose * 0.7), True
            elif inside and medicine.medicine_class is MedicineClass.BASAL_INSULIN:
                dose.dose, changed = round(dose.dose * 0.8), True
            kept.append(dose)
        plan.medicines = kept
    return changed


def _episode_templates(record: PatientRecord, rng: np.random.Generator) -> list[str]:
    chosen = list(rng.permutation(record.fasts_kept))[:EPISODES]
    others = [t for t in FAST_TEMPLATE_IDS if t != "custom"]
    while len(chosen) < EPISODES:
        chosen.append(str(rng.choice(others)))
    return [str(t) for t in chosen]


def _sleep_windows(
    start: datetime, days: int, plans: list[FastingPlan], city: str, rng: np.random.Generator
) -> list[tuple[int, int]]:
    by_date = {p.date: p for p in plans}
    windows = []
    for d in range(-1, days + 1):
        evening = (start + timedelta(days=d)).date()
        tomorrow = evening + timedelta(days=1)
        base = datetime.combine(evening, time(22, 30)) + timedelta(minutes=float(rng.normal(0, 30)))
        wake = datetime.combine(tomorrow, time(6, 0)) + timedelta(minutes=float(rng.normal(0, 30)))
        plan = by_date.get(tomorrow)
        today = by_date.get(evening)
        if today is not None and any("Garba" in a.label for a in today.activities):
            base = datetime.combine(tomorrow, time(0, 0))
        if plan is not None and plan.fast_type == "ramadan":
            dawn = sun_times(tomorrow, city).dawn
            pieces = [
                (base, dawn - timedelta(minutes=50)),
                (dawn + timedelta(minutes=30), datetime.combine(tomorrow, time(7, 30))),
            ]
        elif plan is not None and plan.fast_type == "karva_chauth":
            pieces = [
                (base, datetime.combine(tomorrow, time(4, 10))),
                (datetime.combine(tomorrow, time(5, 0)), datetime.combine(tomorrow, time(6, 30))),
            ]
        else:
            pieces = [(base, wake)]
        for a, b in pieces:
            windows.append(
                (int((a - start) / timedelta(minutes=1)), int((b - start) / timedelta(minutes=1)))
            )
    return windows


def build_timeline(
    twin: VirtualTwin,
    group: str,
    seed: int,
    templates: list[str] | None = None,
    fast_dates: list[date] | None = None,
    history_days: int | None = None,
    vary: bool = True,
    allow_plan_change: bool = True,
) -> Timeline:
    rng = np.random.default_rng(seed)
    record = twin.record
    history = history_days or int(rng.integers(HISTORY_DAYS[0], HISTORY_DAYS[1] + 1))
    templates = templates or _episode_templates(record, rng)
    if fast_dates:
        start_date = fast_dates[0] - timedelta(days=history + 1)
    else:
        start_date = date(2026, 1, 5) + timedelta(days=int(rng.integers(0, 300)))
    start = datetime.combine(start_date, time(0, 0))
    usual = record.usual_doses()
    on_risky_medicine = any(
        _is_secretagogue(u.name) or get_medicine(u.name).is_insulin for u in usual
    )

    episodes: list[Episode] = []
    next_date = start_date + timedelta(days=history + 1)
    for number, template_id in enumerate(templates):
        fast_date = fast_dates[number] if fast_dates else next_date
        plan = build_plan(template_id, record.patient_id, fast_date, record.city, usual)
        change = (
            vary
            and allow_plan_change
            and on_risky_medicine
            and rng.random() < PLAN_CHANGE_PROBABILITY
        )
        changed = _vary_plan(plan, rng, change) if vary else False
        episodes.append(Episode(number, plan, changed))
        next_date = plan.window_end.date() + timedelta(days=GAP_DAYS + 1)
    end = datetime.combine(episodes[-1].plan.window_end.date() + timedelta(days=2), time(0, 0))
    minutes = int((end - start) / timedelta(minutes=1))
    windows = [(e.plan.window_start, e.plan.window_end) for e in episodes]

    def in_window(moment: datetime) -> Episode | None:
        for episode, (a, b) in zip(episodes, windows, strict=True):
            if a <= moment <= b:
                return episode
        return None

    def minute(moment: datetime) -> float:
        return (moment - start) / timedelta(minutes=1)

    meals, logged = [], []
    day = start_date - timedelta(days=1)
    while day < end.date():
        for clock, carbs, category in USUAL_MEALS:
            moment = datetime.combine(day, clock)
            if vary:
                moment += timedelta(minutes=float(rng.normal(0, MEAL_TIME_SD_MIN)))
                carbs = float(carbs * rng.lognormal(0, PORTION_LOG_SD))
            if in_window(moment) is None:
                meals.append(Meal(minute(moment), carbs, category))
                logged.append(
                    {
                        "time": moment,
                        "carbs_actual": carbs,
                        "category": category,
                        "label": "Usual meal",
                        "breaks_fast": False,
                        "episode": None,
                    }
                )
        if vary and rng.random() < SNACK_PROBABILITY:
            moment = datetime.combine(day, time(16, 0)) + timedelta(
                minutes=float(rng.uniform(0, 90))
            )
            if in_window(moment) is None:
                # An unrecorded snack: it changes glucose but does not appear in the events.
                meals.append(Meal(minute(moment), SNACK_CARBS_G, FoodCategory.FAST_ABSORBING))
        day += timedelta(days=1)
    for episode in episodes:
        for meal in episode.plan.meals:
            meals.append(Meal(minute(meal.time), meal.carbs_g, meal.food_category))
            logged.append(
                {
                    "time": meal.time,
                    "carbs_actual": meal.carbs_g,
                    "category": meal.food_category,
                    "label": meal.label,
                    "breaks_fast": meal.breaks_fast,
                    "episode": episode.number,
                }
            )

    doses, dose_events = [], []
    day = start_date - timedelta(days=2)
    while day < end.date():
        for u in usual:
            moment = datetime.combine(day, u.time)
            if in_window(moment) is None:
                doses.append(Dose(minute(moment), u.name, u.dose))
                dose_events.append(
                    {
                        "time": moment,
                        "name": u.name,
                        "dose": u.dose,
                        "episode": None,
                        "changed": False,
                    }
                )
        day += timedelta(days=1)
    for episode in episodes:
        for d in episode.plan.medicines:
            doses.append(Dose(minute(d.time), d.name, d.dose))
            dose_events.append(
                {
                    "time": d.time,
                    "name": d.name,
                    "dose": d.dose,
                    "episode": episode.number,
                    "changed": d.is_changed,
                }
            )

    activities = [
        (int(minute(a.start)), int(minute(a.end)), a.mets, a.label)
        for e in episodes
        for a in e.plan.activities
    ]
    sleep = _sleep_windows(start, minutes // DAY, [e.plan for e in episodes], record.city, rng)
    return Timeline(
        twin,
        group,
        start,
        minutes,
        meals,
        logged,
        doses,
        dose_events,
        activities,
        sleep,
        episodes,
        seed,
    )


# --- Simulating a batch of timelines -----------------------------------------------------


def _pad(arrays: list[np.ndarray], length: int) -> np.ndarray:
    return np.stack([np.pad(a, (0, length - len(a)), mode="edge") for a in arrays])


def simulate_timelines(timelines: list[Timeline]) -> list[np.ndarray]:
    """Simulate the true glucose of each timeline, one value for each minute."""
    length = max(t.minutes for t in timelines)
    forcings, mets_all = [], []
    for t in timelines:
        rng = np.random.default_rng(t.seed + 1)
        asleep = np.zeros(t.minutes, dtype=bool)
        for a, b in t.sleep_windows:
            asleep[max(0, a) : max(0, min(t.minutes, b))] = True
        t.extra["asleep"] = asleep
        mets = wearables.activity_mets(
            t.minutes,
            t.twin.record.occupation,
            asleep,
            [(a, b, m) for a, b, m, _ in t.activities],
            rng,
        )
        t.extra["mets"] = mets
        values = t.twin.true_values
        f = build_forcing(
            t.meals,
            t.doses,
            t.minutes,
            t.twin.profile.body_weight,
            t.twin.profile.cyp_factor,
            mets,
            values["k_abs_factor"],
            values["meal_factor"],
        )
        disturbance = wearables._ar1(
            t.minutes, DISTURBANCE_SD, float(np.exp(-1 / DISTURBANCE_TAU_MIN)), rng
        )
        f.ra = f.ra[0] + disturbance
        forcings.append(f)
        mets_all.append(mets)
    stacked = Forcing(*(_pad([getattr(f, n) for f in forcings], length) for n in Forcing.FIELDS))
    profiles = [t.twin.profile for t in timelines]
    values = {
        n: np.array([t.twin.true_values[n] for t in timelines])
        for n in timelines[0].twin.true_values
    }
    p = Parameters(
        G_b=np.array([pr.G_b for pr in profiles]),
        I_b=np.array([pr.I_b for pr in profiles]),
        body_weight=np.array([pr.body_weight for pr in profiles]),
        renal_factor=np.array([min(pr.egfr / 90, 1) for pr in profiles]),
        cr_factor=np.array([pr.cr_factor for pr in profiles]),
        **values,
    )
    morning_minute = DAY + 7 * 60  # 7:00 am on the second normal day
    p = calibrate_production(p, morning_inputs(stacked, morning_minute))
    G = integrate(*steady_start(p, stacked.column(0)), p, stacked).G
    return [G[i, : t.minutes + 1] for i, t in enumerate(timelines)]


# --- Turning one simulated timeline into tables ------------------------------------------


def _rows(
    pid: str, start: datetime, minutes: np.ndarray, values: np.ndarray, signal: str, unit: str
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "patient_id": pid,
            "timestamp_local": pd.Timestamp(start) + pd.to_timedelta(minutes, unit="min"),
            "timezone": TIMEZONE,
            "signal": signal,
            "value": np.asarray(values, dtype=float),
            "unit": unit,
            "source": SOURCE,
            "dataset": DATASET,
            "device": DEVICE,
        }
    )


def _five_minute(values: np.ndarray, how: str = "mean") -> tuple[np.ndarray, np.ndarray]:
    usable = len(values) // 5 * 5
    blocks = values[:usable].reshape(-1, 5)
    out = blocks.mean(axis=1) if how == "mean" else blocks.sum(axis=1)
    return np.arange(0, usable, 5), out


def timeline_tables(t: Timeline, glucose: np.ndarray) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(t.seed + 2)
    record = t.twin.record
    pid = record.patient_id
    age = record.age_on(t.start.date())
    sp = wearables.signal_profile(
        record.resting_heart_rate,
        age,
        record.years_with_diabetes_on(t.start.date()),
        record.hypoglycaemia is Hypoglycaemia.UNAWARE,
        record.takes_beta_blocker,
        rng,
    )
    t.signals = sp
    asleep, mets = t.extra["asleep"], t.extra["mets"]

    thirst = np.zeros(t.minutes)
    for e in t.episodes:
        if not e.plan.water_allowed:
            a, b = int(t.minute(e.plan.fast_start)), int(t.minute(e.plan.fast_end))
            thirst[max(0, a) : min(t.minutes, b)] = np.arange(max(0, a), min(t.minutes, b)) - a
    thirst /= 60
    heart = wearables.heart_signals(glucose, mets, asleep, thirst, sp, rng)
    cgm_minutes, cgm_values = wearables.cgm_readings(glucose, sp, rng)
    steps = wearables.steps_per_minute(mets, asleep, rng)
    stages = wearables.sleep_stages(t.sleep_windows, t.minutes, rng)

    parts = [_rows(pid, t.start, cgm_minutes, cgm_values, "glucose_cgm", "mg/dL")]
    for values, signal, unit, how in (
        (heart.heart_rate, "heart_rate", "beats per minute", "mean"),
        (heart.rmssd, "hrv_rmssd", "ms", "mean"),
        (mets, "mets", "MET", "mean"),
        (steps, "steps", "steps", "sum"),
    ):
        m, v = _five_minute(values, how)
        parts.append(_rows(pid, t.start, m, np.round(v, 2), signal, unit))
    sampled = np.arange(0, t.minutes, 5)
    sleeping = stages[sampled] >= 0
    parts.append(
        _rows(
            pid, t.start, sampled[sleeping], stages[sampled][sleeping], "sleep_stage", "stage code"
        )
    )
    timeseries = pd.concat(parts, ignore_index=True)

    events = []
    log_rng = np.random.default_rng(t.seed + 3)
    for meal in t.logged_meals:
        logged = round(meal["carbs_actual"] * float(log_rng.lognormal(0, LOGGED_CARBS_LOG_SD)), 1)
        events.append(
            (
                pid,
                meal["time"],
                meal["time"],
                "meal",
                {
                    "label": meal["label"],
                    "carbs_g": logged,
                    "carbs_source": "logged by the patient",
                    "food_category": meal["category"].value,
                    "breaks_fast": meal["breaks_fast"],
                    "episode": meal["episode"],
                },
            )
        )
    for d in t.dose_events:
        medicine = get_medicine(d["name"])
        events.append(
            (
                pid,
                d["time"],
                d["time"],
                "insulin" if medicine.is_insulin else "medicine",
                {
                    "name": d["name"],
                    "dose": d["dose"],
                    "unit": medicine.unit,
                    "route": "subcutaneous" if medicine.is_insulin else "oral",
                    "episode": d["episode"],
                    "changed_by_plan": d["changed"],
                },
            )
        )
    for a, b, level, label in t.activities:
        events.append(
            (
                pid,
                t.start + timedelta(minutes=a),
                t.start + timedelta(minutes=b),
                "activity",
                {"label": label, "mets": level},
            )
        )
    for e in t.episodes:
        events.append(
            (
                pid,
                e.plan.fast_start,
                e.plan.fast_end,
                "fast",
                {
                    "episode": e.number,
                    "template_id": e.plan.template_id,
                    "fast_type": e.plan.fast_type,
                    "water_allowed": e.plan.water_allowed,
                    "medicine_changed": e.medicine_changed,
                },
            )
        )
    events = pd.DataFrame(
        [
            (
                p,
                pd.Timestamp(s),
                pd.Timestamp(en),
                k,
                json.dumps(d, ensure_ascii=False, default=str),
            )
            for p, s, en, k, d in events
        ],
        columns=["patient_id", "start", "end", "event_type", "details"],
    )

    labels = {name: [] for name in ("e1", "e1_120", "e1_54", "e3", "e2")}
    for e in t.episodes:
        window = [(int(t.minute(e.plan.fast_start)), int(t.minute(e.plan.fast_end)))]
        settings = {
            "e1": (60, 70.0, True),
            "e1_120": (120, 70.0, True),
            "e1_54": (60, 54.0, True),
            "e3": (60, 300.0, False),
        }
        for name, (horizon, threshold, below) in settings.items():
            frame = point_labels(cgm_minutes, cgm_values, 5, window, horizon, threshold, below)
            labels[name].append(frame.assign(episode=e.number, template_id=e.plan.template_id))
        breaking = e.plan.breaking_meal
        if breaking is not None:
            frame = breaking_meal_labels(cgm_minutes, cgm_values, 5, [int(t.minute(breaking.time))])
            labels["e2"].append(frame.assign(episode=e.number, template_id=e.plan.template_id))
    tables = {"timeseries": timeseries, "events": events}
    for name, frames in labels.items():
        frame = pd.concat(frames, ignore_index=True)
        minute_column = "minute" if "minute" in frame else "meal_minute"
        frame.insert(0, "patient_id", pid)
        frame["timestamp_local"] = pd.Timestamp(t.start) + pd.to_timedelta(
            frame[minute_column], unit="min"
        )
        tables[f"labels_{name}"] = frame
    tables["patient"] = pd.DataFrame([patient_row(t, sp)])
    return tables


def patient_row(t: Timeline, sp: wearables.SignalProfile) -> dict:
    record = t.twin.record
    row = {
        "patient_id": record.patient_id,
        "group": t.group,
        "source": SOURCE,
        "donor_id": t.twin.donor_id,
        "timeline_start": t.start,
        "age": record.age_on(t.start.date()),
        "sex": record.sex,
        "city": record.city,
        "hba1c_percent": record.hba1c_percent,
        "fasting_glucose_mg_dl": record.fasting_glucose_mg_dl,
        "egfr": record.egfr,
        "years_with_diabetes": record.years_with_diabetes_on(t.start.date()),
        "medicines": ", ".join(m.name for m in record.medicines),
        "takes_sulfonylurea": any(_is_secretagogue(m.name) for m in record.medicines),
        "takes_insulin": any(get_medicine(m.name).is_insulin for m in record.medicines),
        "takes_beta_blocker": record.takes_beta_blocker,
        "cyp2c9": record.cyp2c9,
        "hypoglycaemia_history": record.hypoglycaemia.value,
        "episodes": ", ".join(e.plan.template_id for e in t.episodes),
        "hypo_hr_rise_bpm": round(sp.hypo_hr_rise, 1),
        "estimated_log_cov": json.dumps(np.round(t.twin.profile.log_cov, 6).tolist()),
    }
    for name, value in t.twin.true_values.items():
        row[f"true_{name}"] = value
    for name, value in t.twin.estimated_values.items():
        row[f"estimated_{name}"] = value
    return row


TABLE_FILES = {"patient": "virtual_patients"}


def chunk_tables(timelines: list[Timeline]) -> dict[str, pd.DataFrame]:
    glucose = simulate_timelines(timelines)
    results: dict[str, list[pd.DataFrame]] = {}
    for t, g in zip(timelines, glucose, strict=True):
        for name, frame in timeline_tables(t, g).items():
            results.setdefault(name, []).append(frame)
    return {name: pd.concat(frames, ignore_index=True) for name, frames in results.items()}


def process_chunk(job: tuple[int, list[Timeline], Path]) -> int:
    """Simulate one group of timelines and write each table as a part file.

    Each worker writes its own files, so the whole cohort never has to fit in memory.
    """
    index, timelines, out_dir = job
    for name, frame in chunk_tables(timelines).items():
        folder = out_dir / TABLE_FILES.get(name, name)
        folder.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(folder / f"part-{index:03d}.parquet", index=False)
    return len(timelines)


# --- The whole cohort --------------------------------------------------------------------


def make_virtual_twins(count: int, seed: int) -> list[tuple[VirtualTwin, str]]:
    twins = load_twins()
    if not twins:
        raise FileNotFoundError("The fitted twins are missing. Please run 'rozmarra twin fit'.")
    records = generate_records(count, seed)
    training, test = training_twins(twins), held_out_twins(twins)
    rng = np.random.default_rng(seed)
    n_test = int(round(TEST_SHARE * count))
    result = []
    for i, record in enumerate(records):
        group = "test" if i >= count - n_test else "training"
        donors = test if group == "test" else training
        result.append((virtual_twin(record, donors, record.record_date, rng), group))
    return result


def build_cohort(
    count: int = 500, seed: int = RANDOM_SEED, workers: int = 6, out_dir: Path = OUT_DIR
) -> dict:
    pairs = make_virtual_twins(count, seed)
    timelines = [
        build_timeline(twin, group, seed * 1000 + i) for i, (twin, group) in enumerate(pairs)
    ]
    # Remove the part files of an earlier run, so that old and new parts never mix.
    for folder in out_dir.glob("*"):
        if folder.is_dir() and folder.name != "ehr":
            for part in folder.glob("part-*.parquet"):
                part.unlink()
    jobs = [(i, timelines[s : s + CHUNK], out_dir) for i, s in enumerate(range(0, count, CHUNK))]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            list(pool.map(process_chunk, jobs))
    else:
        for job in jobs:
            process_chunk(job)
    write_bundles([twin.record for twin, _ in pairs], out_dir / "ehr")

    tables = {
        name: pd.read_parquet(out_dir / TABLE_FILES.get(name, name))
        for name in (
            "patient",
            "events",
            "labels_e1",
            "labels_e1_120",
            "labels_e1_54",
            "labels_e3",
            "labels_e2",
        )
    }
    summary = summarise(tables)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "synthetic_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


DEMO_SEED = 4100
DEMO_HISTORY_DAYS = 14


def build_demo_days(records, fasts: dict, out_dir: Path) -> dict[str, VirtualTwin]:
    """Create the demo fasting days: 14 normal days and then the planned fast with Plan A.

    Each demo patient's twin is the closest training donor, with no random draw, and the
    seed is fixed. The team does not tune these days to make a story happen.
    """
    twins = load_twins()
    timelines, demo_twins = [], {}
    for i, record in enumerate(records):
        fast = fasts[record.patient_id]
        twin = demo_twin(record, twins, fast.date)
        demo_twins[record.patient_id] = twin
        timelines.append(
            build_timeline(
                twin,
                "demo",
                DEMO_SEED + i,
                templates=[fast.template_id],
                fast_dates=[fast.date],
                history_days=DEMO_HISTORY_DAYS,
                allow_plan_change=False,
            )
        )
    tables = chunk_tables(timelines)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("timeseries", "events", "labels_e1", "labels_e1_54", "labels_e2", "patient"):
        tables[name].to_parquet(out_dir / f"{TABLE_FILES.get(name, name)}.parquet", index=False)
    return demo_twins


def summarise(tables: dict[str, pd.DataFrame]) -> dict:
    patients = tables["patient"]
    e1 = tables["labels_e1"]
    usable = e1[e1["usable"]]
    events = tables["events"]
    fasts = events[events["event_type"] == "fast"].copy()
    fasts["details"] = fasts["details"].map(json.loads)
    fasts["template_id"] = fasts["details"].map(lambda d: d["template_id"])
    fasts["episode"] = fasts["details"].map(lambda d: d["episode"])
    fasts["changed"] = fasts["details"].map(lambda d: d["medicine_changed"])
    episode_low = e1.groupby(["patient_id", "episode"])["label"].max().rename("low")
    fasts = fasts.join(episode_low, on=["patient_id", "episode"])
    fasts = fasts.merge(
        patients[["patient_id", "takes_sulfonylurea", "takes_insulin", "group"]], on="patient_id"
    )

    def rate(frame: pd.DataFrame) -> dict:
        return {
            "episodes": len(frame),
            "share_with_low_blood_sugar": round(float(frame["low"].fillna(0).mean()), 3),
        }

    medicine = np.where(
        fasts["takes_insulin"],
        "insulin",
        np.where(fasts["takes_sulfonylurea"], "sulfonylurea without insulin", "neither"),
    )
    e2 = tables["labels_e2"]
    e1_54 = tables["labels_e1_54"]
    e3 = tables["labels_e3"]
    return {
        "source": "synthetic",
        "virtual_patients": int(len(patients)),
        "by_group": patients["group"].value_counts().to_dict(),
        "fasting_episodes": int(len(fasts)),
        "e1_time_points_usable": int(len(usable)),
        "e1_share_of_usable_points_with_label_1": round(float(usable["label"].mean()), 4),
        "e1_120_share": round(float(tables["labels_e1_120"].query("usable")["label"].mean()), 4),
        "e1_54_share": round(float(e1_54.query("usable")["label"].mean()), 4),
        "e3_share": round(float(e3.query("usable")["label"].mean()), 4),
        "e2_breaking_meals": int(len(e2)),
        "e2_share_with_label_1": round(float(e2.query("usable")["label"].mean()), 4),
        "episodes_with_low_blood_sugar": rate(fasts),
        "by_template": {k: rate(g) for k, g in fasts.groupby("template_id")},
        "by_medicine": {k: rate(g) for k, g in fasts.groupby(medicine)},
        "by_plan_change": {
            ("changed" if k else "usual"): rate(g) for k, g in fasts.groupby("changed")
        },
    }

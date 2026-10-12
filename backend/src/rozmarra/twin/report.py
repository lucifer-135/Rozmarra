"""The command "rozmarra twin fit": fit a twin to every usable real patient and report the fit.

Usable patients are the ShanghaiT2DM recording periods without an insulin pump or
intravenous insulin, and the CGMacros participants with Type 2 Diabetes. The command
writes the twins to models/twins.json and the fit report to reports/twin_fit.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from rozmarra.config import MODELS_DIR, PROCESSED_DIR, REPORTS_DIR
from rozmarra.twin.fit import (
    FORECAST_HORIZONS,
    PatientData,
    TwinFit,
    build_problem,
    fit_patient,
    fitting_windows,
    load_patient,
)

# The validation RMSE of the 40 trained twins in the T2DSim AI repository (docs/techstack.md,
# Section 5.6). It is a reference point, not a target.
T2DSIM_REFERENCE_RMSE = 29.0


def usable_patients(patients: pd.DataFrame) -> pd.DataFrame:
    shanghai = patients[
        (patients["dataset"] == "ShanghaiT2DM")
        & ~patients["uses_insulin_pump"].fillna(False).astype(bool)
        & ~patients["has_intravenous_insulin"].fillna(False).astype(bool)
    ]
    cgmacros = patients[
        (patients["dataset"] == "CGMacros") & (patients["diabetes_status"] == "type_2_diabetes")
    ]
    return pd.concat([shanghai, cgmacros])


def load_all(limit: int | None = None) -> list[PatientData]:
    timeseries = pd.read_parquet(PROCESSED_DIR / "timeseries.parquet")
    events = pd.read_parquet(PROCESSED_DIR / "events.parquet")
    patients = usable_patients(pd.read_parquet(PROCESSED_DIR / "patients.parquet"))
    if limit:
        patients = patients.head(limit)
    by_patient_ts = dict(tuple(timeseries.groupby("patient_id")))
    by_patient_ev = dict(tuple(events.groupby("patient_id")))
    empty_ev = events.iloc[:0]
    result = []
    for _, patient in patients.iterrows():
        pid = patient["patient_id"]
        if pid not in by_patient_ts:
            continue
        data = load_patient(patient, by_patient_ts[pid], by_patient_ev.get(pid, empty_ev))
        if data is not None:
            result.append(data)
    return result


def fit_and_plot(data: PatientData, figure_dir: Path | None) -> TwinFit | None:
    fit = fit_patient(data)
    if fit is not None and figure_dir is not None:
        plot_patient(data, fit, figure_dir / f"{data.patient_id}.png")
    return fit


def plot_patient(data: PatientData, fit: TwinFit, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    problem = build_problem(data)
    values = {k: np.array([v]) for k, v in fit.fitted.items()}
    fig, ax = plt.subplots(figsize=(12, 4))
    for test, colour in ((False, "#1f6f8b"), (True, "#c0392b")):
        windows = fitting_windows(data, test=test)
        if not len(windows):
            continue
        G = problem.simulator.run(values, windows)[0]
        for w in range(len(windows)):
            minutes = windows.starts[w] + np.arange(windows.length + 1)
            label = ("Twin, held-out days" if test else "Twin, fitted days") if w == 0 else None
            ax.plot(minutes / 1440, G[w], color=colour, linewidth=1.2, label=label)
    ax.plot(
        data.cgm_minute / 1440,
        data.cgm_value,
        ".",
        color="#333333",
        markersize=2,
        label="Measured CGM",
    )
    ax.axhspan(70, 180, color="#2e8b57", alpha=0.08, label="Target range (70 to 180 mg/dL)")
    ax.axhline(70, color="#b03a2e", linewidth=0.8, linestyle="--")
    ax.axvline(data.split_minute / 1440, color="#555555", linewidth=0.8, linestyle=":")
    test_rmse = (fit.metrics.get("test") or {}).get("rmse_mg_dl")
    ax.set_title(
        f"{data.patient_id} ({data.dataset}, real open data). Twin error on held-out days: "
        f"{test_rmse} mg/dL."
    )
    ax.set_xlabel("Day of the recording")
    ax.set_ylabel("Glucose (mg/dL)")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def median_of(values: Iterable[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(float(np.median(clean)), 1) if clean else None


def summarise(fits: list[TwinFit]) -> dict:
    def metric(part: str, name: str):
        return [(f.metrics.get(part) or {}).get(name) for f in fits]

    forecast = {}
    for horizon in FORECAST_HORIZONS:
        key = str(horizon)
        rows = [f.metrics.get("forecast_rmse_mg_dl", {}).get(key) for f in fits]
        rows = [r for r in rows if r]
        forecast[key] = {
            name: median_of(r[name] for r in rows)
            for name in ("twin", "last_value", "straight_line")
        }
        forecast[key]["patients"] = len(rows)
        forecast[key]["patients_where_twin_beats_last_value"] = sum(
            r["twin"] < r["last_value"] for r in rows
        )
    lows = sum(f.metrics.get("test_windows_with_low", 0) for f in fits)
    shown = sum(f.metrics.get("test_windows_with_low_where_twin_shows_low", 0) for f in fits)
    by_dataset = {}
    for dataset in sorted({f.dataset for f in fits}):
        subset = [f for f in fits if f.dataset == dataset]
        by_dataset[dataset] = {
            "patients": len(subset),
            "median_test_rmse_mg_dl": median_of(
                (f.metrics.get("test") or {}).get("rmse_mg_dl") for f in subset
            ),
        }
    parameters = {}
    for name in ("S_G", "S_I", "beta", "k_abs_factor", "meal_factor", "gamma_su"):
        values = [f.fitted[name] for f in fits if name in f.fitted]
        if values:
            # Four significant figures, because S_I is about 0.0003.
            parameters[name] = float(f"{np.median(values):.4g}")
    return {
        "created_on": date.today().isoformat(),
        "source": "real_open",
        "patients_fitted": len(fits),
        "by_dataset": by_dataset,
        "median_rmse_mg_dl": {
            "fitted_days": median_of(metric("fit", "rmse_mg_dl")),
            "held_out_days": median_of(metric("test", "rmse_mg_dl")),
        },
        "median_mard_percent": {
            "fitted_days": median_of(metric("fit", "mard_percent")),
            "held_out_days": median_of(metric("test", "mard_percent")),
        },
        "median_forecast_rmse_mg_dl": forecast,
        "held_out_windows_with_a_measured_low": lows,
        "of_which_the_twin_shows_a_low": shown,
        "median_parameters": parameters,
        "t2dsim_reference_rmse_mg_dl": T2DSIM_REFERENCE_RMSE,
    }


def write_markdown(summary: dict, path: Path) -> None:
    rmse = summary["median_rmse_mg_dl"]
    mard = summary["median_mard_percent"]
    lines = [
        "# Twin fit report",
        "",
        "This report describes how well each twin fits the real open data. All patients in "
        "this report come from the open datasets ShanghaiT2DM and CGMacros. The command "
        "`rozmarra twin fit` creates it.",
        "",
        f"The team fitted {summary['patients_fitted']} twins. The first 70% of each patient's "
        "days were used for fitting, and the last 30% were held back. Each simulation runs in "
        "12-hour windows that start from the measured CGM value.",
        "",
        "| Measure | Fitted days | Held-out days |",
        "|---|---|---|",
        f"| Median RMSE in 12-hour windows | {rmse['fitted_days']} mg/dL | "
        f"{rmse['held_out_days']} mg/dL |",
        f"| Median MARD in 12-hour windows | {mard['fitted_days']}% | {mard['held_out_days']}% |",
        "",
        "The T2DSim AI repository reports a median validation RMSE of about "
        f"{summary['t2dsim_reference_rmse_mg_dl']:g} mg/dL for its 40 trained twins. This value "
        "is a reference point from a different method and different patients, not a direct "
        "comparison.",
        "",
        "## Forecasts on held-out days",
        "",
        "Each forecast starts from the measured CGM value with the trend-matched start. The "
        "forecasts use the meals and doses recorded in the data, in the same way that a fasting "
        "plan provides them. The values are the median RMSE across patients.",
        "",
        "| Horizon | Twin | Last value | Straight line | "
        "Patients where the twin beats the last value |",
        "|---|---|---|---|---|",
    ]
    for horizon, row in summary["median_forecast_rmse_mg_dl"].items():
        lines.append(
            f"| {horizon} minutes | {row['twin']} mg/dL | {row['last_value']} mg/dL | "
            f"{row['straight_line']} mg/dL | {row['patients_where_twin_beats_last_value']} of "
            f"{row['patients']} |"
        )
    lines += [
        "",
        "## Low blood sugar",
        "",
        f"The held-out days contain {summary['held_out_windows_with_a_measured_low']} 12-hour "
        "windows with at least one measured reading below 70 mg/dL. The twin shows a value below "
        f"70 mg/dL in {summary['of_which_the_twin_shows_a_low']} of them. A twin alone can "
        "therefore miss low blood sugar, which is why the alert model will also use the CGM "
        "readings directly.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_figures(twins: list[dict], figure_dir: Path = REPORTS_DIR / "figures") -> list[Path]:
    """Write the summary figure and copy one example fit for each dataset.

    Each example is the twin whose error on held-out days is closest to the median of its
    dataset, so that the examples show a typical fit, not the best fit.
    """
    import shutil

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    written = []
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4.2))
    names = {"twin": "Twin", "last_value": "Last value", "straight_line": "Straight line"}
    for offset, (key, label) in enumerate(names.items()):
        medians = []
        for horizon in FORECAST_HORIZONS:
            values = [
                t["metrics"].get("forecast_rmse_mg_dl", {}).get(str(horizon), {}).get(key)
                for t in twins
            ]
            medians.append(np.median([v for v in values if v is not None]))
        positions = np.arange(len(FORECAST_HORIZONS)) + (offset - 1) * 0.27
        left.bar(positions, medians, width=0.27, label=label)
    left.set_xticks(range(len(FORECAST_HORIZONS)), [f"{h} minutes" for h in FORECAST_HORIZONS])
    left.set_ylabel("Median RMSE across patients (mg/dL)")
    left.set_title("Forecast error on held-out days (real open data)")
    left.legend()
    for dataset in sorted({t["dataset"] for t in twins}):
        values = [
            (t["metrics"].get("test") or {}).get("rmse_mg_dl")
            for t in twins
            if t["dataset"] == dataset
        ]
        right.hist([v for v in values if v is not None], bins=12, alpha=0.6, label=dataset)
    right.axvline(
        T2DSIM_REFERENCE_RMSE,
        color="#333333",
        linestyle="--",
        label="T2DSim AI reference (about 29 mg/dL)",
    )
    right.set_xlabel("RMSE in 12-hour windows on held-out days (mg/dL)")
    right.set_ylabel("Number of twins")
    right.set_title("Twin error on held-out days (real open data)")
    right.legend()
    fig.tight_layout()
    summary_path = figure_dir / "twin_fit_summary.png"
    fig.savefig(summary_path, dpi=120)
    plt.close(fig)
    written.append(summary_path)

    source_dir = REPORTS_DIR / "twin_fit" / "patients"
    for dataset in sorted({t["dataset"] for t in twins}):
        subset = [
            t
            for t in twins
            if t["dataset"] == dataset
            and (t["metrics"].get("test") or {}).get("rmse_mg_dl") is not None
        ]
        if not subset:
            continue
        middle = np.median([t["metrics"]["test"]["rmse_mg_dl"] for t in subset])
        example = min(subset, key=lambda t: abs(t["metrics"]["test"]["rmse_mg_dl"] - middle))
        source = source_dir / f"{example['patient_id']}.png"
        if source.exists():
            target = figure_dir / f"twin_fit_example_{dataset.lower()}.png"
            shutil.copyfile(source, target)
            written.append(target)
    return written


def fit_all(workers: int = 6, limit: int | None = None, figures: bool = True) -> dict:
    datas = load_all(limit)
    figure_dir = REPORTS_DIR / "twin_fit" / "patients" if figures else None
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            fits = list(pool.map(fit_and_plot, datas, [figure_dir] * len(datas)))
    else:
        fits = [fit_and_plot(data, figure_dir) for data in datas]
    fits = [f for f in fits if f is not None]

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": (
            "Twins fitted on real open data from ShanghaiT2DM and CGMacros. Files derived from "
            "CGMacros follow its CC BY-NC-SA 4.0 licence."
        ),
        "created_on": date.today().isoformat(),
        "twins": [f.to_json() for f in fits],
    }
    (MODELS_DIR / "twins.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")

    summary = summarise(fits)
    out = REPORTS_DIR / "twin_fit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(summary, out / "summary.md")
    if figures:
        write_figures(payload["twins"])
    return summary

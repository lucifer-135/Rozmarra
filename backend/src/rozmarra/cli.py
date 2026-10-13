"""The Rozmarra command-line tool.

Each command in docs/techstack.md, Section 13.2, has an entry here. Commands that
the team has not built yet print a clear message and stop with exit code 1.
"""

from __future__ import annotations

from enum import StrEnum

import typer

from rozmarra import __version__

app = typer.Typer(
    name="rozmarra",
    help=(
        "Rozmarra is a digital twin that predicts low and high blood sugar during religious "
        "fasting for people with Type 2 Diabetes. Rozmarra supports clinical decisions. "
        "It does not replace the judgement of a doctor."
    ),
    no_args_is_help=True,
    add_completion=False,
)
data_app = typer.Typer(
    help="Download the open datasets and convert them into the standard format.",
    no_args_is_help=True,
)
twin_app = typer.Typer(help="Fit and run the personalised physiology twin.", no_args_is_help=True)
synth_app = typer.Typer(
    help="Create synthetic virtual patients and synthetic fasting days.", no_args_is_help=True
)
model_app = typer.Typer(help="Train and evaluate the prediction models.", no_args_is_help=True)
demo_app = typer.Typer(
    help="Prepare the demo patients and their saved results.", no_args_is_help=True
)
ehr_app = typer.Typer(
    help="Create synthetic health records in FHIR R4 format.", no_args_is_help=True
)

app.add_typer(data_app, name="data")
app.add_typer(ehr_app, name="ehr")
app.add_typer(twin_app, name="twin")
app.add_typer(synth_app, name="synth")
app.add_typer(model_app, name="model")
app.add_typer(demo_app, name="demo")


class Dataset(StrEnum):
    all = "all"
    shanghai = "shanghai"
    cgmacros = "cgmacros"
    bigideas = "bigideas"


def _not_built(command: str) -> None:
    typer.echo(
        f"The command 'rozmarra {command}' is not built yet. "
        "Section 13.2 of docs/techstack.md describes what it will do."
    )
    raise typer.Exit(code=1)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"Rozmarra {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the Rozmarra version and stop.",
        callback=_show_version,
        is_eager=True,
    ),
) -> None:
    """Rozmarra command-line tool."""


@data_app.command("download")
def data_download(
    dataset: Dataset = typer.Option(
        Dataset.all, "--dataset", "-d", help="The dataset to download. The default is all of them."
    ),
) -> None:
    """Download the open datasets into data/raw. The raw files are never committed."""
    from rozmarra.data.download import DATASETS, download_datasets

    download_datasets(DATASETS if dataset is Dataset.all else (dataset.value,))


@data_app.command("prepare")
def data_prepare() -> None:
    """Convert the downloaded datasets into the standard Parquet format in data/processed."""
    from rozmarra.config import PROCESSED_DIR
    from rozmarra.data.prepare import prepare

    summary = prepare()
    for dataset, facts in summary["datasets"].items():
        typer.echo(
            f"{dataset}: {facts['patients']} patients, {facts['cgm_readings']:,} CGM readings "
            f"over a median of {facts['median_days_of_cgm']} days, and {facts['meals']:,} meals."
        )
    typer.echo(f"Rozmarra saved the standard tables in {PROCESSED_DIR}.")


@twin_app.command("fit")
def twin_fit(
    workers: int = typer.Option(6, help="The number of patients to fit at the same time."),
    limit: int = typer.Option(0, help="Fit only this many patients, for a quick check."),
) -> None:
    """Fit a twin to each usable real patient and write the fit report to reports/twin_fit."""
    from rozmarra.twin.report import fit_all

    summary = fit_all(workers=workers, limit=limit or None)
    rmse = summary["median_rmse_mg_dl"]
    two_hours = summary["median_forecast_rmse_mg_dl"].get("120", {})
    typer.echo(
        f"Rozmarra fitted {summary['patients_fitted']} twins. The median error in 12-hour windows "
        f"is {rmse['fitted_days']} mg/dL on fitted days and {rmse['held_out_days']} mg/dL on "
        f"held-out days. The median 2-hour forecast error is {two_hours.get('twin')} mg/dL, "
        f"compared with {two_hours.get('last_value')} mg/dL for the last value."
    )


@twin_app.command("parkes")
def twin_parkes(
    workers: int = typer.Option(6, help="The number of patients to process at the same time."),
) -> None:
    """Sort the twins' forecasts on held-out days into the zones of the Parkes error grid."""
    from rozmarra.config import REPORTS_DIR
    from rozmarra.twin.parkes import run

    result = run(workers=workers)
    row = result["all"]["30_min"]["twin"]
    typer.echo(
        f"{row['share_a_and_b']:.2%} of {row['pairs']:,} 30-minute twin forecasts fall in zones "
        f"A and B of the Parkes error grid for Type 2 Diabetes. The PRD target is "
        f"{result['target_share_a_and_b_30_min']:.0%} or more. The results are in "
        f"{REPORTS_DIR / 'twin_fit'}."
    )


@synth_app.command("cohort")
def synth_cohort(
    patients: int = typer.Option(500, help="The number of virtual patients to create."),
    seed: int = typer.Option(2026, help="The random seed, so that the cohort is reproducible."),
    workers: int = typer.Option(6, help="The number of patient groups to simulate at once."),
) -> None:
    """Create synthetic virtual patients with normal days, fasting days, wearables and labels."""
    from rozmarra.synth.cohort import OUT_DIR, build_cohort

    summary = build_cohort(patients, seed, workers=workers)
    low = summary["episodes_with_low_blood_sugar"]
    typer.echo(
        f"Rozmarra created {summary['virtual_patients']} synthetic virtual patients with "
        f"{summary['fasting_episodes']} fasting episodes. Low blood sugar occurred in "
        f"{low['share_with_low_blood_sugar']:.0%} of the episodes, and "
        f"{summary['e2_share_with_label_1']:.0%} of the meals that break a fast were followed by "
        f"high blood sugar. The files are in {OUT_DIR}."
    )


@model_app.command("train")
def model_train(
    workers: int = typer.Option(6, help="The number of patient groups to process at once."),
) -> None:
    """Build the feature tables for the models: time points, meals and fasting episodes."""
    import warnings

    from rozmarra.ml.datasets import FEATURE_DIR, build_feature_tables, build_real_meal_table
    from rozmarra.ml.episodes import build_episode_table

    warnings.filterwarnings("ignore", category=RuntimeWarning)
    counts = build_feature_tables(workers=workers)
    real_meals = build_real_meal_table(workers=workers)
    episodes = build_episode_table(workers=workers)
    typer.echo(
        f"Rozmarra built {counts['e1_synthetic']:,} synthetic time points, "
        f"{counts['e2_synthetic']:,} meals that break a fast, {counts['e1_real']:,} real time "
        f"points, {real_meals:,} real meals after a night without food and "
        f"{len(episodes):,} fasting episodes in {FEATURE_DIR}."
    )


@model_app.command("evaluate")
def model_evaluate() -> None:
    """Train the models on the training group, test them, and write reports/metrics.json."""
    import json
    import warnings

    from rozmarra.config import REPORTS_DIR
    from rozmarra.ml.episodes import train_episode_models
    from rozmarra.ml.evaluate import run_all
    from rozmarra.ml.figures import write_figures

    warnings.filterwarnings("ignore")
    metrics = run_all()
    metrics["synthetic"]["f1"] = train_episode_models()
    (REPORTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    write_figures(metrics)
    e1 = metrics["synthetic"]["e1"]
    real = metrics["real"]["e1"]["all"]
    meals = metrics["real"].get("e2")
    meal_text = (
        f"Real meals after a night without food: E2 AUROC {meals['auroc']}. " if meals else ""
    )
    typer.echo(
        f"Synthetic fasting days: E1 AUROC {e1['auroc']}, AUPRC {e1['auprc']}. "
        f"Real normal days: E1 AUROC {real['auroc']}, AUPRC {real['auprc']}. {meal_text}"
        f"The full results are in {REPORTS_DIR / 'metrics.json'}."
    )


@model_app.command("sensitivity")
def model_sensitivity(
    workers: int = typer.Option(6, help="The number of patient groups to process at once."),
) -> None:
    """Repeat the E1 evaluation with the weaker sulfonylurea effect fitted on real data."""
    import warnings

    from rozmarra.ml.sensitivity import WEAK_GAMMA_SU, run

    warnings.filterwarnings("ignore")
    result = run(workers=workers)
    low = result["episodes_with_low_blood_sugar"]["share_with_low_blood_sugar"]
    typer.echo(
        f"With the sulfonylurea effect centred on {WEAK_GAMMA_SU}, low blood sugar occurred in "
        f"{low:.0%} of the fasting episodes. The E1 model reached an AUROC of "
        f"{result['e1']['auroc']} and an AUPRC of {result['e1']['auprc']} on the test group."
    )


@ehr_app.command("generate")
def ehr_generate(
    patients: int = typer.Option(300, help="The number of synthetic records to create."),
    seed: int = typer.Option(2026, help="The random seed, so that the records are reproducible."),
) -> None:
    """Create synthetic health records and save them as FHIR R4 Bundles in data/processed/ehr."""
    from rozmarra.config import PROCESSED_DIR
    from rozmarra.ehr.generator import generate_records
    from rozmarra.ehr.store import write_bundles

    folder = PROCESSED_DIR / "ehr"
    paths = write_bundles(generate_records(patients, seed), folder)
    typer.echo(f"Rozmarra saved {len(paths)} synthetic health records in {folder}.")


@demo_app.command("build")
def demo_build() -> None:
    """Prepare the demo patients: their health records, draft plans and IDF-DAR scores."""
    from rozmarra.config import DEMO_DIR
    from rozmarra.demo import build_demo
    from rozmarra.formatting import capitalised

    for summary in build_demo():
        typer.echo(
            f"{summary['label']}, plans to keep the {summary['fast']} fast on "
            f"{summary['fast_date_text']}. The IDF-DAR total is {summary['idf_dar_total']:g} "
            f"({capitalised(summary['idf_dar_category'])})."
        )
    typer.echo(f"Rozmarra saved the synthetic demo patients in {DEMO_DIR}.")


@demo_app.command("reset")
def demo_reset() -> None:
    """Remove the saved plans and approvals, so that every demo plan starts as "Not started"."""
    from rozmarra.api.store import STORE

    removed = STORE.clear_saved_plans()
    typer.echo(f"Rozmarra removed {removed} saved plans. Every demo plan is now not started.")


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", help="The address on which the API listens."),
    port: int = typer.Option(8000, help="The port on which the API listens."),
    reload: bool = typer.Option(False, help="Restart the API when the code changes."),
) -> None:
    """Start the Rozmarra API at http://127.0.0.1:8000/api."""
    import uvicorn

    uvicorn.run("rozmarra.api.main:app", host=host, port=port, reload=reload)


@app.command("check-language")
def check_language() -> None:
    """Check the English text against the list of words to avoid in docs/prd.md, Section 17.3."""
    from rozmarra.language.check import check

    findings = check()
    for finding in findings:
        typer.echo(str(finding))
    if findings:
        typer.echo(f"The language check found {len(findings)} issues. Please correct them.")
        raise typer.Exit(code=1)
    typer.echo("The language check found no words to avoid and no American spellings.")


if __name__ == "__main__":
    app()

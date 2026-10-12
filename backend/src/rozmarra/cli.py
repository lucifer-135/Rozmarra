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

app.add_typer(data_app, name="data")
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
    """Convert the downloaded datasets into the standard Parquet format."""
    _not_built("data prepare")


@twin_app.command("fit")
def twin_fit() -> None:
    """Fit a twin to each real patient and write the fit report."""
    _not_built("twin fit")


@synth_app.command("cohort")
def synth_cohort(
    patients: int = typer.Option(300, help="The number of virtual patients to create."),
    seed: int = typer.Option(2026, help="The random seed, so that the cohort is reproducible."),
) -> None:
    """Create synthetic virtual patients with fasting days and wearable signals."""
    _not_built("synth cohort")


@model_app.command("train")
def model_train() -> None:
    """Train the LightGBM models for the adverse events."""
    _not_built("model train")


@model_app.command("evaluate")
def model_evaluate() -> None:
    """Evaluate the models and write reports/metrics.json and the figures."""
    _not_built("model evaluate")


@demo_app.command("build")
def demo_build() -> None:
    """Prepare the demo patients and their saved results."""
    _not_built("demo build")


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
    _not_built("check-language")


if __name__ == "__main__":
    app()

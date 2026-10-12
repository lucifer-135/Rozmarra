"""Figures of the model results for the model card and the presentation."""

from __future__ import annotations

from pathlib import Path

from rozmarra.config import REPORTS_DIR

FIGURES = REPORTS_DIR / "figures"


def _bars(ax, rows: list[tuple[str, float | None, list[float] | None]], title: str, metric: str):
    labels = [r[0] for r in rows]
    values = [r[1] or 0 for r in rows]
    errors = [
        [(v - (ci[0] if ci else v)) for v, (_, _, ci) in zip(values, rows, strict=True)],
        [((ci[1] if ci else v) - v) for v, (_, _, ci) in zip(values, rows, strict=True)],
    ]
    colours = [
        "#1f6f8b" if label in {"Full model", "all streams"} else "#9aa5b1" for label in labels
    ]
    ax.barh(labels, values, xerr=errors, color=colours, capsize=3)
    ax.invert_yaxis()
    ax.set_xlabel(metric)
    ax.set_title(title, fontsize=10)
    # Each value label sits to the right of the end of its error bar.
    for i, (v, (_, _, ci)) in enumerate(zip(values, rows, strict=True)):
        ax.text((ci[1] if ci else v) + 0.01, i, f"{v:.2f}", va="center", fontsize=8)
    ax.set_xlim(0, max((r[2][1] if r[2] else r[1] or 0) for r in rows) * 1.18 + 0.02)


def _comparison_rows(report: dict, metric: str):
    rows = [
        ("Full model", report.get(metric), report.get("confidence_intervals_95", {}).get(metric))
    ]
    for name, values in report.get("baselines", {}).items():
        if name == "model with CGM data only":
            continue
        rows.append(
            (
                name[0].upper() + name[1:],
                values.get(metric),
                values.get("confidence_intervals_95", {}).get(metric),
            )
        )
    for name, values in report.get("ablation", {}).items():
        if name == "all streams":
            continue
        rows.append(
            (
                f"Model: {name}",
                values.get(metric),
                values.get("confidence_intervals_95", {}).get(metric),
            )
        )
    return rows


def write_figures(metrics: dict, folder: Path = FIGURES) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    folder.mkdir(parents=True, exist_ok=True)
    written = []
    synthetic, real = metrics["synthetic"]["e1"], metrics["real"]["e1"]
    real_report = {**real["all"], "baselines": real["baselines"], "ablation": real["ablation"]}
    for metric, label in (("auprc", "AUPRC"), ("auroc", "AUROC")):
        fig, axes = plt.subplots(1, 2, figsize=(13, 5))
        _bars(
            axes[0],
            _comparison_rows(synthetic, metric),
            "Synthetic fasting days (test group)",
            label,
        )
        _bars(
            axes[1],
            _comparison_rows(real_report, metric),
            "Real normal days (held-out days)",
            label,
        )
        fig.suptitle(f"Low blood sugar 60 minutes ahead: {label} with 95% intervals", fontsize=11)
        fig.tight_layout()
        path = folder / f"e1_comparison_{metric}.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        written.append(path)

    fig, ax = plt.subplots(figsize=(6, 5))
    for name, curve in (
        ("E1, synthetic fasting days", synthetic["calibration"]),
        ("E1, real normal days", real["all"].get("calibration", [])),
        ("E2, synthetic meals that break a fast", metrics["synthetic"]["e2"]["calibration"]),
    ):
        if curve:
            ax.plot(
                [c["mean_predicted"] for c in curve],
                [c["observed_rate"] for c in curve],
                "o-",
                label=name,
            )
    ax.plot([0, 1], [0, 1], "--", color="#777777", label="Perfect calibration")
    ax.set_xlabel("Estimated chance")
    ax.set_ylabel("Observed share of events")
    ax.set_title("Calibration of the prediction models", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = folder / "calibration.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    written.append(path)
    return written

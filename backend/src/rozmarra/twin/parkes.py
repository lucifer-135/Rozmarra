"""The Parkes consensus error grid for Type 2 Diabetes, applied to the twin's forecasts.

The grid sorts each pair of a reference glucose value (x) and an estimated value (y) into
five zones. Zone A means no effect on clinical action, zone B altered action with little or
no effect on the outcome, zone C an altered outcome, zone D a significant medical risk and
zone E dangerous consequences. The zone boundaries come from:

    Pfützner A, Klonoff DC, Pardo S, Parkes JL. Technical aspects of the Parkes error grid.
    J Diabetes Sci Technol. 2013;7(5):1275-1281.

The team wrote this code from the published coordinates. Here the reference value is the
measured CGM reading on a held-out day, and the estimated value is the twin's forecast made
30, 60 or 120 minutes earlier. The PRD target is 95% or more of the 30-minute forecasts in
zones A and B (docs/prd.md, Section 15).
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from datetime import date

import numpy as np

from rozmarra.config import REPORTS_DIR

GRID_LIMIT = 550.0
ZONES = ("A", "B", "C", "D", "E")
TARGET_A_AND_B = 0.95
FORECASTS = {"twin": "Twin", "last_value": "Last value", "straight_line": "Straight line"}


def zone_polygons(limit: float = GRID_LIMIT) -> dict[str, list[np.ndarray]]:
    """The polygons of zones B to E for Type 2 Diabetes, in mg/dL. Zone A is the rest.

    Each zone has an upper part (the estimate is too high) and a lower part (too low), except
    zone E, which has only an upper part. When the data goes above 550 mg/dL, the last edge of
    each boundary is extended along the same line, as the paper describes."""
    L = max(float(limit), GRID_LIMIT)

    def polygon(*points):
        return np.array(points, dtype=float)

    return {
        "E": [polygon((0, 200), (35, 200), (35 + 3 * (L - 200) / 70, L), (0, L))],
        "D": [
            polygon((0, 80), (25, 80), (35, 90), (35 + 9 * (L - 90) / 46, L), (0, L)),
            polygon((250, 0), (250, 40), (410, 110), (L, 110 + 5 * (L - 410) / 14), (L, 0)),
        ],
        "C": [
            polygon((0, 60), (30, 60), (30 + 25 * (L - 60) / 49, L), (0, L)),
            polygon((90, 0), (260, 130), (L, 130 + 12 * (L - 260) / 29), (L, 0)),
        ],
        "B": [
            polygon((0, 50), (30, 50), (230, 330), (230 + 21 * (L - 330) / 22, L), (0, L)),
            polygon((50, 0), (50, 30), (90, 80), (330, 230), (L, L - 100), (L, 0)),
        ],
    }


def inside(polygon: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Whether each point lies inside the polygon, by counting edge crossings of a ray."""
    result = np.zeros(len(x), dtype=bool)
    for (x1, y1), (x2, y2) in zip(polygon, np.roll(polygon, -1, axis=0), strict=True):
        if y1 == y2:
            continue
        crosses = (y1 > y) != (y2 > y)
        edge_x = x1 + (x2 - x1) * (y - y1) / (y2 - y1)
        result ^= crosses & (x < edge_x)
    return result


def parkes_zones(reference, estimate) -> np.ndarray:
    """The zone letter of each pair of a reference value and an estimated value (mg/dL)."""
    x = np.clip(np.asarray(reference, dtype=float), 0, None)
    y = np.clip(np.asarray(estimate, dtype=float), 0, None)
    limit = max(GRID_LIMIT, float(x.max(initial=0)) + 1, float(y.max(initial=0)) + 1)
    zones = np.full(len(x), "A", dtype="<U1")
    decided = np.zeros(len(x), dtype=bool)
    # The more severe zone wins where zones overlap, so the zones are checked from E to B.
    for zone, polygons in zone_polygons(limit).items():
        hit = np.zeros(len(x), dtype=bool)
        for polygon in polygons:
            hit |= inside(polygon, x, y)
        zones[hit & ~decided] = zone
        decided |= hit
    return zones


def zone_shares(zones: np.ndarray) -> dict:
    count = len(zones)
    shares = {z: round(float(np.mean(zones == z)), 4) if count else None for z in ZONES}
    return {
        "pairs": int(count),
        "shares": shares,
        "share_a_and_b": round(float(np.isin(zones, ["A", "B"]).mean()), 4) if count else None,
    }


# --- The twin's forecasts on held-out days ------------------------------------------------


def _patient_pairs(job) -> tuple[str, str, dict[int, dict[str, np.ndarray]]] | None:
    from rozmarra.twin.fit import forecast_pairs, forecast_windows, twin_simulator

    data, twin = job
    forecasts = forecast_windows(data)
    if not len(forecasts):
        return None
    return data.patient_id, data.dataset, forecast_pairs(twin_simulator(data), twin, forecasts)


def collect_pairs(workers: int = 6, datas=None, twins: list[dict] | None = None):
    """The forecast pairs of every fitted twin on its held-out days."""
    from rozmarra.twin.profiles import load_twins
    from rozmarra.twin.report import load_all

    datas = datas if datas is not None else load_all()
    fitted = {t["patient_id"]: t["fitted"] for t in (twins or load_twins())}
    jobs = [(d, fitted[d.patient_id]) for d in datas if d.patient_id in fitted]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_patient_pairs, jobs, chunksize=2))
    else:
        results = [_patient_pairs(job) for job in jobs]
    return [r for r in results if r is not None]


def summarise(results) -> dict:
    """Zone shares for each horizon and forecast, for all patients and for each dataset."""
    from rozmarra.twin.fit import FORECAST_HORIZONS

    def joined(subset, horizon, key):
        parts = [pairs[horizon][key] for _, _, pairs in subset if horizon in pairs]
        return np.concatenate(parts) if parts else np.array([])

    def part(subset):
        out = {"patients": len({pid for pid, _, _ in subset})}
        for horizon in FORECAST_HORIZONS:
            measured = joined(subset, horizon, "measured")
            out[f"{horizon}_min"] = {
                key: zone_shares(parkes_zones(measured, joined(subset, horizon, key)))
                for key in FORECASTS
            }
        return out

    summary = {
        "created_on": date.today().isoformat(),
        "source": "real_open",
        "grid": "Parkes consensus error grid for Type 2 Diabetes (Pfützner et al., 2013)",
        "target_share_a_and_b_30_min": TARGET_A_AND_B,
        "all": part(results),
        "by_dataset": {},
    }
    for dataset in sorted({d for _, d, _ in results}):
        summary["by_dataset"][dataset] = part([r for r in results if r[1] == dataset])
    return summary


def plot_grid(results, path, horizon: int = 30) -> None:
    """Draw the zone boundaries and the twin's forecasts at one horizon."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    measured = np.concatenate([p[horizon]["measured"] for _, _, p in results if horizon in p])
    twin = np.concatenate([p[horizon]["twin"] for _, _, p in results if horizon in p])
    shares = zone_shares(parkes_zones(measured, twin))
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(measured, twin, s=3, alpha=0.25, color="#1f6f8b", linewidths=0)
    for polygons in zone_polygons().values():
        for polygon in polygons:
            closed = np.vstack([polygon, polygon[:1]])
            ax.plot(closed[:, 0], closed[:, 1], color="#444444", linewidth=0.9)
    labels = {"A": (440, 440), "B": (440, 300), "C": (440, 170), "D": (480, 60), "E": (12, 450)}
    for zone, (x, y) in labels.items():
        ax.text(x, y, zone, fontsize=13, fontweight="bold", color="#444444")
    ax.text(300, 500, "B", fontsize=13, fontweight="bold", color="#444444")
    ax.text(170, 500, "C", fontsize=13, fontweight="bold", color="#444444")
    ax.text(70, 500, "D", fontsize=13, fontweight="bold", color="#444444")
    ax.set_xlim(0, GRID_LIMIT)
    ax.set_ylim(0, GRID_LIMIT)
    ax.set_aspect("equal")
    ax.set_xlabel("Measured CGM value on a held-out day (mg/dL)")
    ax.set_ylabel(f"Twin forecast made {horizon} minutes earlier (mg/dL)")
    ax.set_title(
        f"Parkes error grid for Type 2 Diabetes (real open data).\n"
        f"{shares['share_a_and_b']:.2%} of {shares['pairs']:,} forecasts fall in zones A and B."
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def run(workers: int = 6, datas=None, twins: list[dict] | None = None) -> dict:
    """Score the forecasts, add the result to reports/twin_fit and draw the figure."""
    from rozmarra.twin.report import write_markdown

    results = collect_pairs(workers, datas, twins)
    parkes = summarise(results)
    out = REPORTS_DIR / "twin_fit"
    summary_path = out / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["parkes"] = parkes
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        write_markdown(summary, out / "summary.md")
    plot_grid(results, REPORTS_DIR / "figures" / "parkes_30min.png")
    return parkes

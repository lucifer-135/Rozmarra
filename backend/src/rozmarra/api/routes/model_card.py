"""The model card endpoint: the metrics, the data sources and the limits."""

from __future__ import annotations

import json

from fastapi import APIRouter

from rozmarra.api.store import STORE
from rozmarra.config import REPORTS_DIR

router = APIRouter(tags=["Model card"])

DATA_SOURCES = [
    {
        "name": "ShanghaiT2DM",
        "type": "real_open",
        "licence": "CC BY 4.0 (article)",
        "use": "Fitting the twins and testing predictions on normal days",
    },
    {
        "name": "CGMacros",
        "type": "real_open",
        "licence": "CC BY-NC-SA 4.0",
        "use": "Fitting the twins and testing the fusion of CGM and smartwatch data",
    },
    {
        "name": "Rozmarra synthetic cohort",
        "type": "synthetic",
        "licence": "Apache License 2.0",
        "use": "Simulated fasting days of 500 virtual patients for training and testing",
    },
]
LIMITATIONS = [
    "Rozmarra is a research prototype. It is not a certified medical device.",
    "The real data comes from China and the United States, not from India.",
    "No open dataset contains CGM data from Indian festival fasts. The fasting results come "
    "from simulated fasting days, which reflect the team's modelling assumptions.",
    "No doctor or pharmacist has reviewed the clinical content of this prototype.",
    "The twin's sulfonylurea effect is modest, and the real data identifies it poorly.",
]


@router.get("/model-card", summary="The metrics, data sources and limitations")
def model_card():
    twin_fit = REPORTS_DIR / "twin_fit" / "summary.json"
    synthetic = REPORTS_DIR / "synthetic_summary.json"
    return {
        "metrics": STORE.metrics,
        "twin_fit": json.loads(twin_fit.read_text(encoding="utf-8")) if twin_fit.exists() else None,
        "synthetic_cohort": json.loads(synthetic.read_text(encoding="utf-8"))
        if synthetic.exists()
        else None,
        "data_sources": DATA_SOURCES,
        "limitations": LIMITATIONS,
        "notice": (
            "Rozmarra supports clinical decisions. It does not replace the judgement of a doctor."
        ),
    }

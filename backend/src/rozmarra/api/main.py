"""The Rozmarra API application.

Start it with "uv run rozmarra serve". The interactive documentation is then at
http://127.0.0.1:8000/docs.
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rozmarra import __version__
from rozmarra.api import services
from rozmarra.api.routes import health, model_card, patients
from rozmarra.config import DASHBOARD_ORIGINS

log = logging.getLogger("rozmarra")


def _warm_up() -> None:
    try:
        services.warm_up()
        log.info("Rozmarra prepared the demo patients.")
    except Exception:  # The API still works without the prepared results, only more slowly.
        log.exception("Rozmarra could not prepare the demo patients in advance.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The slow results are prepared in the background, so the API answers at once.
    threading.Thread(target=_warm_up, name="rozmarra-warm-up", daemon=True).start()
    yield


def create_app(warm_up: bool = True) -> FastAPI:
    app = FastAPI(
        lifespan=lifespan if warm_up else None,
        title="Rozmarra API",
        version=__version__,
        description=(
            "The Rozmarra API serves the virtual patients, fasting plan simulations, risk "
            "predictions and patient plans to the doctor dashboard. All patient data in this "
            "prototype is synthetic or comes from open anonymised datasets. Rozmarra supports "
            "clinical decisions. It does not replace the judgement of a doctor."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DASHBOARD_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(patients.router, prefix="/api")
    app.include_router(model_card.router, prefix="/api")
    return app


app = create_app()

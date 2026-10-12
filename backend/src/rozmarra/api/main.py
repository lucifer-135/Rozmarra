"""The Rozmarra API application.

Start it with "uv run rozmarra serve". The interactive documentation is then at
http://127.0.0.1:8000/docs.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rozmarra import __version__
from rozmarra.api.routes import health
from rozmarra.config import DASHBOARD_ORIGINS


def create_app() -> FastAPI:
    app = FastAPI(
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
    return app


app = create_app()

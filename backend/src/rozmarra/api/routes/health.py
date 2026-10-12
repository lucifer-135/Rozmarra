"""The health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from rozmarra import __version__
from rozmarra.api.schemas import HealthResponse

router = APIRouter(tags=["Service"])


@router.get("/health", response_model=HealthResponse, summary="Check that the service is running")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="Rozmarra API",
        version=__version__,
        message="The Rozmarra service is running.",
    )

"""Request and response shapes for the Rozmarra API."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    message: str

"""Paths and shared settings for Rozmarra.

This module uses only the Python standard library, so that the download script
can import it before the full environment is installed.
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_repo_root() -> Path:
    """Return the repository root folder.

    The environment variable ROZMARRA_ROOT overrides the search. Otherwise, the
    function looks for the first parent folder that holds both "backend" and "docs".
    """
    override = os.environ.get("ROZMARRA_ROOT")
    if override:
        return Path(override).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "backend").is_dir() and (parent / "docs").is_dir():
            return parent
    return Path.cwd()


REPO_ROOT = _find_repo_root()
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DEMO_DIR = DATA_DIR / "demo"
MODELS_DIR = REPO_ROOT / "models"
REPORTS_DIR = REPO_ROOT / "reports"

# Every random process in Rozmarra uses this seed, so that results are reproducible.
RANDOM_SEED = 2026

# Synthetic Indian patients use Indian Standard Time.
TIMEZONE_INDIA = "Asia/Kolkata"

# The dashboard runs at this address during development.
DASHBOARD_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

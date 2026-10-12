"""Saving and loading health records as FHIR R4 Bundle files."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from rozmarra.ehr.fhir import from_bundle, to_bundle
from rozmarra.ehr.records import PatientRecord


def write_bundle(record: PatientRecord, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record.patient_id}.json"
    path.write_text(json.dumps(to_bundle(record), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_bundles(records: Iterable[PatientRecord], folder: Path) -> list[Path]:
    return [write_bundle(record, folder) for record in records]


def read_bundle(path: Path) -> PatientRecord:
    return from_bundle(json.loads(path.read_text(encoding="utf-8")))


def load_records(folder: Path) -> list[PatientRecord]:
    return [read_bundle(path) for path in sorted(folder.glob("SY-*.json"))]

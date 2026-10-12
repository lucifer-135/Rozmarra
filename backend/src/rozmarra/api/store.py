"""The data that the API serves: the synthetic demo patients and the trained models.

The API reads everything from data/demo, models and reports, so the demo runs without the
large datasets. Plan approvals are kept in a small SQLite file (data/demo/approvals.sqlite),
which is not committed.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd

from rozmarra.config import DEMO_DIR, MODELS_DIR, REPORTS_DIR
from rozmarra.ehr.demo_patients import DEMO_FASTS
from rozmarra.ehr.records import PatientRecord
from rozmarra.ehr.store import read_bundle
from rozmarra.fasting.plan import FastingPlan, PlanStatus
from rozmarra.twin.profiles import average_parameters, load_twins
from rozmarra.twin.simulate import TwinProfile
from rozmarra.twin.virtual_patients import training_twins

APPROVALS_FILE = DEMO_DIR / "approvals.sqlite"


class DemoStore:
    def __init__(self, demo_dir: Path = DEMO_DIR, models_dir: Path = MODELS_DIR):
        self.demo_dir = demo_dir
        self.models_dir = models_dir
        self._approvals_ready = False

    # --- Patients ------------------------------------------------------------------------

    @cached_property
    def records(self) -> dict[str, PatientRecord]:
        records = [read_bundle(p) for p in sorted((self.demo_dir / "patients").glob("SY-*.json"))]
        return {r.patient_id: r for r in records}

    @cached_property
    def summaries(self) -> dict[str, dict]:
        rows = json.loads((self.demo_dir / "demo_patients.json").read_text(encoding="utf-8"))
        return {row["patient_id"]: row for row in rows}

    def record(self, patient_id: str) -> PatientRecord:
        if patient_id not in self.records:
            raise KeyError(patient_id)
        return self.records[patient_id]

    def fast(self, patient_id: str):
        return DEMO_FASTS[patient_id]

    def default_plan(self, patient_id: str) -> FastingPlan:
        path = self.demo_dir / "plans" / f"{patient_id}_plan_a.json"
        return FastingPlan.model_validate_json(path.read_text(encoding="utf-8"))

    # --- Twins ---------------------------------------------------------------------------

    @cached_property
    def demo_twins(self) -> dict[str, dict]:
        return json.loads((self.demo_dir / "demo_twins.json").read_text(encoding="utf-8"))

    def profile(self, patient_id: str) -> TwinProfile:
        t = self.demo_twins[patient_id]
        return TwinProfile(
            t["G_b"],
            t["I_b"],
            t["body_weight"],
            t["egfr"],
            t["cr_factor"],
            t["cyp_factor"],
            tuple(t["names"]),
            np.array(t["log_mean"]),
            np.array(t["log_cov"]),
            f"donor twin {t['donor_id']}",
        )

    @cached_property
    def fitted_twins(self) -> list[dict]:
        return load_twins(self.models_dir / "twins.json")

    @cached_property
    def average_values(self) -> dict[str, float]:
        values = average_parameters(training_twins(self.fitted_twins))
        # The average patient uses the same sulfonylurea effect as the demo twins.
        values["gamma_su"] = 3.0
        return values

    def average_profile(self, patient_id: str) -> TwinProfile:
        return self.profile(patient_id).with_parameters(
            self.average_values, source="average patient"
        )

    def donor(self, patient_id: str) -> dict | None:
        donor_id = self.demo_twins[patient_id]["donor_id"]
        return next((t for t in self.fitted_twins if t["patient_id"] == donor_id), None)

    # --- Demo fasting days ---------------------------------------------------------------

    @cached_property
    def fasting_days(self) -> dict[str, pd.DataFrame]:
        folder = self.demo_dir / "fasting_days"
        return {
            name: pd.read_parquet(folder / f"{name}.parquet")
            for name in ("timeseries", "events", "virtual_patients", "labels_e1")
        }

    # --- Models and reports --------------------------------------------------------------

    @cached_property
    def point_models(self):
        from rozmarra.ml.train import TrainedModel

        return {
            t: TrainedModel.load(t, self.models_dir)
            for t in ("e1", "e2")
            if (self.models_dir / f"{t}.json").exists()
        }

    @cached_property
    def episode_models(self):
        from rozmarra.ml.episodes import EpisodeModel

        return {
            n: EpisodeModel.load(n, self.models_dir)
            for n in ("f1_low", "f1_high")
            if (self.models_dir / f"{n}.json").exists()
        }

    @cached_property
    def metrics(self) -> dict:
        path = REPORTS_DIR / "metrics.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    # --- Approvals -----------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(APPROVALS_FILE)
        if not self._approvals_ready:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS approvals (patient_id TEXT, plan_id TEXT, "
                "plan TEXT, approved_by TEXT, approved_on TEXT, saved_at TEXT, "
                "PRIMARY KEY (patient_id, plan_id))"
            )
            self._approvals_ready = True
        return connection

    def approve(self, patient_id: str, plan_id: str, plan: FastingPlan, doctor: str) -> FastingPlan:
        approved = plan.model_copy(
            update={
                "status": PlanStatus.APPROVED,
                "approved_by": doctor,
                "approved_on": date.today(),
            }
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO approvals VALUES (?, ?, ?, ?, ?, ?)",
                (
                    patient_id,
                    plan_id,
                    approved.model_dump_json(),
                    doctor,
                    approved.approved_on.isoformat(),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
        return approved

    def approved_plan(self, patient_id: str, plan_id: str) -> FastingPlan | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT plan FROM approvals WHERE patient_id = ? AND plan_id = ?",
                (patient_id, plan_id),
            ).fetchone()
        return FastingPlan.model_validate_json(row[0]) if row else None

    def plan_status(self, patient_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM approvals WHERE patient_id = ?", (patient_id,)
            ).fetchone()
        return "Approved" if row and row[0] else "Draft"


STORE = DemoStore()

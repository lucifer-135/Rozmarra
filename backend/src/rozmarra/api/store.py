"""The data that the API serves: the synthetic demo patients and the trained models.

The API reads everything from data/demo, models and reports, so the demo runs without the
large datasets. The doctor's saved plans and approvals are kept in a small SQLite file
(data/demo/approvals.sqlite), which is not committed.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
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


def _content(plan: FastingPlan) -> dict:
    """The plan without its status and approval, to check whether the doctor changed it."""
    return plan.model_dump(exclude={"status", "approved_by", "approved_on"})


def _as_draft(plan: FastingPlan) -> FastingPlan:
    return plan.model_copy(
        update={"status": PlanStatus.DRAFT, "approved_by": None, "approved_on": None}
    )


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

    # --- Saved plans and approvals --------------------------------------------------------
    #
    # The doctor's plans are saved as drafts when the doctor tests them. A patient has at
    # most one approved plan. If the doctor changes an approved plan, it becomes a draft
    # again, because the approval no longer matches the plan.

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """A connection that saves the changes and then closes, so the file is never left open."""
        connection = sqlite3.connect(APPROVALS_FILE)
        try:
            with connection:
                if not self._approvals_ready:
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS plans (patient_id TEXT, plan_id TEXT, "
                        "plan TEXT, status TEXT, saved_at TEXT, PRIMARY KEY (patient_id, plan_id))"
                    )
                    self._approvals_ready = True
                yield connection
        finally:
            connection.close()

    def _save(self, connection, patient_id: str, plan_id: str, plan: FastingPlan) -> None:
        connection.execute(
            "INSERT OR REPLACE INTO plans VALUES (?, ?, ?, ?, ?)",
            (
                patient_id,
                plan_id,
                plan.model_dump_json(),
                plan.status.value,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

    def save_draft(self, patient_id: str, plan_id: str, plan: FastingPlan) -> FastingPlan:
        saved = self.saved_plan(patient_id, plan_id)
        if (
            saved is not None
            and saved.status is PlanStatus.APPROVED
            and _content(saved) == _content(plan)
        ):
            return saved
        draft = _as_draft(plan)
        with self._connect() as connection:
            self._save(connection, patient_id, plan_id, draft)
        return draft

    def approve(self, patient_id: str, plan_id: str, plan: FastingPlan, doctor: str) -> FastingPlan:
        approved = plan.model_copy(
            update={
                "status": PlanStatus.APPROVED,
                "approved_by": doctor,
                "approved_on": date.today(),
            }
        )
        with self._connect() as connection:
            # Any earlier approval of another plan for this patient goes back to a draft.
            for other_id, other in self._saved(connection, patient_id).items():
                if other_id != plan_id and other.status is PlanStatus.APPROVED:
                    self._save(connection, patient_id, other_id, _as_draft(other))
            self._save(connection, patient_id, plan_id, approved)
        return approved

    def _saved(self, connection, patient_id: str) -> dict[str, FastingPlan]:
        rows = connection.execute(
            "SELECT plan_id, plan FROM plans WHERE patient_id = ? ORDER BY plan_id", (patient_id,)
        ).fetchall()
        return {plan_id: FastingPlan.model_validate_json(plan) for plan_id, plan in rows}

    def saved_plans(self, patient_id: str) -> dict[str, FastingPlan]:
        with self._connect() as connection:
            return self._saved(connection, patient_id)

    def saved_plan(self, patient_id: str, plan_id: str) -> FastingPlan | None:
        return self.saved_plans(patient_id).get(plan_id)

    def approved_plan(self, patient_id: str, plan_id: str) -> FastingPlan | None:
        plan = self.saved_plan(patient_id, plan_id)
        return plan if plan is not None and plan.status is PlanStatus.APPROVED else None

    def clear_saved_plans(self) -> int:
        """Removes every saved plan and approval, and returns the number removed."""
        with self._connect() as connection:
            return connection.execute("DELETE FROM plans").rowcount

    def plan_status(self, patient_id: str) -> str:
        """The plan status for the patient list: "not_started", "draft" or "approved"."""
        plans = self.saved_plans(patient_id).values()
        if any(p.status is PlanStatus.APPROVED for p in plans):
            return "approved"
        return "draft" if plans else "not_started"


STORE = DemoStore()

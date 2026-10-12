from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from rozmarra.api import store
from rozmarra.api.main import app
from rozmarra.config import MODELS_DIR

pytestmark = pytest.mark.skipif(
    not (MODELS_DIR / "e1.json").exists(), reason="The trained models are missing."
)
client = TestClient(app)


@pytest.fixture(autouse=True)
def separate_approvals(tmp_path, monkeypatch):
    """Keep test approvals out of the demo's approval file."""
    monkeypatch.setattr(store, "APPROVALS_FILE", tmp_path / "approvals.sqlite")
    monkeypatch.setattr(store.STORE, "_approvals_ready", False)


def test_the_patient_list_is_sorted_by_risk_and_labelled_synthetic():
    rows = client.get("/api/patients").json()
    assert [r["patient_id"] for r in rows if r["patient_id"]] and len(rows) == 4
    chances = [r["chance_of_low_during_fast"]["value"] for r in rows]
    assert chances == sorted(chances, reverse=True)
    assert all(r["source"] == "synthetic" for r in rows)
    sunita = next(r for r in rows if r["patient_id"] == "SY-0001")
    assert sunita["label"] == "Sunita Sharma, Age 54"
    assert sunita["fast_date_text"] == "28 October 2026"
    assert sunita["chance_of_low_during_fast"]["word"] in {"Low", "Moderate", "High"}


def test_a_patient_record_includes_the_cyp2c9_sentence():
    body = client.get("/api/patients/SY-0001").json()
    assert body["cyp2c9"]["genotype"] == "*1/*3"
    assert "longer than usual" in body["cyp2c9"]["sentence"]
    assert any("synthetic" in s for s in body["data_sources"])
    assert client.get("/api/patients/SY-9999").status_code == 404


def test_the_idf_dar_endpoint_gives_the_expected_totals():
    ramesh = client.get("/api/patients/SY-0002/idf-dar").json()
    assert ramesh["total"] == 11 and ramesh["category"] == "high"
    assert ramesh["note"] is not None, "Navratri is not Ramadan, so the approximation note shows."
    abdul = client.get("/api/patients/SY-0003/idf-dar").json()
    assert abdul["total"] == 8.5 and abdul["note"] is None


def test_the_twin_endpoint_describes_the_donor_and_the_parameters():
    body = client.get("/api/patients/SY-0001/twin").json()
    assert body["donor"]["source"] == "real_open"
    assert len(body["parameters"]) == 6
    assert body["fixed"]["cyp2c9_clearance_factor"] == pytest.approx(0.65)


def test_a_simulation_returns_a_curve_a_summary_and_the_caution():
    plan = client.get("/api/patients/SY-0001/plans/default").json()
    body = client.post("/api/patients/SY-0001/simulate", json=plan).json()
    curve = body["curve"]
    assert len(curve["times"]) == len(curve["p50"]) == len(curve["average_patient"])
    summary = body["summary"]
    assert 0 <= summary["chance_of_low_during_fast"]["value"] <= 1
    assert summary["lowest_glucose_mg_dl"] > 30
    assert body["dehydration_caution"] is not None, "Sunita takes dapagliflozin on a dry fast."
    assert any("Ramadan" in note for note in body["notes"])


def test_two_plans_can_be_compared():
    plan_a = client.get("/api/patients/SY-0001/plans/default").json()
    plan_b = {**plan_a, "plan_name": "Plan B: lower glimepiride dose"}
    plan_b["medicines"] = [
        {**m, "dose": 1} if m["name"] == "glimepiride" else m for m in plan_a["medicines"]
    ]
    body = client.post(
        "/api/patients/SY-0001/compare", json={"plan_a": plan_a, "plan_b": plan_b}
    ).json()
    assert set(body) == {"plan_a", "plan_b"}
    low_a = body["plan_a"]["summary"]["lowest_glucose_mg_dl"]
    low_b = body["plan_b"]["summary"]["lowest_glucose_mg_dl"]
    assert low_b >= low_a


def test_the_replay_gives_a_timeline_and_a_moment():
    overview = client.get("/api/patients/SY-0002/replay").json()
    assert len(overview["times"]) == len(overview["chances"]) > 10
    moment = datetime.fromisoformat(overview["fast_start"]) + timedelta(hours=8)
    body = client.get("/api/patients/SY-0002/replay", params={"at": moment.isoformat()}).json()
    assert body["source"] == "synthetic"
    if body["enough_data"]:
        assert 0 <= body["chance_of_low_next_60_min"]["value"] <= 1
        assert len(body["forecast"]["times"]) == len(body["forecast"]["p50"])
        assert all(r["en"].endswith(".") for r in body["reasons"])
    else:
        assert "not enough recent CGM data" in body["message"]


def test_a_plan_must_be_approved_before_printing():
    plan = client.get("/api/patients/SY-0003/plans/default").json()
    assert client.get("/api/patients/SY-0003/plans/plan-a/document").status_code == 409
    response = client.post(
        "/api/patients/SY-0003/plans/plan-a/approve",
        json={"doctor_name": "Ananya Rao", "plan": plan},
    )
    assert response.status_code == 200
    assert response.json()["approval_text"].startswith("Approved by Dr Ananya Rao on ")
    statuses = {r["patient_id"]: r["plan_status"] for r in client.get("/api/patients").json()}
    assert statuses["SY-0003"] == "Approved"
    empty = client.post(
        "/api/patients/SY-0003/plans/plan-a/approve", json={"doctor_name": " ", "plan": plan}
    )
    assert empty.status_code == 422


def test_the_templates_and_the_model_card_are_available():
    assert len(client.get("/api/templates").json()) == 10
    card = client.get("/api/model-card").json()
    assert card["limitations"] and card["data_sources"]
    assert "metrics" in card

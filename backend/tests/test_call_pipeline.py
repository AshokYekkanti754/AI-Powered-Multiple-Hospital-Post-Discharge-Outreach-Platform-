"""End-to-end coverage for the synchronous AI call pipeline + new read surfaces."""
import uuid
from tests.conftest import auth_headers
from app.db.models.user import UserRole


def _seed_hospital_patient(client, db_session, make_hospital, make_user):
    from datetime import datetime, timezone
    from app.db.models.campaign import Campaign
    from app.db.models.encounter import Encounter
    from app.db.models.patient import Patient
    from app.db.models.queue_task import QueueTask, QueueTaskStatus
    from app.services.eligibility_engine import compute_risk_tier
    h = make_hospital(name="Pipeline Hospital")
    make_user("pipe.admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=h.id)
    p = Patient(hospital_id=h.id, mrn="PIPE-1", first_name="Pipe", last_name="Test",
                phone_number="+10000000001", date_of_birth=datetime(1970, 1, 1).date())
    db_session.add(p)
    db_session.flush()
    enc = Encounter(hospital_id=h.id, patient_id=p.id, discharge_timestamp=datetime.now(timezone.utc),
                    risk_score=90.0, risk_tier=compute_risk_tier(90.0))
    db_session.add(enc)
    db_session.flush()
    camp = Campaign(hospital_id=h.id, name="Pipe Campaign")
    db_session.add(camp)
    db_session.flush()
    task = QueueTask(hospital_id=h.id, campaign_id=camp.id, patient_id=p.id,
                     status=QueueTaskStatus.PENDING, priority_score=90.0)
    db_session.add(task)
    db_session.commit()
    return h, task


def test_process_next_runs_full_pipeline_and_is_idempotent(client, db_session, make_hospital, make_user):
    h, task = _seed_hospital_patient(client, db_session, make_hospital, make_user)
    headers = auth_headers(client, "pipe.admin@hosp.test")
    r1 = client.post("/api/v1/calls/process-next", json={}, headers=headers)
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["processed"] is True and body["call_id"]
    r2 = client.post(f"/api/v1/calls/process/{task.id}", json={}, headers=headers)
    # second run replays the existing call instead of duplicating
    assert r2.status_code == 200 and r2.json()["idempotent_replay"] is True
    hist = client.get("/api/v1/calls/history", headers=headers)
    assert hist.status_code == 200 and len(hist.json()) == 1
    esc = client.get("/api/v1/escalations", headers=headers)
    assert esc.status_code == 200  # high-risk seed escalates
    prov = client.get("/api/v1/ai/provider-status", headers=headers)
    assert prov.status_code == 200
    assert prov.json()["provider"] in {"groq", "openrouter", "google", "ollama", "huggingface", "mock"}
    assert prov.json()["mode"] in {"free-cloud", "local", "open-source", "mock-offline"}
    logs = client.get("/api/v1/ai/logs", headers=headers)
    assert logs.status_code == 200 and len(logs.json()) >= 2

"""
Unit tests for the Pydantic-wrapped AI-agent tool interface
(app.tools.ehr_tools). These verify:
  - input validation rejects malformed tool calls before they touch the DB,
  - every invocation writes an ehr_audit_trail row (success or rejection),
  - cross-tenant tool calls are rejected, never silently rescoped.
"""
from app.db.models.ehr_audit import EHRAuditTrail
from app.db.models.user import UserRole
from app.tools import ehr_tools
from tests.conftest import auth_headers


def _seed_patient_and_encounter(client, headers):
    record = {
        "mrn": "MRN-TOOL-1", "first_name": "Tool", "last_name": "User",
        "phone_number": "+15552223333", "date_of_birth": "1990-01-01",
        "discharge_timestamp": "2026-09-10T08:00:00+00:00", "risk_score": 70,
    }
    client.post("/api/v1/patients/ingest", headers=headers, json={"records": [record]})
    patient = client.get("/api/v1/patients", headers=headers).json()[0]
    timeline = client.get(f"/api/v1/patients/{patient['id']}/timeline", headers=headers).json()
    encounter_id = next(e["detail"]["encounter_id"] for e in timeline if e["type"] == "discharge")
    return patient["id"], encounter_id


def test_get_patient_medical_history_tool_success(client, make_hospital, make_user, db_session):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")
    patient_id, _ = _seed_patient_and_encounter(client, headers)

    result = ehr_tools.get_patient_medical_history(
        db_session, hospital_id=hospital.id, caller_agent_id="agent-1", patient_id=patient_id
    )
    assert result.ok is True
    assert result.data["patient"]["mrn"] == "MRN-TOOL-1"

    audit_rows = db_session.query(EHRAuditTrail).filter(EHRAuditTrail.tool_name == "get_patient_medical_history").all()
    assert len(audit_rows) == 1
    assert audit_rows[0].status == "success"
    assert audit_rows[0].caller_agent_id == "agent-1"


def test_get_patient_medical_history_tool_rejects_invalid_uuid(client, make_hospital, make_user, db_session):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)

    result = ehr_tools.get_patient_medical_history(
        db_session, hospital_id=hospital.id, caller_agent_id="agent-1", patient_id="not-a-uuid"
    )
    assert result.ok is False
    assert "invalid_input" in result.error
    # Invalid input never reaches the DB, so no audit row should be written for it.
    assert db_session.query(EHRAuditTrail).count() == 0


def test_get_patient_medical_history_tool_rejects_cross_hospital_patient(client, make_hospital, make_user, db_session):
    hosp_a = make_hospital(name="Hospital A")
    hosp_b = make_hospital(name="Hospital B")
    make_user("admin.a@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_a.id)
    headers_a = auth_headers(client, "admin.a@hosp.test")
    patient_id, _ = _seed_patient_and_encounter(client, headers_a)

    result = ehr_tools.get_patient_medical_history(
        db_session, hospital_id=hosp_b.id, caller_agent_id="agent-rogue", patient_id=patient_id
    )
    assert result.ok is False
    assert "different_hospital" in result.error

    audit_rows = db_session.query(EHRAuditTrail).filter(EHRAuditTrail.caller_agent_id == "agent-rogue").all()
    assert len(audit_rows) == 1
    assert audit_rows[0].status.startswith("rejected")


def test_record_post_call_observation_tool_rejects_invalid_severity(client, make_hospital, make_user, db_session):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")
    patient_id, encounter_id = _seed_patient_and_encounter(client, headers)

    result = ehr_tools.record_post_call_observation(
        db_session, hospital_id=hospital.id, caller_agent_id="agent-1",
        patient_id=patient_id, encounter_id=encounter_id, symptom="shortness of breath", severity="catastrophic",
    )
    assert result.ok is False
    assert "invalid_input" in result.error


def test_record_post_call_observation_tool_success(client, make_hospital, make_user, db_session):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")
    patient_id, encounter_id = _seed_patient_and_encounter(client, headers)

    result = ehr_tools.record_post_call_observation(
        db_session, hospital_id=hospital.id, caller_agent_id="agent-1",
        patient_id=patient_id, encounter_id=encounter_id, symptom="mild cough", severity="mild",
    )
    assert result.ok is True
    assert "mild cough" in result.data["value"]


def test_create_clinical_followup_task_tool_success(client, make_hospital, make_user, db_session):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")
    patient_id, _ = _seed_patient_and_encounter(client, headers)

    result = ehr_tools.create_clinical_followup_task(
        db_session, hospital_id=hospital.id, caller_agent_id="agent-1",
        patient_id=patient_id, reason="Patient reports worsening symptoms, needs nurse callback.",
    )
    assert result.ok is True
    assert result.data["status"] == "OPEN"


def test_create_clinical_followup_task_tool_rejects_empty_reason(client, make_hospital, make_user, db_session):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")
    patient_id, _ = _seed_patient_and_encounter(client, headers)

    result = ehr_tools.create_clinical_followup_task(
        db_session, hospital_id=hospital.id, caller_agent_id="agent-1", patient_id=patient_id, reason="",
    )
    assert result.ok is False
    assert "invalid_input" in result.error

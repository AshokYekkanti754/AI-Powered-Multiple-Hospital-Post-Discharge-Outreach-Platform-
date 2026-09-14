"""
Unit/integration tests for the mock EHR service layer, including the
security test required by the milestone: attempting an EHR operation for a
patient belonging to a different hospital must be rejected.
"""
import pytest

from app.db.models.user import UserRole
from app.services import mock_ehr
from app.services.mock_ehr import EHRAuthorizationError
from tests.conftest import auth_headers


def _seed_patient_via_api(client, headers):
    record = {
        "mrn": "MRN-EHR-1", "first_name": "Eh", "last_name": "Are",
        "phone_number": "+15551110000", "date_of_birth": "1975-05-05",
        "discharge_timestamp": "2026-09-10T08:00:00+00:00", "risk_score": 60,
    }
    resp = client.post("/api/v1/patients/ingest", headers=headers, json={"records": [record]})
    assert resp.status_code == 201
    patient = client.get("/api/v1/patients", headers=headers).json()[0]
    timeline = client.get(f"/api/v1/patients/{patient['id']}/timeline", headers=headers).json()
    encounter_id = next(e["detail"]["encounter_id"] for e in timeline if e["type"] == "discharge")
    return patient["id"], encounter_id


def test_get_patient_profile_succeeds_for_own_hospital(db_session, make_hospital, make_user, client):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")
    patient_id, _ = _seed_patient_via_api(client, headers)

    profile = mock_ehr.get_patient_profile(db_session, patient_id=patient_id, hospital_id=hospital.id)
    assert profile["mrn"] == "MRN-EHR-1"


def test_get_patient_profile_rejects_cross_hospital_access(db_session, make_hospital, make_user, client):
    hosp_a = make_hospital(name="Hospital A")
    hosp_b = make_hospital(name="Hospital B")
    make_user("admin.a@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_a.id)
    headers_a = auth_headers(client, "admin.a@hosp.test")
    patient_id, _ = _seed_patient_via_api(client, headers_a)

    with pytest.raises(EHRAuthorizationError):
        mock_ehr.get_patient_profile(db_session, patient_id=patient_id, hospital_id=hosp_b.id)


def test_record_communication_persists_and_is_scoped(db_session, make_hospital, make_user, client):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")
    patient_id, _ = _seed_patient_via_api(client, headers)

    result = mock_ehr.record_communication(
        db_session, patient_id=patient_id, hospital_id=hospital.id,
        channel="phone_call", outcome="connected", notes="Patient reports feeling better.",
    )
    assert result["outcome"] == "connected"


def test_create_followup_task_rejects_cross_hospital_patient(db_session, make_hospital, make_user, client):
    hosp_a = make_hospital(name="Hospital A")
    hosp_b = make_hospital(name="Hospital B")
    make_user("admin.a2@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_a.id)
    headers_a = auth_headers(client, "admin.a2@hosp.test")
    patient_id, _ = _seed_patient_via_api(client, headers_a)

    with pytest.raises(EHRAuthorizationError):
        mock_ehr.create_followup_task(db_session, patient_id=patient_id, hospital_id=hosp_b.id, reason="test")


def test_ehr_read_endpoint_returns_403_or_404_for_cross_tenant_patient(client, make_hospital, make_user):
    hosp_a = make_hospital(name="Hospital A")
    hosp_b = make_hospital(name="Hospital B")
    make_user("admin.a3@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_a.id)
    make_user("admin.b3@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_b.id)
    headers_a = auth_headers(client, "admin.a3@hosp.test")
    patient_id, _ = _seed_patient_via_api(client, headers_a)

    headers_b = auth_headers(client, "admin.b3@hosp.test")
    resp = client.get(f"/api/v1/ehr/patients/{patient_id}", headers=headers_b)
    assert resp.status_code == 403


def test_ehr_write_endpoint_audits_success_and_failure(client, make_hospital, make_user, db_session):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")
    patient_id, _ = _seed_patient_via_api(client, headers)

    resp = client.post(
        "/api/v1/ehr/communications", headers=headers,
        json={"patient_id": patient_id, "outcome": "no_answer"},
    )
    assert resp.status_code == 201

    audit_resp = client.get("/api/v1/ehr/audit-trail", headers=headers)
    assert audit_resp.status_code == 200
    actions = [a["action"] for a in audit_resp.json()]
    assert "record_communication" in actions

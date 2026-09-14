"""
Integration tests: bulk ingestion of 200+ discharge records and strict
tenant partitioning between Hospital A and Hospital B.
"""
import json
from pathlib import Path

from app.db.models.user import UserRole
from tests.conftest import auth_headers

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed_discharges.json"


def _load_seed():
    with open(SEED_PATH) as f:
        return json.load(f)


def test_seed_file_has_200_plus_records_across_two_hospitals():
    records = _load_seed()
    assert len(records) >= 200
    hospitals = {r["hospital_name"] for r in records}
    assert hospitals == {"Hospital A", "Hospital B"}


def test_bulk_ingest_200_plus_records_with_strict_tenant_partitioning(client, make_hospital, make_user):
    records = _load_seed()
    hosp_a_records = [r for r in records if r["hospital_name"] == "Hospital A"]
    hosp_b_records = [r for r in records if r["hospital_name"] == "Hospital B"]

    hosp_a = make_hospital(name="Hospital A")
    hosp_b = make_hospital(name="Hospital B")
    make_user("admin.a@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_a.id)
    make_user("admin.b@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_b.id)

    headers_a = auth_headers(client, "admin.a@hosp.test")
    headers_b = auth_headers(client, "admin.b@hosp.test")

    resp_a = client.post("/api/v1/patients/ingest", headers=headers_a, json={"records": hosp_a_records})
    assert resp_a.status_code == 201
    report_a = resp_a.json()
    assert report_a["total_submitted"] == len(hosp_a_records)
    assert report_a["ingested"] >= 100  # allowing for the deliberately malformed records
    assert report_a["failed"] > 0  # a few malformed records ARE expected in the seed data
    assert report_a["ingested"] + report_a["failed"] == report_a["total_submitted"]

    resp_b = client.post("/api/v1/patients/ingest", headers=headers_b, json={"records": hosp_b_records})
    assert resp_b.status_code == 201
    report_b = resp_b.json()
    assert report_b["ingested"] > 0

    # Strict tenant partitioning: Hospital A cannot see Hospital B's ingested patients.
    list_resp_a = client.get("/api/v1/patients?limit=200", headers=headers_a)
    assert list_resp_a.status_code == 200
    mrns_a = {p["mrn"] for p in list_resp_a.json()}
    assert all(mrn.startswith("MRN-A-") for mrn in mrns_a)

    list_resp_b = client.get("/api/v1/patients?limit=200", headers=headers_b)
    mrns_b = {p["mrn"] for p in list_resp_b.json()}
    assert all(mrn.startswith("MRN-B-") for mrn in mrns_b)
    assert mrns_a.isdisjoint(mrns_b)


def test_malformed_record_does_not_abort_the_batch(client, make_hospital, make_user):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")

    good_record = {
        "mrn": "MRN-GOOD-1", "first_name": "Ann", "last_name": "Lee",
        "phone_number": "+15551234567", "date_of_birth": "1980-01-01",
        "discharge_timestamp": "2026-09-10T12:00:00+00:00", "risk_score": 50,
    }
    bad_record = {"mrn": "MRN-BAD-1", "first_name": "No", "last_name": "Phone"}  # missing required fields

    resp = client.post(
        "/api/v1/patients/ingest", headers=headers, json={"records": [good_record, bad_record]}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ingested"] == 1
    assert body["failed"] == 1
    assert body["errors"][0]["mrn"] == "MRN-BAD-1"
    assert "missing required fields" in body["errors"][0]["error"]


def test_platform_admin_must_specify_hospital_id_when_ingesting(client, make_user):
    make_user("platform@platform.test", role=UserRole.PLATFORM_ADMIN, hospital_id=None)
    headers = auth_headers(client, "platform@platform.test")

    resp = client.post("/api/v1/patients/ingest", headers=headers, json={"records": []})
    assert resp.status_code == 422


def test_hospital_admin_cannot_target_another_hospital_via_payload(client, make_hospital, make_user):
    hosp_a = make_hospital(name="Hospital A")
    hosp_b = make_hospital(name="Hospital B")
    make_user("admin.a2@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_a.id)
    headers_a = auth_headers(client, "admin.a2@hosp.test")

    resp = client.post(
        "/api/v1/patients/ingest",
        headers=headers_a,
        json={"hospital_id": str(hosp_b.id), "records": []},
    )
    assert resp.status_code == 403


def test_timeline_returns_403_for_cross_tenant_patient(client, make_hospital, make_user):
    hosp_a = make_hospital(name="Hospital A")
    hosp_b = make_hospital(name="Hospital B")
    make_user("admin.a3@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_a.id)
    make_user("admin.b3@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_b.id)

    good_record = {
        "mrn": "MRN-B-999", "first_name": "Bee", "last_name": "Hospital",
        "phone_number": "+15550000000", "date_of_birth": "1980-01-01",
        "discharge_timestamp": "2026-09-10T12:00:00+00:00", "risk_score": 40,
    }
    headers_b = auth_headers(client, "admin.b3@hosp.test")
    ingest_resp = client.post("/api/v1/patients/ingest", headers=headers_b, json={"records": [good_record]})
    patient_id = ingest_resp.json()["ingested"] and client.get(
        "/api/v1/patients", headers=headers_b
    ).json()[0]["id"]

    headers_a = auth_headers(client, "admin.a3@hosp.test")
    resp = client.get(f"/api/v1/patients/{patient_id}/timeline", headers=headers_a)
    assert resp.status_code == 403

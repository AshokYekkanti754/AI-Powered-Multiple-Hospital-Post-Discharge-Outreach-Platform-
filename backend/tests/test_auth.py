"""
Unit tests: password hashing + JWT issuance/validation.
Integration tests: /api/v1/auth/login behavior.
"""
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.models.user import UserRole
from tests.conftest import auth_headers


def test_password_hash_and_verify_roundtrip():
    hashed = hash_password("Sup3rSecret!")
    assert hashed != "Sup3rSecret!"
    assert verify_password("Sup3rSecret!", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_jwt_issuance_and_decoding_roundtrip():
    token = create_access_token(user_id="user-123", role="HOSPITAL_ADMIN", hospital_id="hosp-1")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "HOSPITAL_ADMIN"
    assert payload["hospital_id"] == "hosp-1"


def test_jwt_decoding_rejects_tampered_token():
    token = create_access_token(user_id="user-123", role="HOSPITAL_ADMIN", hospital_id="hosp-1")
    tampered = token[:-2] + "xx"
    with pytest.raises(ValueError):
        decode_access_token(tampered)


def test_login_success(client, make_hospital, make_user):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)

    resp = client.post(
        "/api/v1/auth/login", json={"email": "admin@hosp.test", "password": "Password123!"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client, make_hospital, make_user):
    hospital = make_hospital()
    make_user("admin2@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)

    resp = client.post(
        "/api/v1/auth/login", json={"email": "admin2@hosp.test", "password": "WrongPassword"}
    )
    assert resp.status_code == 401


def test_login_unknown_email_returns_401(client):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "nobody@nowhere.test", "password": "whatever"}
    )
    assert resp.status_code == 401


def test_protected_endpoint_without_token_returns_401(client):
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401


def test_protected_endpoint_with_invalid_token_returns_401(client):
    resp = client.get("/api/v1/users", headers={"Authorization": "Bearer garbage.token.here"})
    assert resp.status_code == 401

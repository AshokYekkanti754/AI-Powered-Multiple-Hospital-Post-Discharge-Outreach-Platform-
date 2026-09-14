"""
Test fixtures.

Forces DATABASE_URL to an in-memory SQLite DB *before* any app module is
imported, so tests never touch a real Postgres instance and are fully
self-contained / parallel-safe.
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def make_hospital(db_session):
    from app.db.models.hospital import Hospital

    def _make(name="Test Hospital", **kwargs):
        h = Hospital(name=name, **kwargs)
        db_session.add(h)
        db_session.commit()
        db_session.refresh(h)
        return h

    return _make


@pytest.fixture()
def make_user(db_session):
    from app.core.security import hash_password
    from app.db.models.user import User, UserRole

    def _make(email, role=UserRole.HOSPITAL_ADMIN, hospital_id=None, password="Password123!"):
        u = User(
            email=email,
            hashed_password=hash_password(password),
            full_name="Test User",
            role=role,
            hospital_id=hospital_id,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        return u

    return _make


def auth_headers(client, email, password="Password123!"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

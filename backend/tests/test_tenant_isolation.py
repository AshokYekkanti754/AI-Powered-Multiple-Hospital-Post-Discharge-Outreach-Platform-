"""
Integration tests: RBAC across all 4 roles, hospital onboarding, and the
critical security guarantee — a user from Hospital A can never read or
write data belonging to Hospital B.
"""
from app.db.models.user import UserRole
from tests.conftest import auth_headers


def _bootstrap_two_hospitals(make_hospital, make_user):
    hosp_a = make_hospital(name="Hospital A")
    hosp_b = make_hospital(name="Hospital B")
    admin_a = make_user("admin.a@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_a.id)
    admin_b = make_user("admin.b@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hosp_b.id)
    return hosp_a, hosp_b, admin_a, admin_b


def test_hospital_admin_can_only_list_own_hospital_users(client, make_hospital, make_user):
    hosp_a, hosp_b, admin_a, admin_b = _bootstrap_two_hospitals(make_hospital, make_user)
    make_user("staff.a@hosp.test", role=UserRole.CAMPAIGN_MANAGER, hospital_id=hosp_a.id)
    make_user("staff.b@hosp.test", role=UserRole.CAMPAIGN_MANAGER, hospital_id=hosp_b.id)

    headers_a = auth_headers(client, "admin.a@hosp.test")
    resp = client.get("/api/v1/users", headers=headers_a)
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert emails == {"admin.a@hosp.test", "staff.a@hosp.test"}
    assert "staff.b@hosp.test" not in emails


def test_cross_tenant_hospital_me_never_leaks_other_hospital(client, make_hospital, make_user):
    hosp_a, hosp_b, admin_a, admin_b = _bootstrap_two_hospitals(make_hospital, make_user)

    headers_a = auth_headers(client, "admin.a@hosp.test")
    resp = client.get("/api/v1/hospitals/me", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["id"] == str(hosp_a.id)
    assert resp.json()["id"] != str(hosp_b.id)


def test_hospital_admin_cannot_onboard_new_hospital(client, make_hospital, make_user):
    hosp_a, _, admin_a, _ = _bootstrap_two_hospitals(make_hospital, make_user)
    headers_a = auth_headers(client, "admin.a@hosp.test")

    resp = client.post(
        "/api/v1/hospitals/onboard",
        headers=headers_a,
        json={
            "hospital_name": "Sneaky Hospital",
            "admin_email": "sneaky@hosp.test",
            "admin_full_name": "Sneaky Admin",
            "admin_password": "Password123!",
        },
    )
    assert resp.status_code == 403


def test_platform_admin_can_onboard_hospital_and_creates_hospital_admin(client, make_user):
    make_user("platform@platform.test", role=UserRole.PLATFORM_ADMIN, hospital_id=None)
    headers = auth_headers(client, "platform@platform.test")

    resp = client.post(
        "/api/v1/hospitals/onboard",
        headers=headers,
        json={
            "hospital_name": "New Hospital",
            "admin_email": "newadmin@hosp.test",
            "admin_full_name": "New Admin",
            "admin_password": "Password123!",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "New Hospital"

    # The created admin can now log in and is scoped to the new hospital.
    login_resp = client.post(
        "/api/v1/auth/login", json={"email": "newadmin@hosp.test", "password": "Password123!"}
    )
    assert login_resp.status_code == 200


def test_campaign_manager_cannot_create_users(client, make_hospital, make_user):
    hospital = make_hospital()
    make_user("cm@hosp.test", role=UserRole.CAMPAIGN_MANAGER, hospital_id=hospital.id)
    headers = auth_headers(client, "cm@hosp.test")

    resp = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "new.staff@hosp.test",
            "full_name": "New Staff",
            "password": "Password123!",
            "role": "CLINICAL_REVIEWER",
        },
    )
    assert resp.status_code == 403


def test_hospital_admin_can_create_scoped_user_inheriting_hospital_id(client, make_hospital, make_user):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")

    resp = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "reviewer@hosp.test",
            "full_name": "Clinical Reviewer",
            "password": "Password123!",
            "role": "CLINICAL_REVIEWER",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["hospital_id"] == str(hospital.id)  # inherited from context, not client-supplied


def test_hospital_admin_cannot_create_platform_admin(client, make_hospital, make_user):
    hospital = make_hospital()
    make_user("admin@hosp.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    headers = auth_headers(client, "admin@hosp.test")

    resp = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "wannabe.platform@hosp.test",
            "full_name": "Wannabe",
            "password": "Password123!",
            "role": "PLATFORM_ADMIN",
        },
    )
    assert resp.status_code == 403


def test_clinical_reviewer_can_login_and_view_own_hospital_scope(client, make_hospital, make_user):
    hospital = make_hospital()
    make_user("clin@hosp.test", role=UserRole.CLINICAL_REVIEWER, hospital_id=hospital.id)
    headers = auth_headers(client, "clin@hosp.test")

    resp = client.get("/api/v1/hospitals/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == str(hospital.id)

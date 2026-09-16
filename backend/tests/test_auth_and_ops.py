import uuid

from app.models import User
from app.models.enums import MemberRole


def test_login_and_me(client, db_session):
    from app.core.security import hash_password
    from app.models import Organization, OrganizationMember

    org = Organization(name="Demo", slug="demo-auth")
    user = User(
        email="owner@example.com", hashed_password=hash_password("demo1234"), full_name="Demo Owner"
    )
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role=MemberRole.OWNER)
    )
    db_session.commit()

    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": "demo1234"})
    assert response.status_code == 200
    token = response.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == user.email
    assert me.json()["memberships"][0]["role"] == "owner"


def test_invalid_login_rejected(client, db_session):
    from app.core.security import hash_password

    db_session.add(
        User(
            email="owner@example.com",
            hashed_password=hash_password("demo1234"),
            full_name="Demo Owner",
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrongpass"}
    )
    assert response.status_code == 401


def test_execution_lookup_requires_org_membership(client, db_session):
    from app.core.security import create_access_token
    from app.models import Organization

    org = Organization(name="Demo", slug="demo-ops")
    user = User(email="owner2@example.com", hashed_password="unused", full_name="Owner")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.commit()
    execution_id = uuid.uuid4()

    # Membership intentionally omitted.
    token = create_access_token(str(user.id))
    res = client.get(
        f"/api/v1/ops/executions/{execution_id}?org_id={org.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_metrics_requires_auth(client):
    response = client.get("/api/v1/ops/metrics?org_id=00000000-0000-0000-0000-000000000000")
    assert response.status_code in {401, 403}


def test_demo_execution_endpoint_requires_auth(client):
    import uuid

    response = client.get(f"/api/v1/demo/executions/{uuid.uuid4()}?org_id={uuid.uuid4()}")
    assert response.status_code in {401, 403}


def test_demo_approval_endpoint_requires_auth(client):
    import uuid

    response = client.post(
        f"/api/v1/demo/approvals/{uuid.uuid4()}/decision?org_id={uuid.uuid4()}",
        json={"decision": "approved"},
    )
    assert response.status_code in {401, 403}

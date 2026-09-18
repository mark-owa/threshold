from app.core.security import create_access_token, hash_password
from app.models import Organization, OrganizationMember, User
from app.models.enums import MemberRole


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_registration_creates_isolated_trial_workspace(client, db_session):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "founder@example.com",
            "password": "strongpass123",
            "full_name": "Threshold Founder",
            "organization_name": "Example Operations",
            "organization_slug": "example-operations",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]

    org = db_session.query(Organization).filter_by(slug="example-operations").one()
    user = db_session.query(User).filter_by(email="founder@example.com").one()
    membership = (
        db_session.query(OrganizationMember)
        .filter_by(organization_id=org.id, user_id=user.id)
        .one()
    )
    assert org.plan == "trial"
    assert membership.role == MemberRole.OWNER
    assert body["organization_id"] == str(org.id)


def test_workspace_list_only_returns_authenticated_users_memberships(client, db_session):
    visible = Organization(name="Visible", slug="visible", plan="trial")
    hidden = Organization(name="Hidden", slug="hidden", plan="trial")
    user = User(
        email="member@example.com",
        hashed_password=hash_password("demo1234"),
        full_name="Member",
    )
    db_session.add_all([visible, hidden, user])
    db_session.flush()
    db_session.add(
        OrganizationMember(
            organization_id=visible.id,
            user_id=user.id,
            role=MemberRole.VIEWER,
        )
    )
    db_session.commit()

    response = client.get("/api/v1/organizations", headers=auth_header(user))
    assert response.status_code == 200
    assert [row["slug"] for row in response.json()] == ["visible"]


def test_authenticated_user_can_create_trial_workspace(client, db_session):
    user = User(
        email="owner3@example.com",
        hashed_password=hash_password("demo1234"),
        full_name="Owner Three",
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/organizations",
        headers=auth_header(user),
        json={"name": "Second Workspace", "slug": "second-workspace"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["plan"] == "trial"
    assert body["role"] == "owner"


def test_demo_scenarios_are_blocked_in_trial_workspaces(client, db_session):
    org = Organization(name="Customer", slug="customer-trial", plan="trial")
    user = User(
        email="customer@example.com",
        hashed_password=hash_password("demo1234"),
        full_name="Customer Owner",
    )
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role=MemberRole.OWNER)
    )
    db_session.commit()

    response = client.post(
        f"/api/v1/demo/run?org_id={org.id}",
        headers=auth_header(user),
        json={"scenario": "low_risk_refund"},
    )
    assert response.status_code == 403
    assert "demo workspaces" in response.json()["detail"].lower()


def test_workspace_product_endpoints_require_membership(client, db_session):
    org = Organization(name="Private", slug="private-space", plan="trial")
    user = User(
        email="outsider@example.com",
        hashed_password=hash_password("demo1234"),
        full_name="Outsider",
    )
    db_session.add_all([org, user])
    db_session.commit()

    response = client.get(
        f"/api/v1/workspace/policies?org_id={org.id}",
        headers=auth_header(user),
    )
    assert response.status_code == 403

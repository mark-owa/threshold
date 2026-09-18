import hashlib

from app.core.security import create_access_token
from app.models import Organization, OrganizationInvitation, OrganizationMember, Policy, User
from app.models.enums import MemberRole, RequestCategory


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def make_owner(db_session, *, slug="m2-workspace", email="owner-m2@example.com"):
    org = Organization(name="Milestone Two", slug=slug, plan="trial")
    user = User(email=email, hashed_password="unused", full_name="Owner")
    db_session.add_all([org, user])
    db_session.flush()
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=MemberRole.OWNER,
    )
    db_session.add(membership)
    db_session.commit()
    return org, user, membership


def test_owner_can_create_hashed_expiring_invitation(client, db_session):
    org, owner, _ = make_owner(db_session)
    response = client.post(
        f"/api/v1/organizations/{org.id}/invitations",
        headers=auth_header(owner),
        json={"email": "reviewer-m2@example.com", "role": "reviewer"},
    )
    assert response.status_code == 201
    body = response.json()
    raw_token = body["invitation_token"]
    invitation = db_session.query(OrganizationInvitation).filter_by(id=body["id"]).one()
    assert invitation.email == "reviewer-m2@example.com"
    assert invitation.role == MemberRole.REVIEWER
    assert invitation.token_hash != raw_token
    assert invitation.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def test_admin_cannot_invite_another_admin(client, db_session):
    org, _, _ = make_owner(db_session, slug="admin-boundary", email="owner-admin@example.com")
    admin = User(email="admin@example.com", hashed_password="unused", full_name="Admin")
    db_session.add(admin)
    db_session.flush()
    db_session.add(
        OrganizationMember(organization_id=org.id, user_id=admin.id, role=MemberRole.ADMIN)
    )
    db_session.commit()

    response = client.post(
        f"/api/v1/organizations/{org.id}/invitations",
        headers=auth_header(admin),
        json={"email": "second-admin@example.com", "role": "admin"},
    )
    assert response.status_code == 403


def test_last_owner_cannot_be_demoted(client, db_session):
    org, owner, membership = make_owner(
        db_session, slug="owner-protection", email="protected-owner@example.com"
    )
    response = client.patch(
        f"/api/v1/organizations/{org.id}/members/{membership.id}",
        headers=auth_header(owner),
        json={"role": "admin"},
    )
    assert response.status_code == 409
    assert "at least one owner" in response.json()["detail"].lower()


def test_owner_can_create_refund_policy_and_onboarding_reflects_it(client, db_session):
    org, owner, _ = make_owner(
        db_session, slug="policy-onboarding", email="policy-owner@example.com"
    )
    before = client.get(
        f"/api/v1/workspace/onboarding?org_id={org.id}", headers=auth_header(owner)
    )
    assert before.status_code == 200
    before_steps = {step["key"]: step for step in before.json()["steps"]}
    assert before_steps["refund_policy"]["complete"] is False

    update = client.put(
        f"/api/v1/workspace/refund-policy?org_id={org.id}",
        headers=auth_header(owner),
        json={
            "title": "Customer refund policy",
            "content": "Refunds are allowed for completed orders within thirty days.",
            "refund_window_days": 30,
            "max_auto_refund_usd": 75.50,
        },
    )
    assert update.status_code == 200
    policy = db_session.query(Policy).filter_by(
        organization_id=org.id, category=RequestCategory.REFUND_REQUEST
    ).one()
    assert policy.structured_rules == {
        "refund_window_days": 30,
        "max_auto_refund_usd": 75.5,
    }

    after = client.get(
        f"/api/v1/workspace/onboarding?org_id={org.id}", headers=auth_header(owner)
    )
    after_steps = {step["key"]: step for step in after.json()["steps"]}
    assert after_steps["refund_policy"]["complete"] is True

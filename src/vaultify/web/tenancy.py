"""Trusted organization-membership resolution for the Vaultify web layer."""

from flask import session
from flask_login import current_user, logout_user

from vaultify.models import Membership


def get_memberships_for_user(user_id):
    """Return memberships owned by one authenticated user in stable order."""
    return (
        Membership.query
        .filter_by(user_id=user_id)
        .order_by(Membership.id.asc())
        .all()
    )


def resolve_active_membership():
    """Resolve the active organization only from verified server-side membership."""
    if not current_user.is_authenticated:
        return None

    memberships = get_memberships_for_user(current_user.id)

    if not memberships:
        logout_user()
        session.pop("organization_id", None)
        return None

    selected_id = session.get("organization_id")

    for membership in memberships:
        if membership.organization_id == selected_id:
            return membership

    membership = memberships[0]
    session["organization_id"] = membership.organization_id
    return membership

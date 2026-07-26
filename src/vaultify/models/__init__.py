"""Core SQLAlchemy models extracted from the Vaultify golden notebook."""

import secrets
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from vaultify.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    memberships = db.relationship(
        "Membership",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def is_active(self):
        return self.is_active_account

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.String(80),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: f"tenant_{secrets.token_hex(12)}",
    )
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, index=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    memberships = db.relationship(
        "Membership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    documents = db.relationship(
        "Document",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class Membership(db.Model):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "organization_id",
            name="uq_membership_user_organization",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = db.Column(db.String(20), nullable=False, default="member")

    user = db.relationship("User", back_populates="memberships")
    organization = db.relationship("Organization", back_populates="memberships")


class Document(db.Model):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "document_hash",
            name="uq_document_organization_hash",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    storage_path = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(120), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    document_hash = db.Column(db.String(64), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="uploaded")
    chunk_count = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    indexed_at = db.Column(db.DateTime(timezone=True))

    organization = db.relationship("Organization", back_populates="documents")


class ConnectorCredential(db.Model):
    __tablename__ = "connector_credentials"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(
        db.String(120),
        nullable=False,
        default="Claude MCP Connector",
    )
    token_hash = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    token_prefix = db.Column(db.String(32), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)

    organization = db.relationship("Organization")


class QueryLog(db.Model):
    __tablename__ = "query_logs"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    source_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


__all__ = [
    "User",
    "Organization",
    "Membership",
    "Document",
    "ConnectorCredential",
    "QueryLog",
    "utc_now",
]

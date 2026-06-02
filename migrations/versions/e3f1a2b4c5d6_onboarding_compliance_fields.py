"""Add onboarding, compliance, and reporting fields

Revision ID: e3f1a2b4c5d6
Revises: d2cbb0605a5e
Create Date: 2026-05-21 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "e3f1a2b4c5d6"
down_revision: Union[str, None] = "d2cbb0605a5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── User compliance + onboarding fields ───────────────────────────────────
    op.add_column(
        "users", sa.Column("date_of_birth", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users", sa.Column("email_verification_token", sa.String(255), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("terms_version", sa.String(16), nullable=True))
    op.add_column(
        "users",
        sa.Column("location_consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users", sa.Column("password_reset_token", sa.String(255), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column(
            "password_reset_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )

    # ── UserPhoto CSAM tracking ───────────────────────────────────────────────
    op.add_column(
        "user_photos",
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Token blacklist for logout/session revocation ─────────────────────────
    op.create_table(
        "token_blacklist",
        sa.Column("jti", sa.String(255), nullable=False),
        sa.Column("blacklisted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
    )

    # ── User reports for FOSTA-SESTA compliance ───────────────────────────────
    op.create_table(
        "user_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("reported_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reported_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("user_reports")
    op.drop_table("token_blacklist")
    op.drop_column("user_photos", "reported_at")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_token")
    op.drop_column("users", "onboarding_completed_at")
    op.drop_column("users", "location_consent_at")
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "date_of_birth")

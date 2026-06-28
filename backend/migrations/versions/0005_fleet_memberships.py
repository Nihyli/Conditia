"""Fleet membership table for user-scoped access."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_fleet_memberships"
down_revision: str | Sequence[str] | None = "0004_timestamptz"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fleet_memberships",
        sa.Column("fleet_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.CheckConstraint(
            "role IN ('viewer','inspector','admin')",
            name="ck_fleet_membership_role",
        ),
        sa.ForeignKeyConstraint(["fleet_id"], ["fleets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("fleet_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("fleet_memberships")

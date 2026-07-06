"""Security hardening: per-fleet VIN uniqueness and finding resolved_by audit."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_security_hardening"
down_revision: str | Sequence[str] | None = "0007_analysis_job_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "findings" in inspector.get_table_names():
        finding_columns = {c["name"] for c in inspector.get_columns("findings")}
        if "resolved_by" not in finding_columns:
            op.add_column(
                "findings", sa.Column("resolved_by", sa.String(), nullable=True)
            )

    truck_uniques = {
        uc["name"]
        for uc in inspector.get_unique_constraints("trucks")
        if uc.get("column_names") == ["vin"]
    }
    for name in truck_uniques:
        op.drop_constraint(name, "trucks", type_="unique")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("trucks") as batch_op:
            batch_op.create_unique_constraint(
                "uq_truck_fleet_vin", ["fleet_id", "vin"]
            )
    else:
        op.create_unique_constraint(
            "uq_truck_fleet_vin", "trucks", ["fleet_id", "vin"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("trucks") as batch_op:
            batch_op.drop_constraint("uq_truck_fleet_vin", type_="unique")
            batch_op.create_unique_constraint("trucks_vin_key", ["vin"])
    else:
        op.drop_constraint("uq_truck_fleet_vin", "trucks", type_="unique")
        op.create_unique_constraint("trucks_vin_key", "trucks", ["vin"])
    inspector = sa.inspect(bind)
    if "findings" in inspector.get_table_names():
        finding_columns = {c["name"] for c in inspector.get_columns("findings")}
        if "resolved_by" in finding_columns:
            op.drop_column("findings", "resolved_by")

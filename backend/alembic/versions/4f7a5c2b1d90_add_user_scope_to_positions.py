"""add user scope to positions

Revision ID: 4f7a5c2b1d90
Revises: de4ce5d15def
Create Date: 2026-08-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f7a5c2b1d90"
down_revision: Union[str, None] = "de4ce5d15def"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    cols = inspector.get_columns(table_name)
    return any(c.get("name") == column_name for c in cols)


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    indexes = inspector.get_indexes(table_name)
    return any(i.get("name") == index_name for i in indexes)


def _has_fk(inspector: sa.Inspector, table_name: str, fk_name: str) -> bool:
    fks = inspector.get_foreign_keys(table_name)
    return any(fk.get("name") == fk_name for fk in fks)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "positions"):
        return

    if not _has_column(inspector, "positions", "user_id"):
        op.add_column("positions", sa.Column("user_id", sa.Integer(), nullable=True))

    if _has_table(inspector, "users") and not _has_fk(inspector, "positions", "fk_positions_user_id_users"):
        op.create_foreign_key(
            "fk_positions_user_id_users",
            "positions",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "positions", "ix_positions_user_id"):
        op.create_index("ix_positions_user_id", "positions", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "positions"):
        return

    if _has_index(inspector, "positions", "ix_positions_user_id"):
        op.drop_index("ix_positions_user_id", table_name="positions")

    if _has_fk(inspector, "positions", "fk_positions_user_id_users"):
        op.drop_constraint("fk_positions_user_id_users", "positions", type_="foreignkey")

    if _has_column(inspector, "positions", "user_id"):
        op.drop_column("positions", "user_id")

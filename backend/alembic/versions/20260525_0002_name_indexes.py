"""Add person and entity name indexes.

Revision ID: 20260525_0002
Revises: 20260523_0001
Create Date: 2026-05-25
"""

from __future__ import annotations

from alembic import op

revision = "20260525_0002"
down_revision = "20260523_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_person_name", "person", ["name"])
    op.create_index("ix_entity_name", "entity", ["name"])


def downgrade() -> None:
    op.drop_index("ix_entity_name", table_name="entity")
    op.drop_index("ix_person_name", table_name="person")

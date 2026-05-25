"""Initial schema.

Revision ID: 20260523_0001
Revises:
Create Date: 2026-05-23
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "20260523_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "self_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("bio", sa.Text()),
        sa.Column("communication_style", sa.Text()),
        sa.Column("sensitivities", sa.JSON()),
        sa.Column("goals", sa.JSON()),
        sa.Column("profile_json", sa.JSON()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("id = 1", name="ck_self_profile_single_row"),
    )

    op.create_table(
        "life_stage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text()),
        sa.Column("location", sa.Text()),
        sa.Column("started_at", sa.Date()),
        sa.Column("ended_at", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("sort_order", sa.Integer()),
    )

    op.create_table(
        "person",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("aliases", sa.JSON()),
        sa.Column("bio", sa.Text()),
        sa.Column("profile_json", sa.JSON()),
        sa.Column("photo_path", sa.Text()),
        sa.Column("importance", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "entity",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("bio", sa.Text()),
        sa.Column("profile_json", sa.JSON()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "entity_member",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entity.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text()),
        sa.Column("started_at", sa.Date()),
        sa.Column("ended_at", sa.Date()),
        sa.UniqueConstraint("entity_id", "person_id", name="uq_entity_member_entity_person"),
    )

    op.create_table(
        "relationship",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("from_type", sa.Text(), nullable=False),
        sa.Column("from_id", sa.Integer()),
        sa.Column("to_type", sa.Text(), nullable=False),
        sa.Column("to_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("role", sa.Text()),
        sa.Column("strength", sa.Integer()),
        sa.Column("status", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("started_at", sa.Date()),
        sa.Column("ended_at", sa.Date()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "person_stage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.Integer(), sa.ForeignKey("life_stage.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_in_stage", sa.Text()),
        sa.Column("started_at", sa.Date()),
        sa.Column("ended_at", sa.Date()),
        sa.UniqueConstraint("person_id", "stage_id", name="uq_person_stage_person_stage"),
    )

    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.Date()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("participants", sa.JSON()),
        sa.Column("source", sa.Text()),
        sa.Column("source_session_id", sa.Integer()),
        sa.Column("importance", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "chat_session",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("chat_model", sa.Text()),
        sa.Column("started_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ended_at", sa.TIMESTAMP()),
    )

    op.create_table(
        "chat_message",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_used", sa.JSON()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "extraction",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_session.id")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Integer()),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.REAL()),
        sa.Column("status", sa.Text(), server_default="pending"),
        sa.Column("applied_at", sa.TIMESTAMP()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "note",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Integer()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.Text()),
        sa.Column("source_file", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "app_setting",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.JSON()),
    )

    op.execute(
        """
        CREATE VIRTUAL TABLE person_fts USING fts5(
          name, aliases, bio, profile_json, content='person', content_rowid='id'
        )
        """
    )
    op.execute(
        """
        CREATE VIRTUAL TABLE entity_fts USING fts5(
          name, bio, profile_json, content='entity', content_rowid='id'
        )
        """
    )
    op.execute(
        """
        CREATE VIRTUAL TABLE note_fts USING fts5(
          content, content='note', content_rowid='id'
        )
        """
    )

    op.execute(
        """
        CREATE TRIGGER person_ai AFTER INSERT ON person BEGIN
          INSERT INTO person_fts(rowid, name, aliases, bio, profile_json)
          VALUES (new.id, new.name, new.aliases, new.bio, new.profile_json);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER person_ad AFTER DELETE ON person BEGIN
          INSERT INTO person_fts(person_fts, rowid, name, aliases, bio, profile_json)
          VALUES ('delete', old.id, old.name, old.aliases, old.bio, old.profile_json);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER person_au AFTER UPDATE ON person BEGIN
          INSERT INTO person_fts(person_fts, rowid, name, aliases, bio, profile_json)
          VALUES ('delete', old.id, old.name, old.aliases, old.bio, old.profile_json);
          INSERT INTO person_fts(rowid, name, aliases, bio, profile_json)
          VALUES (new.id, new.name, new.aliases, new.bio, new.profile_json);
        END
        """
    )

    op.execute(
        """
        CREATE TRIGGER entity_ai AFTER INSERT ON entity BEGIN
          INSERT INTO entity_fts(rowid, name, bio, profile_json)
          VALUES (new.id, new.name, new.bio, new.profile_json);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER entity_ad AFTER DELETE ON entity BEGIN
          INSERT INTO entity_fts(entity_fts, rowid, name, bio, profile_json)
          VALUES ('delete', old.id, old.name, old.bio, old.profile_json);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER entity_au AFTER UPDATE ON entity BEGIN
          INSERT INTO entity_fts(entity_fts, rowid, name, bio, profile_json)
          VALUES ('delete', old.id, old.name, old.bio, old.profile_json);
          INSERT INTO entity_fts(rowid, name, bio, profile_json)
          VALUES (new.id, new.name, new.bio, new.profile_json);
        END
        """
    )

    op.execute(
        """
        CREATE TRIGGER note_ai AFTER INSERT ON note BEGIN
          INSERT INTO note_fts(rowid, content) VALUES (new.id, new.content);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER note_ad AFTER DELETE ON note BEGIN
          INSERT INTO note_fts(note_fts, rowid, content)
          VALUES ('delete', old.id, old.content);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER note_au AFTER UPDATE ON note BEGIN
          INSERT INTO note_fts(note_fts, rowid, content)
          VALUES ('delete', old.id, old.content);
          INSERT INTO note_fts(rowid, content) VALUES (new.id, new.content);
        END
        """
    )

    defaults = {
        "chat_model": "anthropic/claude-sonnet-4-6",
        "extraction_model": "anthropic/claude-haiku-4-5-20251001",
        "auto_extract_threshold": 0.85,
        "auto_extract_kinds": ["event_new", "person_new", "note_new"],
        "mcp_enabled": True,
        "language": "zh-CN",
        "obsidian_export_path": None,
    }
    op.get_bind().execute(
        sa.text("INSERT INTO app_setting (key, value) VALUES (:key, :value)"),
        [
            {"key": key, "value": json.dumps(value, ensure_ascii=False)}
            for key, value in defaults.items()
        ],
    )


def downgrade() -> None:
    for trigger in (
        "note_au",
        "note_ad",
        "note_ai",
        "entity_au",
        "entity_ad",
        "entity_ai",
        "person_au",
        "person_ad",
        "person_ai",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")

    op.execute("DROP TABLE IF EXISTS note_fts")
    op.execute("DROP TABLE IF EXISTS entity_fts")
    op.execute("DROP TABLE IF EXISTS person_fts")

    for table in (
        "app_setting",
        "note",
        "extraction",
        "chat_message",
        "chat_session",
        "event",
        "person_stage",
        "relationship",
        "entity_member",
        "entity",
        "person",
        "life_stage",
        "self_profile",
    ):
        op.drop_table(table)

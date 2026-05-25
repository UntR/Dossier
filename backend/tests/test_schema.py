import json
import sqlite3

from alembic import command
from alembic.config import Config


def json_value(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def test_initial_migration_creates_schema_and_default_settings(tmp_path, monkeypatch):
    db_path = tmp_path / "dossier.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    config = Config("backend/alembic.ini")
    command.upgrade(config, "head")

    conn = sqlite3.connect(db_path)
    try:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        expected_tables = {
            "self_profile",
            "life_stage",
            "person",
            "entity",
            "entity_member",
            "relationship",
            "person_stage",
            "event",
            "chat_session",
            "chat_message",
            "extraction",
            "note",
            "app_setting",
            "person_fts",
            "entity_fts",
            "note_fts",
        }
        assert expected_tables.issubset(table_names)

        settings = {key: json_value(value) for key, value in conn.execute("SELECT key, value FROM app_setting")}
        assert settings["chat_model"] == "anthropic/claude-sonnet-4-6"
        assert settings["extraction_model"] == "anthropic/claude-haiku-4-5-20251001"
        assert settings["auto_extract_threshold"] == 0.85
        assert settings["auto_extract_kinds"] == [
            "event_new",
            "person_new",
            "note_new",
        ]
        assert settings["mcp_enabled"] is True
        assert settings["language"] == "zh-CN"
        assert settings["obsidian_export_path"] is None

        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode == "wal"

        person_indexes = {row[1] for row in conn.execute("PRAGMA index_list('person')")}
        entity_indexes = {row[1] for row in conn.execute("PRAGMA index_list('entity')")}
        assert "ix_person_name" in person_indexes
        assert "ix_entity_name" in entity_indexes
    finally:
        conn.close()

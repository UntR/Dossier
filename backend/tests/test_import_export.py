from __future__ import annotations

import io
import json
import os
import sqlite3
import zipfile
from pathlib import Path

from app.parsers.files import parse_import_file
from test_crud_api import unwrap


def test_import_file_and_llm_memory_create_pending_extractions(client):
    person = unwrap(client.post("/api/people", json={"name": "老板"}))

    file_result = unwrap(
        client.post(
            "/api/import/file",
            data={"target_type": "person", "target_id": str(person["id"])},
            files={"file": ("memory.txt", "老板喜欢结果导向".encode("utf-8"), "text/plain")},
        )
    )
    assert file_result["created"] == 1

    prompt = unwrap(client.get("/api/import/llm-prompt-template"))
    assert "people" in prompt["template"]
    assert "events" in prompt["template"]

    llm_result = unwrap(
        client.post(
            "/api/import/llm-memory",
            json={
                "json": """
                {
                  "people": [{"name": "张三", "aliases": ["小张"], "bio": "前同事"}],
                  "entities": [{"type": "company", "name": "字节跳动", "bio": "工作单位"}],
                  "events": [{"occurred_at": "2026-05-23", "title": "一起吃饭", "description": "聊项目", "participants": ["张三"]}],
                  "self": {"communication_style": "直接", "sensitivities": ["被催"]}
                }
                """
            },
        )
    )
    assert llm_result["created"] == 4

    pending = unwrap(client.get("/api/extractions"))
    kinds = [item["kind"] for item in pending["items"]]
    assert "note_new" in kinds
    assert "person_new" in kinds
    assert "entity_new" in kinds
    assert "event_new" in kinds
    assert "self_update" in kinds
    note = next(item for item in pending["items"] if item["kind"] == "note_new")
    assert note["payload"]["target_type"] == "person"
    assert note["payload"]["target_id"] == person["id"]
    assert "结果导向" in note["payload"]["content"]


def test_imports_persist_source_markdown_documents(client):
    file_result = unwrap(
        client.post(
            "/api/import/file",
            data={"target_type": "self"},
            files={"file": ("memory.txt", "老板喜欢结果导向".encode("utf-8"), "text/plain")},
        )
    )
    file_document = Path(file_result["source_document"]["path"])
    file_content = file_document.read_text(encoding="utf-8")
    assert file_document.parent == Path(os.environ["UPLOAD_DIR"]).parent / "imports"
    assert file_document.suffix == ".md"
    assert "source: file_import" in file_content
    assert "source_file: memory.txt" in file_content
    assert "老板喜欢结果导向" in file_content

    llm_result = unwrap(
        client.post(
            "/api/import/llm-memory",
            json={
                "json": """
                {
                  "events": [{"occurred_at": "近期", "title": "米饼事件", "description": "女儿想踩落地零食"}]
                }
                """
            },
        )
    )
    llm_document = Path(llm_result["source_document"]["path"])
    llm_content = llm_document.read_text(encoding="utf-8")
    assert llm_document.parent == Path(os.environ["UPLOAD_DIR"]).parent / "imports"
    assert "source: llm_memory_import" in llm_content
    assert '"occurred_at": "近期"' in llm_content
    assert "米饼事件" in llm_content


def test_llm_memory_import_matches_existing_person_instead_of_duplicating(client):
    person = unwrap(client.post("/api/people", json={"name": "张总", "aliases": ["Alice Zhang"], "profile_json": {"role": "老板"}}))

    result = unwrap(
        client.post(
            "/api/import/llm-memory",
            json={
                "json": """
                {
                  "people": [{"name": "Zhang Alice", "aliases": ["张总"], "bio": "直属上级", "profile": {"style": "结果导向"}}]
                }
                """
            },
        )
    )
    assert result["created"] == 1

    pending = unwrap(client.get("/api/extractions"))
    person_updates = [item for item in pending["items"] if item["kind"] == "person_update"]
    assert len(person_updates) == 1
    assert person_updates[0]["payload"] == {"person_id": person["id"], "profile_json": {"style": "结果导向"}}
    assert [item for item in pending["items"] if item["kind"] == "person_new"] == []


def test_llm_memory_import_resolves_event_participants_to_existing_people(client):
    person = unwrap(client.post("/api/people", json={"name": "张总", "aliases": ["Alice Zhang"]}))

    result = unwrap(
        client.post(
            "/api/import/llm-memory",
            json={
                "json": """
                {
                  "events": [
                    {
                      "occurred_at": "2026-05-23",
                      "title": "项目复盘",
                      "description": "张总和新同事一起复盘。",
                      "participants": ["Alice Zhang", "新同事"]
                    }
                  ]
                }
                """
            },
        )
    )
    assert result["created"] == 1

    pending = unwrap(client.get("/api/extractions"))
    event = next(item for item in pending["items"] if item["kind"] == "event_new")
    assert event["payload"]["participants"] == [
        {"type": "person", "id": person["id"]},
        {"type": "name", "name": "新同事"},
    ]


def test_import_file_uses_extraction_model_output_when_available(client, monkeypatch):
    person = unwrap(client.post("/api/people", json={"name": "老板"}))
    calls = []

    class FakeLLMClient:
        def complete_json(self, model, messages):
            calls.append({"model": model, "messages": messages})
            return {
                "events": [
                    {
                        "occurred_at": "2026-05-23",
                        "title": "文件抽取事件",
                        "description": "从文件导入中抽取。",
                        "participants": [{"type": "person", "matched_id": person["id"]}],
                        "confidence": 0.9,
                    }
                ],
                "self_updates": {"patches": {"goals": ["减少无效加班"]}, "confidence": 0.7},
            }

    monkeypatch.setattr("app.api.import_.LLMClient", FakeLLMClient, raising=False)

    result = unwrap(
        client.post(
            "/api/import/file",
            files={"file": ("memory.txt", "老板说要减少无效加班".encode("utf-8"), "text/plain")},
        )
    )
    assert result["created"] == 2
    assert calls and calls[0]["model"] == "anthropic/claude-haiku-4-5-20251001"
    assert "老板说要减少无效加班" in calls[0]["messages"][0]["content"]

    pending = unwrap(client.get("/api/extractions"))
    event = next(item for item in pending["items"] if item["kind"] == "event_new")
    self_update = next(item for item in pending["items"] if item["kind"] == "self_update")
    assert event["payload"]["source"] == "file_import"
    assert event["payload"]["source_file"] == "memory.txt"
    assert event["payload"]["participants"] == [{"type": "person", "id": person["id"]}]
    assert self_update["payload"] == {"patches": {"goals": ["减少无效加班"]}}
    assert [item for item in pending["items"] if item["kind"] == "note_new"] == []


def test_import_docx_file_creates_pending_extraction(client):
    document_xml = docx_document("老板在文档里强调周五前要同步风险")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    result = unwrap(
        client.post(
            "/api/import/file",
            data={"target_type": "self"},
            files={"file": ("memory.docx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    )

    assert result["created"] == 1
    pending = unwrap(client.get("/api/extractions"))
    note = next(item for item in pending["items"] if item["kind"] == "note_new")
    assert note["payload"]["source_file"] == "memory.docx"
    assert "周五前要同步风险" in note["payload"]["content"]


def test_import_file_rejects_large_files_and_chunks_long_content(client):
    too_large = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post(
        "/api/import/file",
        files={"file": ("too-large.txt", too_large, "text/plain")},
    )
    assert response.status_code == 413
    assert response.json() == {"ok": False, "error": "file exceeds 10MB limit"}

    long_text = "老板喜欢结果导向。" * 600
    result = unwrap(
        client.post(
            "/api/import/file",
            data={"target_type": "self"},
            files={"file": ("long-memory.txt", long_text.encode("utf-8"), "text/plain")},
        )
    )
    assert result["created"] > 1

    pending = unwrap(client.get("/api/extractions"))
    chunks = [item for item in pending["items"] if item["kind"] == "note_new" and item["payload"]["source_file"] == "long-memory.txt"]
    assert len(chunks) == result["created"]
    assert {item["payload"]["source_chunk_total"] for item in chunks} == {result["created"]}
    assert max(len(item["payload"]["content"]) for item in chunks) <= 4000


def test_docx_parser_preserves_inline_breaks_and_tabs():
    document_xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p>
          <w:r><w:t>第一行</w:t></w:r>
          <w:r><w:br/></w:r>
          <w:r><w:t>第二行</w:t></w:r>
          <w:r><w:tab/></w:r>
          <w:r><w:t>标签</w:t></w:r>
          <w:r><w:t>值</w:t></w:r>
        </w:p>
      </w:body>
    </w:document>
    """.encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    assert parse_import_file("memory.docx", buffer.getvalue()) == "第一行\n第二行\t标签值"


def test_docx_parser_includes_headers_footers_and_notes():
    document_xml = docx_document("正文内容")
    header_xml = docx_document("页眉提醒")
    footer_xml = docx_document("页脚备注")
    footnotes_xml = docx_notes("脚注上下文")
    endnotes_xml = docx_notes("尾注线索")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/header1.xml", header_xml)
        archive.writestr("word/footer1.xml", footer_xml)
        archive.writestr("word/footnotes.xml", footnotes_xml)
        archive.writestr("word/endnotes.xml", endnotes_xml)

    assert parse_import_file("memory.docx", buffer.getvalue()) == "正文内容\n页眉提醒\n页脚备注\n脚注上下文\n尾注线索"


def test_docx_parser_includes_comments():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", docx_document("正文内容"))
        archive.writestr("word/comments.xml", docx_comments("批注提醒"))

    assert parse_import_file("memory.docx", buffer.getvalue()) == "正文内容\n批注提醒"


def docx_document(text: str) -> bytes:
    return f"""
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
      </w:body>
    </w:document>
    """.encode("utf-8")


def docx_notes(text: str) -> bytes:
    return f"""
    <w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:footnote w:id="2">
        <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
      </w:footnote>
    </w:footnotes>
    """.encode("utf-8")


def docx_comments(text: str) -> bytes:
    return f"""
    <w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:comment w:id="0" w:author="tester">
        <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
      </w:comment>
    </w:comments>
    """.encode("utf-8")


def test_export_zip_and_obsidian_markdown(client, tmp_path):
    person = unwrap(client.post("/api/people", json={"name": "老板", "aliases": ["张总"], "bio": "直属上级", "importance": 4}))
    colleague = unwrap(client.post("/api/people", json={"name": "同事", "bio": "一起协作"}))
    unwrap(
        client.post(
            "/api/relationships",
            json={
                "from_type": "person",
                "from_id": person["id"],
                "to_type": "person",
                "to_id": colleague["id"],
                "relation_type": "同事",
                "role": "项目协作",
            },
        )
    )
    unwrap(
        client.post(
            "/api/events",
            json={
                "occurred_at": "2026-05-23",
                "title": "周会提醒",
                "participants": [{"type": "person", "id": person["id"]}],
                "source": "manual",
            },
        )
    )

    zip_response = client.get("/api/export/zip")
    assert zip_response.status_code == 200
    assert zip_response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
        names = set(archive.namelist())
        assert "dossier.json" in names
        assert "schema.sql" in names
        assert "people/老板.md" in names
        schema_sql = archive.read("schema.sql").decode("utf-8")
        person_markdown = archive.read("people/老板.md").decode("utf-8")
    assert "CREATE TABLE person" in schema_sql
    assert "CREATE VIRTUAL TABLE person_fts" in schema_sql
    assert "# 老板" in person_markdown
    assert "周会提醒" in person_markdown
    assert "[[同事]]" in person_markdown

    export_dir = tmp_path / "obsidian-export"
    unwrap(client.patch("/api/settings", json={"obsidian_export_path": str(export_dir)}))
    obsidian_result = unwrap(client.post("/api/export/obsidian"))
    assert obsidian_result["people"] == 2
    exported_file = export_dir / "people" / "老板.md"
    assert exported_file.exists()
    first_export = exported_file.read_text(encoding="utf-8")
    assert "aliases: [张总]" in first_export
    assert "[[同事]]" in first_export
    unwrap(client.post("/api/export/obsidian"))
    assert exported_file.read_text(encoding="utf-8") == first_export


def test_export_zip_contains_restorable_data_dir_and_redacted_config(client, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-for-export")
    person = unwrap(client.post("/api/people", json={"name": "导出恢复人物"}))
    upload_dir = Path(os.environ["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "raw.txt").write_text("上传原文", encoding="utf-8")

    zip_response = client.get("/api/export/zip")
    assert zip_response.status_code == 200

    restore_dir = tmp_path / "restore"
    with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
        names = set(archive.namelist())
        assert "data/dossier.db" in names
        assert "data/uploads/raw.txt" in names
        assert "schema.sql" in names
        assert "config.redacted.json" in names
        config = json.loads(archive.read("config.redacted.json").decode("utf-8"))
        assert config["env"]["OPENAI_API_KEY"] == "***REDACTED***"
        assert "sk-secret-for-export" not in archive.read("config.redacted.json").decode("utf-8")
        archive.extractall(restore_dir)

    restored_db = restore_dir / "data" / "dossier.db"
    with sqlite3.connect(restored_db) as conn:
        row = conn.execute("SELECT name FROM person WHERE id = ?", (person["id"],)).fetchone()
    assert row == ("导出恢复人物",)

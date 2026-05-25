from __future__ import annotations

import importlib
import json
import os
import random
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config


MCP_ROOT = Path(__file__).resolve().parents[2] / "mcp"
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))


def test_intent_tools_call_backend_api(monkeypatch):
    intent = importlib.import_module("tools.intent")
    calls = []

    async def fake_request_json(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"ok": True, "path": path}

    monkeypatch.setattr(intent, "request_json", fake_request_json)

    assert intent.anyio.run(intent.interpret_message, "老板说我最近加班比较多啊")["path"] == "/api/mcp/interpret"
    assert intent.anyio.run(intent.prepare_conversation, "老板")["path"] == "/api/mcp/prepare"
    assert intent.anyio.run(intent.stale_contacts, 14)["path"] == "/api/mcp/stale-contacts"
    assert intent.anyio.run(intent.recent_changes, "老板", 7)["path"] == "/api/mcp/recent-changes"
    assert calls[0] == (
        "POST",
        "/api/mcp/interpret",
        {"json": {"message": "老板说我最近加班比较多啊", "from_hint": None, "context_hint": None}},
    )


def test_data_tools_call_existing_rest_api(monkeypatch):
    data = importlib.import_module("tools.data")
    calls = []

    async def fake_request_json(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/api/search":
            return {"people": [{"id": 12, "name": "老板"}]}
        if path == "/api/people/12":
            return {"person": {"id": 12, "name": "老板"}}
        return {"items": []}

    monkeypatch.setattr(data, "request_json", fake_request_json)

    assert data.anyio.run(data.get_person, "老板") == {"id": 12, "name": "老板"}
    assert data.anyio.run(data.search_people, "老板", 5) == [{"id": 12, "name": "老板"}]
    assert data.anyio.run(data.get_relationship, "老板") == []
    assert data.anyio.run(data.get_recent_events, "老板", 30) == []
    assert data.anyio.run(data.get_self_profile) == {"items": []}
    assert data.anyio.run(data.get_timeline, None, None) == {"items": []}

    assert ("GET", "/api/search", {"params": {"q": "老板", "type": "people"}}) in calls
    assert ("GET", "/api/relationships", {"params": {"to": "person:12"}}) in calls


def test_mcp_server_imports_from_file_path():
    while str(MCP_ROOT) in sys.path:
        sys.path.remove(str(MCP_ROOT))
    spec = importlib.util.spec_from_file_location("dossier_mcp_server", MCP_ROOT / "server.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)
        assert module.mcp.name == "Dossier"
    finally:
        if str(MCP_ROOT) not in sys.path:
            sys.path.insert(0, str(MCP_ROOT))


def test_mcp_stdio_verify_script_lists_registered_tools():
    project_root = MCP_ROOT.parent
    script = project_root / "scripts" / "verify-mcp-stdio.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    for tool_name in (
        "interpret_message",
        "prepare_conversation",
        "stale_contacts",
        "recent_changes",
        "get_person",
        "search_people",
        "get_relationship",
        "get_recent_events",
        "get_self_profile",
        "get_timeline",
    ):
        assert tool_name in result.stdout


def test_install_mcp_uses_project_venv_python_for_install_and_config(tmp_path):
    project_root = MCP_ROOT.parent
    install_script = tmp_path / "project" / "scripts" / "install-mcp.sh"
    install_script.parent.mkdir(parents=True)
    install_script.write_text((project_root / "scripts" / "install-mcp.sh").read_text(encoding="utf-8"), encoding="utf-8")
    install_script.chmod(0o755)
    mcp_dir = tmp_path / "project" / "mcp"
    mcp_dir.mkdir()
    (mcp_dir / "requirements.txt").write_text("mcp\nhttpx\n", encoding="utf-8")
    (mcp_dir / "server.py").write_text("", encoding="utf-8")
    fake_python = tmp_path / "project" / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > python-args.log\n", encoding="utf-8")
    fake_python.chmod(0o755)

    result = subprocess.run(
        ["/bin/bash", str(install_script)],
        cwd=tmp_path / "project",
        env={**os.environ, "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "project" / "python-args.log").read_text(encoding="utf-8").splitlines() == [
        "-m",
        "pip",
        "install",
        "-r",
        "mcp/requirements.txt",
    ]
    config = json.loads(result.stdout[result.stdout.index("{") :])
    server_config = config["mcpServers"]["dossier"]
    assert server_config["command"] == str(fake_python)
    assert server_config["args"] == [str(tmp_path / "project" / "mcp" / "server.py")]


def test_install_mcp_can_merge_dossier_into_existing_claude_config(tmp_path):
    project_root = MCP_ROOT.parent
    project_dir = tmp_path / "project"
    install_script = project_dir / "scripts" / "install-mcp.sh"
    install_script.parent.mkdir(parents=True)
    install_script.write_text((project_root / "scripts" / "install-mcp.sh").read_text(encoding="utf-8"), encoding="utf-8")
    install_script.chmod(0o755)
    mcp_dir = project_dir / "mcp"
    mcp_dir.mkdir()
    (mcp_dir / "requirements.txt").write_text("mcp\nhttpx\n", encoding="utf-8")
    (mcp_dir / "server.py").write_text("", encoding="utf-8")
    fake_python = project_dir / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = \"-m\" ] && [ \"$2\" = \"pip\" ]; then\n"
        "  printf '%s\\n' \"$@\" > python-args.log\n"
        "  exit 0\n"
        "fi\n"
        f"exec {sys.executable} \"$@\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    home = tmp_path / "home"
    config_path = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"preferences": {"quickEntryShortcut": "off"}}, ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        ["/bin/bash", str(install_script), "--write-claude-config"],
        cwd=project_dir,
        env={**os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["preferences"] == {"quickEntryShortcut": "off"}
    assert config["mcpServers"]["dossier"] == {
        "command": str(fake_python),
        "args": [str(project_dir / "mcp" / "server.py")],
        "env": {"DOSSIER_API_URL": "http://127.0.0.1:8000"},
    }
    assert json.loads(config_path.with_name(config_path.name + ".bak").read_text(encoding="utf-8")) == {
        "preferences": {"quickEntryShortcut": "off"}
    }
    assert "Wrote Claude Desktop config" in result.stdout


def test_mcp_stdio_verify_script_can_call_interpret_message(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "interpret_message",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: interpret_message" in result.stdout
    assert "reply_options" in result.stdout


def test_mcp_stdio_verify_script_can_call_prepare_conversation(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "prepare_conversation",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: prepare_conversation" in result.stdout
    assert "suggested_opening" in result.stdout


def test_mcp_stdio_verify_script_can_call_stale_contacts(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people",
            data=json.dumps({"name": "旧同事"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 200
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "stale_contacts",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: stale_contacts" in result.stdout
    assert "旧同事" in result.stdout


def test_mcp_stdio_verify_script_can_call_recent_changes(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        person_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people",
            data=json.dumps({"name": "老板", "aliases": ["张总"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(person_request, timeout=2) as response:
            assert response.status == 200
            person = json.loads(response.read().decode("utf-8"))["data"]
        event_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/events",
            data=json.dumps(
                {
                    "occurred_at": date.today().isoformat(),
                    "title": "合同范围变更",
                    "participants": [{"type": "person", "id": person["id"]}],
                    "source": "manual",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(event_request, timeout=2) as response:
            assert response.status == 200
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "recent_changes",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: recent_changes" in result.stdout
    assert "合同范围变更" in result.stdout


def test_mcp_stdio_verify_script_can_call_all_tools(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        self_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/self",
            data=json.dumps({"name": "我", "communication_style": "直接"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with urllib.request.urlopen(self_request, timeout=2) as response:
            assert response.status == 200
        boss_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people",
            data=json.dumps({"name": "老板", "aliases": ["张总"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(boss_request, timeout=2) as response:
            assert response.status == 200
            boss = json.loads(response.read().decode("utf-8"))["data"]
        stale_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people",
            data=json.dumps({"name": "旧同事"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(stale_request, timeout=2) as response:
            assert response.status == 200
        relationship_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/relationships",
            data=json.dumps(
                {
                    "from_type": "self",
                    "to_type": "person",
                    "to_id": boss["id"],
                    "relation_type": "上下级",
                    "role": "老板",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(relationship_request, timeout=2) as response:
            assert response.status == 200
        stage_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/stages",
            data=json.dumps({"name": "工作", "kind": "工作", "started_at": "2022-07-01", "sort_order": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(stage_request, timeout=2) as response:
            assert response.status == 200
            stage = json.loads(response.read().decode("utf-8"))["data"]
        assignment_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people/{boss['id']}/stages",
            data=json.dumps({"stage_id": stage["id"], "role_in_stage": "直属上级", "started_at": "2023-01-01"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(assignment_request, timeout=2) as response:
            assert response.status == 200
        event_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/events",
            data=json.dumps(
                {
                    "occurred_at": date.today().isoformat(),
                    "title": "合同范围变更",
                    "participants": [{"type": "person", "id": boss["id"]}],
                    "source": "manual",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(event_request, timeout=2) as response:
            assert response.status == 200
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-all",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    for tool_name in (
        "get_person",
        "get_recent_events",
        "get_relationship",
        "get_self_profile",
        "get_timeline",
        "interpret_message",
        "prepare_conversation",
        "recent_changes",
        "search_people",
        "stale_contacts",
    ):
        assert f"MCP stdio call OK: {tool_name}" in result.stdout
    assert "合同范围变更" in result.stdout
    assert "旧同事" in result.stdout
    assert "直属上级" in result.stdout


def test_mcp_stdio_verify_script_can_call_search_people(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people",
            data=json.dumps({"name": "老板", "aliases": ["张总"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 200
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "search_people",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: search_people" in result.stdout
    assert "老板" in result.stdout


def test_mcp_stdio_verify_script_can_call_get_person(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people",
            data=json.dumps({"name": "老板", "aliases": ["张总"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 200
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "get_person",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: get_person" in result.stdout
    assert "老板" in result.stdout


def test_mcp_stdio_verify_script_can_call_get_relationship(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        person_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people",
            data=json.dumps({"name": "老板", "aliases": ["张总"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(person_request, timeout=2) as response:
            assert response.status == 200
            person = json.loads(response.read().decode("utf-8"))["data"]
        relationship_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/relationships",
            data=json.dumps(
                {
                    "from_type": "self",
                    "to_type": "person",
                    "to_id": person["id"],
                    "relation_type": "上下级",
                    "role": "老板",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(relationship_request, timeout=2) as response:
            assert response.status == 200
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "get_relationship",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: get_relationship" in result.stdout
    assert "上下级" in result.stdout


def test_mcp_stdio_verify_script_can_call_get_recent_events(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        person_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people",
            data=json.dumps({"name": "老板", "aliases": ["张总"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(person_request, timeout=2) as response:
            assert response.status == 200
            person = json.loads(response.read().decode("utf-8"))["data"]
        event_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/events",
            data=json.dumps(
                {
                    "occurred_at": date.today().isoformat(),
                    "title": "一起复盘项目",
                    "participants": [{"type": "person", "id": person["id"]}],
                    "source": "manual",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(event_request, timeout=2) as response:
            assert response.status == 200
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "get_recent_events",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: get_recent_events" in result.stdout
    assert "一起复盘项目" in result.stdout


def test_mcp_stdio_verify_script_can_call_get_self_profile(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/self",
            data=json.dumps({"name": "我", "communication_style": "直接", "goals": ["减少误解"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 200
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "get_self_profile",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: get_self_profile" in result.stdout
    assert "直接" in result.stdout


def test_mcp_stdio_verify_script_can_call_get_timeline(tmp_path, monkeypatch):
    project_root = MCP_ROOT.parent
    db_path = tmp_path / "dossier.db"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "UPLOAD_DIR": str(upload_dir),
    }
    command.upgrade(Config("backend/alembic.ini"), "head")
    port = unused_high_port()
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        wait_for_backend(port)
        person_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people",
            data=json.dumps({"name": "老板", "aliases": ["张总"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(person_request, timeout=2) as response:
            assert response.status == 200
            person = json.loads(response.read().decode("utf-8"))["data"]
        stage_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/stages",
            data=json.dumps({"name": "工作", "kind": "工作", "started_at": "2022-07-01", "sort_order": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(stage_request, timeout=2) as response:
            assert response.status == 200
            stage = json.loads(response.read().decode("utf-8"))["data"]
        assignment_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/people/{person['id']}/stages",
            data=json.dumps({"stage_id": stage["id"], "role_in_stage": "直属上级", "started_at": "2023-01-01"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(assignment_request, timeout=2) as response:
            assert response.status == 200
        event_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/events",
            data=json.dumps(
                {
                    "occurred_at": "2024-03-10",
                    "title": "周会被提醒进度",
                    "participants": [{"type": "person", "id": person["id"]}],
                    "source": "manual",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(event_request, timeout=2) as response:
            assert response.status == 200
        result = subprocess.run(
            [
                sys.executable,
                str(project_root / "scripts" / "verify-mcp-stdio.py"),
                "--api-url",
                f"http://127.0.0.1:{port}",
                "--call-tool",
                "get_timeline",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    finally:
        backend.terminate()
        backend.communicate(timeout=5)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "MCP stdio call OK: get_timeline" in result.stdout
    assert "直属上级" in result.stdout
    assert "周会被提醒进度" in result.stdout


def unused_high_port() -> int:
    for _ in range(100):
        port = random.randint(20000, 60000)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("no free high port found")


def wait_for_backend(port: int) -> None:
    deadline = time.monotonic() + 10
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("backend did not become ready")

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_root_npm_quickstart_scripts_exist():
    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

    assert package_json["private"] is True
    assert package_json["scripts"]["postinstall"] == "scripts/install-deps.sh"
    assert package_json["scripts"]["start"] == "scripts/start.sh"
    assert package_json["scripts"]["stop"] == "scripts/stop.sh"
    assert (ROOT / "scripts" / "install-deps.sh").exists()


def test_readme_documents_three_step_quickstart_troubleshooting_and_screenshots():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "git clone" in readme
    assert "npm install" in readme
    assert "npm start" in readme
    assert "路径校验失败" in readme
    assert "API key 不识别" in readme
    assert "MCP 装不上" in readme
    for screenshot in ("chat.png", "inbox.png", "timeline.png"):
        assert f"docs/screenshots/{screenshot}" in readme
        assert (ROOT / "docs" / "screenshots" / screenshot).exists()

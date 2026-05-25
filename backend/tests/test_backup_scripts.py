from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path


def test_backup_script_creates_archive_and_keeps_latest_seven(tmp_path):
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    (data_dir / "dossier.db").write_text("db", encoding="utf-8")
    backup_dir.mkdir()
    for index in range(8):
        (backup_dir / f"dossier-backup-20000101_00000{index}.tar.gz").write_text("old", encoding="utf-8")

    result = subprocess.run(
        ["/bin/bash", "scripts/backup.sh"],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "DOSSIER_DATA_DIR": str(data_dir), "DOSSIER_BACKUP_DIR": str(backup_dir)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archives = sorted(backup_dir.glob("dossier-backup-*.tar.gz"))
    assert len(archives) == 7
    assert "dossier-backup-20000101_000000.tar.gz" not in {item.name for item in archives}
    newest = max(archives, key=lambda path: path.stat().st_mtime)
    with tarfile.open(newest, "r:gz") as archive:
        assert "data/dossier.db" in archive.getnames()


def test_install_backup_cron_dry_run_prints_daily_0200_line():
    result = subprocess.run(
        ["/bin/bash", "scripts/install-backup-cron.sh", "--dry-run"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 2 * * *" in result.stdout
    assert "scripts/backup.sh" in result.stdout

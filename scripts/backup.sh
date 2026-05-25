#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
data_dir="${DOSSIER_DATA_DIR:-${repo_dir}/data}"
backup_dir="${DOSSIER_BACKUP_DIR:-${HOME}/Library/Application Support/Dossier/backups}"

mkdir -p "${backup_dir}"
ts=$(date +%Y%m%d_%H%M%S)
archive="${backup_dir}/dossier-backup-${ts}.tar.gz"

tar -czf "${archive}" -C "$(dirname "${data_dir}")" "$(basename "${data_dir}")"

find "${backup_dir}" -maxdepth 1 -type f -name 'dossier-backup*.tar.gz' -print \
  | sort -r \
  | awk 'NR > 7' \
  | xargs -r rm -f

echo "Backup: ${archive}"

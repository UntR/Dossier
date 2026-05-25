#!/usr/bin/env bash
set -euo pipefail

repo_dir="${DOSSIER_REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cron_line="0 2 * * * DOSSIER_REPO_DIR=\"${repo_dir}\" /bin/bash \"${repo_dir}/scripts/backup.sh\" >>\"${repo_dir}/backup.log\" 2>&1"

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "${cron_line}"
  exit 0
fi

existing="$(crontab -l 2>/dev/null | grep -v 'scripts/backup.sh' || true)"
{
  if [[ -n "${existing}" ]]; then
    printf '%s\n' "${existing}"
  fi
  printf '%s\n' "${cron_line}"
} | crontab -

echo "Installed backup cron: ${cron_line}"

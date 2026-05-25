#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
read -r -p "This will DELETE all data. Type 'yes' to confirm: " c
[ "$c" != "yes" ] && exit 1
docker compose down -v
rm -rf data/
mkdir -p data
echo "Reset done. Run scripts/start.sh to start fresh."

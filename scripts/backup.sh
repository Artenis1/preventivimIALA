#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
backup_dir="${1:-backups/$(date -u +%Y%m%dT%H%M%SZ)}"
if [ -e "$backup_dir" ]; then
  echo 'Destinacioni ekziston; zgjidhni një dosje të re.' >&2
  exit 1
fi
mkdir -p "$backup_dir"
# Run during a maintenance window without writes for a consistent DB/files pair.
docker compose exec -T db pg_dump -U smartestimate -d smartestimate --format=custom --no-owner --no-acl > "$backup_dir/database.dump"
docker compose exec -T backend tar -C /data/uploads -czf - . > "$backup_dir/uploads.tar.gz"
test -s "$backup_dir/database.dump"
test -s "$backup_dir/uploads.tar.gz"
(cd "$backup_dir" && sha256sum database.dump uploads.tar.gz > SHA256SUMS)
echo "Kopja rezervë: $backup_dir"

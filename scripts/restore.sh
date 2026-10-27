#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$#" -ne 2 ] || [ "$2" != '--confirm-replace-database' ]; then
  echo 'Përdorimi: scripts/restore.sh DOSJA --confirm-replace-database' >&2
  echo 'KUJDES: zëvendëson databazën. Fillimisht ruani kopjen aktuale dhe ndaloni shkrimet.' >&2
  exit 1
fi
backup_dir="$1"
test -s "$backup_dir/database.dump"
test -s "$backup_dir/uploads.tar.gz"
(cd "$backup_dir" && sha256sum -c SHA256SUMS)
# Restore only trusted backups created by backup.sh. Keep frontend stopped.
docker compose exec -T db pg_restore -U smartestimate -d smartestimate --clean --if-exists --no-owner --no-acl --single-transaction < "$backup_dir/database.dump"
docker compose exec -T backend tar -C /data/uploads -xzf - < "$backup_dir/uploads.tar.gz"
echo 'Rikthimi përfundoi. Verifikoni gatishmërinë, përdoruesit, preventivat dhe shkarkimet para rihapjes.'

#!/usr/bin/env bash
# Backup ARTeX state before stopping/recreating containers.
#
# Includes:
#   - Postgres dump: tasks, conversations + chat messages, explorations,
#     findings, LLM profiles, settings (the data the UI lists as "sessions")
#   - data/: per-conversation task workspaces, transcripts, traffic store
#   - jwt.key: keeps browser login sessions valid after a restore
#   - .env, config.json: runtime configuration
#
# Usage:
#   ./backup.sh                 # writes to backups/
#   ARTEX_BACKUP_DIR=/mnt/x ./backup.sh
#
# Restore (stop the app first):
#   docker exec -i artex-postgres pg_restore -U artex -d artex --clean --if-exists --no-owner < dump
#   tar xzf artex-data-*.tgz
set -euo pipefail
cd "$(dirname "$0")"
umask 077

if [ -f .env ]; then
	set -a
	# shellcheck disable=SC1091
	. ./.env
	set +a
fi

CONTAINER=${ARTEX_PG_CONTAINER:-artex-postgres}
PGUSER=${POSTGRES_USER:-artex}
PGDB=${POSTGRES_DB:-artex}
OUT=${ARTEX_BACKUP_DIR:-backups}
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"

echo "[backup] pg_dump ${PGDB} from ${CONTAINER}..."
docker exec "$CONTAINER" pg_dump -U "$PGUSER" -d "$PGDB" -Fc > "$OUT/artex-db-$STAMP.dump"

echo "[backup] archiving data/, jwt.key, .env, config.json..."
tar czf "$OUT/artex-data-$STAMP.tgz" data jwt.key .env config.json 2>/dev/null || \
	tar czf "$OUT/artex-data-$STAMP.tgz" data jwt.key

echo "[backup] done:"
ls -lh "$OUT/artex-db-$STAMP.dump" "$OUT/artex-data-$STAMP.tgz"

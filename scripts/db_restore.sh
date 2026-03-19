#!/bin/bash
# Restore the Postgres database from a backup
# Usage: ./scripts/db_restore.sh
BACKUP_FILE="db/backup.sql"
if [ ! -f "$BACKUP_FILE" ]; then
    echo "No backup found at $BACKUP_FILE"
    exit 1
fi
echo "Restoring database from $BACKUP_FILE..."
docker compose exec -T db psql -U sfdc sfdc < "$BACKUP_FILE"
echo "Restore complete"
docker compose exec db psql -U sfdc -c "SELECT count(*) as articles FROM articles;"

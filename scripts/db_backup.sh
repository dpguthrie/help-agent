#!/bin/bash
# Backup the Postgres database to a SQL file
# Usage: ./scripts/db_backup.sh
BACKUP_FILE="db/backup.sql"
echo "Backing up database to $BACKUP_FILE..."
docker compose exec -T db pg_dump -U sfdc --data-only sfdc > "$BACKUP_FILE"
echo "Backup complete: $(wc -l < $BACKUP_FILE) lines"

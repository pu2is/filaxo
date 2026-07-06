#!/bin/bash
set -euo pipefail

SQLCMD="/opt/mssql-tools18/bin/sqlcmd -S ${DB_SERVER} -U ${DB_USER} -P ${DB_PASSWORD} -C -b"

EXISTS=$($SQLCMD -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.databases WHERE name = N'${DB_NAME}'" | tr -d '[:space:]')

if [ "$EXISTS" = "1" ]; then
  echo "[restore-db] Database '${DB_NAME}' already exists — skipping restore."
  exit 0
fi

echo "[restore-db] Restoring '${DB_NAME}' from ${BACKUP_FILE}..."
$SQLCMD -v BackupFile="${BACKUP_FILE}" DbName="${DB_NAME}" DataPath="${DATA_PATH}" -i /scripts/restore-db.sql
echo "[restore-db] Restore complete."

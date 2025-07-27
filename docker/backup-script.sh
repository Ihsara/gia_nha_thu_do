#!/bin/bash
# Multi-city database backup script for Oikotie Scraper

# Configuration
BACKUP_DIR=${BACKUP_PATH:-"/backups"}
DATABASE_PATH=${DATABASE_PATH:-"/data/real_estate.duckdb"}
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-7}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/oikotie_backup_$TIMESTAMP.tar.gz"
LOG_FILE="$BACKUP_DIR/backup_$TIMESTAMP.log"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

echo "Starting multi-city database backup at $(date)" | tee -a "$LOG_FILE"

# Create database backup
echo "Creating database backup from $DATABASE_PATH" | tee -a "$LOG_FILE"

# Use DuckDB's built-in backup mechanism
if command -v duckdb &> /dev/null; then
    echo "Using DuckDB CLI for backup" | tee -a "$LOG_FILE"
    duckdb "$DATABASE_PATH" "EXPORT DATABASE '$BACKUP_DIR/temp_backup'" >> "$LOG_FILE" 2>&1
    BACKUP_STATUS=$?
else
    echo "DuckDB CLI not found, using file copy method" | tee -a "$LOG_FILE"
    # Create a temporary directory for the backup
    TEMP_DIR="$BACKUP_DIR/temp_backup_$TIMESTAMP"
    mkdir -p "$TEMP_DIR"
    
    # Copy the database file (this will work if the database is not actively being written to)
    cp "$DATABASE_PATH" "$TEMP_DIR/real_estate.duckdb" >> "$LOG_FILE" 2>&1
    BACKUP_STATUS=$?
fi

# Check if backup was successful
if [ $BACKUP_STATUS -ne 0 ]; then
    echo "ERROR: Database backup failed with status $BACKUP_STATUS" | tee -a "$LOG_FILE"
    exit 1
fi

# Create city-specific metadata
echo "Creating city-specific metadata" | tee -a "$LOG_FILE"
if command -v duckdb &> /dev/null; then
    duckdb "$DATABASE_PATH" "SELECT city, COUNT(*) as listing_count, MIN(scraped_at) as oldest_record, MAX(scraped_at) as newest_record FROM listings GROUP BY city" > "$BACKUP_DIR/temp_backup/city_stats.txt" 2>> "$LOG_FILE"
fi

# Create archive of the backup
echo "Creating compressed archive" | tee -a "$LOG_FILE"
tar -czf "$BACKUP_FILE" -C "$BACKUP_DIR" temp_backup >> "$LOG_FILE" 2>&1
TAR_STATUS=$?

# Clean up temporary files
rm -rf "$BACKUP_DIR/temp_backup"

# Check if archive creation was successful
if [ $TAR_STATUS -ne 0 ]; then
    echo "ERROR: Archive creation failed with status $TAR_STATUS" | tee -a "$LOG_FILE"
    exit 1
fi

# Create backup metadata
echo "Creating backup metadata" | tee -a "$LOG_FILE"
cat > "$BACKUP_DIR/backup_$TIMESTAMP.json" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "backup_file": "$BACKUP_FILE",
  "database_path": "$DATABASE_PATH",
  "backup_size_bytes": $(stat -c%s "$BACKUP_FILE"),
  "cities_included": $(duckdb "$DATABASE_PATH" "SELECT DISTINCT city FROM listings" -csv 2>/dev/null || echo '["unknown"]'),
  "record_counts": $(duckdb "$DATABASE_PATH" "SELECT city, COUNT(*) as count FROM listings GROUP BY city" -json 2>/dev/null || echo '{"unknown": 0}')
}
EOF

# Clean up old backups
echo "Cleaning up backups older than $RETENTION_DAYS days" | tee -a "$LOG_FILE"
find "$BACKUP_DIR" -name "oikotie_backup_*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "backup_*.log" -type f -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "backup_*.json" -type f -mtime +$RETENTION_DAYS -delete

echo "Backup completed successfully at $(date)" | tee -a "$LOG_FILE"
echo "Backup file: $BACKUP_FILE" | tee -a "$LOG_FILE"
echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)" | tee -a "$LOG_FILE"

# Update the latest backup symlink
ln -sf "$BACKUP_FILE" "$BACKUP_DIR/latest_backup.tar.gz"

# Signal success to monitoring systems
touch "$BACKUP_DIR/last_successful_backup_$TIMESTAMP"
ln -sf "$BACKUP_DIR/last_successful_backup_$TIMESTAMP" "$BACKUP_DIR/last_successful_backup"

exit 0
#!/usr/bin/env python3
"""
Comprehensive backup and disaster recovery manager for multi-city scraper.

This module provides automated backup, encryption, validation, and disaster
recovery capabilities for the multi-city Oikotie scraper system.
"""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

import boto3
from cryptography.fernet import Fernet
from loguru import logger

from oikotie.database.connection import get_database_connection
from oikotie.utils.config import load_config


@dataclass
class BackupMetadata:
    """Metadata for a backup."""
    backup_id: str
    timestamp: datetime
    backup_type: str  # "full", "incremental", "city-specific"
    cities: List[str]
    size_bytes: int
    checksum: str
    encryption_enabled: bool
    compression_enabled: bool
    storage_location: str
    validation_status: str  # "pending", "valid", "invalid", "failed"
    retention_until: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['retention_until'] = self.retention_until.isoformat()
        return result


@dataclass
class RestorePoint:
    """Restore point information."""
    backup_id: str
    timestamp: datetime
    cities: List[str]
    data_integrity_score: float
    restore_time_estimate_minutes: int
    dependencies: List[str]  # Other backups needed for full restore


class BackupManager:
    """Comprehensive backup and disaster recovery manager."""
    
    def __init__(self, config_path: str = "config/config.json"):
        """Initialize backup manager."""
        self.config = load_config(config_path)
        self.backup_config = self.config.get("backup", {})
        self.dr_config = self.config.get("disaster_recovery", {})
        
        self.logger = logger.bind(component="backup_manager")
        
        # Backup settings
        self.backup_dir = Path(self.backup_config.get("local_path", "backups"))
        self.backup_dir.mkdir(exist_ok=True)
        
        self.retention_days = self.backup_config.get("retention_days", 7)
        self.compression_enabled = self.backup_config.get("compression", True)
        self.encryption_enabled = self.backup_config.get("encryption", {}).get("enabled", True)
        
        # Initialize encryption
        self.encryption_key = None
        if self.encryption_enabled:
            self._initialize_encryption()
        
        # Initialize S3 client if configured
        self.s3_client = None
        if self.backup_config.get("s3", {}).get("enabled", False):
            self._initialize_s3()
        
        # Database connection
        self.db_connection = None
        self._initialize_database()
    
    def _initialize_encryption(self):
        """Initialize encryption key."""
        key_file = Path("config/backup_encryption.key")
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                self.encryption_key = f.read()
        else:
            # Generate new key
            self.encryption_key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(self.encryption_key)
            key_file.chmod(0o600)  # Restrict permissions
            self.logger.info("Generated new encryption key")
        
        self.fernet = Fernet(self.encryption_key)
    
    def _initialize_s3(self):
        """Initialize S3 client for remote backups."""
        s3_config = self.backup_config.get("s3", {})
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=s3_config.get("access_key"),
                aws_secret_access_key=s3_config.get("secret_key"),
                region_name=s3_config.get("region", "us-east-1"),
                endpoint_url=s3_config.get("endpoint")  # For S3-compatible services
            )
            
            # Test connection
            self.s3_client.head_bucket(Bucket=s3_config.get("bucket"))
            self.logger.info("S3 backup storage initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize S3: {e}")
            self.s3_client = None
    
    def _initialize_database(self):
        """Initialize database connection."""
        try:
            self.db_connection = get_database_connection()
            self.logger.info("Database connection established for backup")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
    
    async def create_full_backup(self, cities: Optional[List[str]] = None) -> BackupMetadata:
        """Create a full backup of the system."""
        self.logger.info("Starting full backup")
        
        backup_id = f"full_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.utcnow()
        
        # Determine cities to backup
        if cities is None:
            cities = [task["city"] for task in self.config.get("tasks", []) if task.get("enabled", False)]
        
        try:
            # Create temporary directory for backup
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                backup_path = temp_path / f"{backup_id}.tar"
                
                # Backup database
                await self._backup_database(temp_path / "database", cities)
                
                # Backup configuration
                await self._backup_configuration(temp_path / "config")
                
                # Backup logs (recent only)
                await self._backup_logs(temp_path / "logs")
                
                # Create compressed archive
                if self.compression_enabled:
                    backup_path = backup_path.with_suffix('.tar.gz')
                    await self._create_compressed_archive(temp_path, backup_path)
                else:
                    await self._create_archive(temp_path, backup_path)
                
                # Calculate checksum
                checksum = await self._calculate_checksum(backup_path)
                
                # Encrypt if enabled
                if self.encryption_enabled:
                    encrypted_path = backup_path.with_suffix(backup_path.suffix + '.enc')
                    await self._encrypt_file(backup_path, encrypted_path)
                    backup_path.unlink()  # Remove unencrypted file
                    backup_path = encrypted_path
                
                # Move to final location
                final_path = self.backup_dir / backup_path.name
                shutil.move(str(backup_path), str(final_path))
                
                # Create metadata
                metadata = BackupMetadata(
                    backup_id=backup_id,
                    timestamp=timestamp,
                    backup_type="full",
                    cities=cities,
                    size_bytes=final_path.stat().st_size,
                    checksum=checksum,
                    encryption_enabled=self.encryption_enabled,
                    compression_enabled=self.compression_enabled,
                    storage_location=str(final_path),
                    validation_status="pending",
                    retention_until=timestamp + timedelta(days=self.retention_days)
                )
                
                # Save metadata
                await self._save_backup_metadata(metadata)
                
                # Upload to S3 if configured
                if self.s3_client:
                    await self._upload_to_s3(final_path, metadata)
                
                # Validate backup
                validation_result = await self._validate_backup(metadata)
                metadata.validation_status = "valid" if validation_result else "invalid"
                await self._save_backup_metadata(metadata)
                
                self.logger.info(f"Full backup completed: {backup_id}")
                return metadata
                
        except Exception as e:
            self.logger.error(f"Full backup failed: {e}")
            raise
    
    async def create_incremental_backup(self, since: datetime, cities: Optional[List[str]] = None) -> BackupMetadata:
        """Create an incremental backup since the specified timestamp."""
        self.logger.info(f"Starting incremental backup since {since}")
        
        backup_id = f"incr_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.utcnow()
        
        if cities is None:
            cities = [task["city"] for task in self.config.get("tasks", []) if task.get("enabled", False)]
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                backup_path = temp_path / f"{backup_id}.tar"
                
                # Backup only changed data since timestamp
                await self._backup_incremental_database(temp_path / "database", cities, since)
                
                # Backup recent logs
                await self._backup_recent_logs(temp_path / "logs", since)
                
                # Create archive
                if self.compression_enabled:
                    backup_path = backup_path.with_suffix('.tar.gz')
                    await self._create_compressed_archive(temp_path, backup_path)
                else:
                    await self._create_archive(temp_path, backup_path)
                
                checksum = await self._calculate_checksum(backup_path)
                
                if self.encryption_enabled:
                    encrypted_path = backup_path.with_suffix(backup_path.suffix + '.enc')
                    await self._encrypt_file(backup_path, encrypted_path)
                    backup_path.unlink()
                    backup_path = encrypted_path
                
                final_path = self.backup_dir / backup_path.name
                shutil.move(str(backup_path), str(final_path))
                
                metadata = BackupMetadata(
                    backup_id=backup_id,
                    timestamp=timestamp,
                    backup_type="incremental",
                    cities=cities,
                    size_bytes=final_path.stat().st_size,
                    checksum=checksum,
                    encryption_enabled=self.encryption_enabled,
                    compression_enabled=self.compression_enabled,
                    storage_location=str(final_path),
                    validation_status="pending",
                    retention_until=timestamp + timedelta(days=self.retention_days)
                )
                
                await self._save_backup_metadata(metadata)
                
                if self.s3_client:
                    await self._upload_to_s3(final_path, metadata)
                
                validation_result = await self._validate_backup(metadata)
                metadata.validation_status = "valid" if validation_result else "invalid"
                await self._save_backup_metadata(metadata)
                
                self.logger.info(f"Incremental backup completed: {backup_id}")
                return metadata
                
        except Exception as e:
            self.logger.error(f"Incremental backup failed: {e}")
            raise
    
    async def create_city_backup(self, city: str) -> BackupMetadata:
        """Create a backup for a specific city."""
        self.logger.info(f"Starting city-specific backup for {city}")
        
        backup_id = f"city_{city}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.utcnow()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                backup_path = temp_path / f"{backup_id}.tar"
                
                # Backup city-specific data
                await self._backup_city_database(temp_path / "database", city)
                
                # Backup city-specific configuration
                await self._backup_city_configuration(temp_path / "config", city)
                
                if self.compression_enabled:
                    backup_path = backup_path.with_suffix('.tar.gz')
                    await self._create_compressed_archive(temp_path, backup_path)
                else:
                    await self._create_archive(temp_path, backup_path)
                
                checksum = await self._calculate_checksum(backup_path)
                
                if self.encryption_enabled:
                    encrypted_path = backup_path.with_suffix(backup_path.suffix + '.enc')
                    await self._encrypt_file(backup_path, encrypted_path)
                    backup_path.unlink()
                    backup_path = encrypted_path
                
                final_path = self.backup_dir / backup_path.name
                shutil.move(str(backup_path), str(final_path))
                
                metadata = BackupMetadata(
                    backup_id=backup_id,
                    timestamp=timestamp,
                    backup_type="city-specific",
                    cities=[city],
                    size_bytes=final_path.stat().st_size,
                    checksum=checksum,
                    encryption_enabled=self.encryption_enabled,
                    compression_enabled=self.compression_enabled,
                    storage_location=str(final_path),
                    validation_status="pending",
                    retention_until=timestamp + timedelta(days=self.retention_days)
                )
                
                await self._save_backup_metadata(metadata)
                
                if self.s3_client:
                    await self._upload_to_s3(final_path, metadata)
                
                validation_result = await self._validate_backup(metadata)
                metadata.validation_status = "valid" if validation_result else "invalid"
                await self._save_backup_metadata(metadata)
                
                self.logger.info(f"City backup completed: {backup_id}")
                return metadata
                
        except Exception as e:
            self.logger.error(f"City backup failed for {city}: {e}")
            raise
    
    async def restore_from_backup(self, backup_id: str, target_path: Optional[Path] = None, cities: Optional[List[str]] = None) -> bool:
        """Restore system from a backup."""
        self.logger.info(f"Starting restore from backup: {backup_id}")
        
        try:
            # Load backup metadata
            metadata = await self._load_backup_metadata(backup_id)
            if not metadata:
                self.logger.error(f"Backup metadata not found: {backup_id}")
                return False
            
            # Validate backup before restore
            if not await self._validate_backup(metadata):
                self.logger.error(f"Backup validation failed: {backup_id}")
                return False
            
            backup_path = Path(metadata.storage_location)
            if not backup_path.exists():
                # Try to download from S3
                if self.s3_client:
                    await self._download_from_s3(backup_path, metadata)
                else:
                    self.logger.error(f"Backup file not found: {backup_path}")
                    return False
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Decrypt if needed
                if metadata.encryption_enabled:
                    decrypted_path = temp_path / "decrypted_backup"
                    await self._decrypt_file(backup_path, decrypted_path)
                    backup_path = decrypted_path
                
                # Extract archive
                extract_path = temp_path / "extracted"
                extract_path.mkdir()
                
                if metadata.compression_enabled:
                    await self._extract_compressed_archive(backup_path, extract_path)
                else:
                    await self._extract_archive(backup_path, extract_path)
                
                # Restore components
                if target_path is None:
                    target_path = Path(".")
                
                # Restore database
                if (extract_path / "database").exists():
                    await self._restore_database(extract_path / "database", cities)
                
                # Restore configuration
                if (extract_path / "config").exists():
                    await self._restore_configuration(extract_path / "config", target_path)
                
                # Restore logs (optional)
                if (extract_path / "logs").exists():
                    await self._restore_logs(extract_path / "logs", target_path)
                
                self.logger.info(f"Restore completed successfully: {backup_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Restore failed: {e}")
            return False
    
    async def cleanup_old_backups(self):
        """Clean up expired backups."""
        self.logger.info("Starting backup cleanup")
        
        try:
            # Load all backup metadata
            metadata_files = list(self.backup_dir.glob("*.metadata.json"))
            current_time = datetime.utcnow()
            
            cleaned_count = 0
            for metadata_file in metadata_files:
                try:
                    with open(metadata_file, 'r') as f:
                        metadata_dict = json.load(f)
                    
                    retention_until = datetime.fromisoformat(metadata_dict['retention_until'])
                    
                    if current_time > retention_until:
                        # Remove backup file
                        backup_path = Path(metadata_dict['storage_location'])
                        if backup_path.exists():
                            backup_path.unlink()
                        
                        # Remove from S3 if configured
                        if self.s3_client:
                            await self._delete_from_s3(metadata_dict['backup_id'])
                        
                        # Remove metadata file
                        metadata_file.unlink()
                        
                        cleaned_count += 1
                        self.logger.info(f"Cleaned up expired backup: {metadata_dict['backup_id']}")
                
                except Exception as e:
                    self.logger.error(f"Failed to process backup metadata {metadata_file}: {e}")
            
            self.logger.info(f"Backup cleanup completed. Removed {cleaned_count} expired backups")
            
        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")
    
    async def get_restore_points(self) -> List[RestorePoint]:
        """Get available restore points."""
        restore_points = []
        
        try:
            metadata_files = list(self.backup_dir.glob("*.metadata.json"))
            
            for metadata_file in metadata_files:
                try:
                    with open(metadata_file, 'r') as f:
                        metadata_dict = json.load(f)
                    
                    if metadata_dict['validation_status'] == 'valid':
                        restore_point = RestorePoint(
                            backup_id=metadata_dict['backup_id'],
                            timestamp=datetime.fromisoformat(metadata_dict['timestamp']),
                            cities=metadata_dict['cities'],
                            data_integrity_score=1.0,  # Could be calculated based on validation
                            restore_time_estimate_minutes=self._estimate_restore_time(metadata_dict),
                            dependencies=[]  # Could be calculated for incremental backups
                        )
                        restore_points.append(restore_point)
                
                except Exception as e:
                    self.logger.error(f"Failed to process restore point {metadata_file}: {e}")
            
            # Sort by timestamp (newest first)
            restore_points.sort(key=lambda x: x.timestamp, reverse=True)
            
        except Exception as e:
            self.logger.error(f"Failed to get restore points: {e}")
        
        return restore_points
    
    # Helper methods for backup operations
    async def _backup_database(self, backup_path: Path, cities: List[str]):
        """Backup database data."""
        backup_path.mkdir(exist_ok=True)
        
        if not self.db_connection:
            raise Exception("Database connection not available")
        
        # Export each city's data
        for city in cities:
            city_file = backup_path / f"{city.lower()}_listings.csv"
            
            query = """
            COPY (
                SELECT * FROM listings 
                WHERE city = ? 
                ORDER BY scraped_at DESC
            ) TO ? WITH (FORMAT CSV, HEADER)
            """
            
            self.db_connection.execute(query, [city, str(city_file)])
        
        # Export schema
        schema_file = backup_path / "schema.sql"
        schema_query = "SELECT sql FROM sqlite_master WHERE type='table'"
        
        with open(schema_file, 'w') as f:
            for row in self.db_connection.execute(schema_query).fetchall():
                f.write(row[0] + ";\n")
    
    async def _backup_incremental_database(self, backup_path: Path, cities: List[str], since: datetime):
        """Backup database data incrementally."""
        backup_path.mkdir(exist_ok=True)
        
        if not self.db_connection:
            raise Exception("Database connection not available")
        
        for city in cities:
            city_file = backup_path / f"{city.lower()}_listings_incremental.csv"
            
            query = """
            COPY (
                SELECT * FROM listings 
                WHERE city = ? AND (
                    scraped_at > ? OR 
                    updated_ts > ? OR 
                    insert_ts > ?
                )
                ORDER BY scraped_at DESC
            ) TO ? WITH (FORMAT CSV, HEADER)
            """
            
            since_str = since.isoformat()
            self.db_connection.execute(query, [city, since_str, since_str, since_str, str(city_file)])
    
    async def _backup_city_database(self, backup_path: Path, city: str):
        """Backup database data for a specific city."""
        await self._backup_database(backup_path, [city])
    
    async def _backup_configuration(self, backup_path: Path):
        """Backup configuration files."""
        backup_path.mkdir(exist_ok=True)
        
        config_dir = Path("config")
        if config_dir.exists():
            shutil.copytree(config_dir, backup_path / "config")
    
    async def _backup_city_configuration(self, backup_path: Path, city: str):
        """Backup city-specific configuration."""
        backup_path.mkdir(exist_ok=True)
        
        # Extract city-specific config
        city_config = {}
        for task in self.config.get("tasks", []):
            if task.get("city") == city:
                city_config[city] = task
                break
        
        config_file = backup_path / f"{city.lower()}_config.json"
        with open(config_file, 'w') as f:
            json.dump(city_config, f, indent=2)
    
    async def _backup_logs(self, backup_path: Path):
        """Backup recent log files."""
        backup_path.mkdir(exist_ok=True)
        
        logs_dir = Path("logs")
        if logs_dir.exists():
            # Copy only recent log files (last 7 days)
            cutoff_time = datetime.utcnow() - timedelta(days=7)
            
            for log_file in logs_dir.glob("*.log"):
                if log_file.stat().st_mtime > cutoff_time.timestamp():
                    shutil.copy2(log_file, backup_path / log_file.name)
    
    async def _backup_recent_logs(self, backup_path: Path, since: datetime):
        """Backup logs since specified timestamp."""
        backup_path.mkdir(exist_ok=True)
        
        logs_dir = Path("logs")
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                if log_file.stat().st_mtime > since.timestamp():
                    shutil.copy2(log_file, backup_path / log_file.name)
    
    async def _create_archive(self, source_path: Path, archive_path: Path):
        """Create tar archive."""
        with tarfile.open(archive_path, 'w') as tar:
            tar.add(source_path, arcname='.')
    
    async def _create_compressed_archive(self, source_path: Path, archive_path: Path):
        """Create compressed tar archive."""
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(source_path, arcname='.')
    
    async def _extract_archive(self, archive_path: Path, extract_path: Path):
        """Extract tar archive."""
        with tarfile.open(archive_path, 'r') as tar:
            tar.extractall(extract_path)
    
    async def _extract_compressed_archive(self, archive_path: Path, extract_path: Path):
        """Extract compressed tar archive."""
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(extract_path)
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    async def _encrypt_file(self, source_path: Path, encrypted_path: Path):
        """Encrypt file using Fernet."""
        with open(source_path, 'rb') as source_file:
            data = source_file.read()
        
        encrypted_data = self.fernet.encrypt(data)
        
        with open(encrypted_path, 'wb') as encrypted_file:
            encrypted_file.write(encrypted_data)
    
    async def _decrypt_file(self, encrypted_path: Path, decrypted_path: Path):
        """Decrypt file using Fernet."""
        with open(encrypted_path, 'rb') as encrypted_file:
            encrypted_data = encrypted_file.read()
        
        decrypted_data = self.fernet.decrypt(encrypted_data)
        
        with open(decrypted_path, 'wb') as decrypted_file:
            decrypted_file.write(decrypted_data)
    
    async def _save_backup_metadata(self, metadata: BackupMetadata):
        """Save backup metadata to file."""
        metadata_file = self.backup_dir / f"{metadata.backup_id}.metadata.json"
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)
    
    async def _load_backup_metadata(self, backup_id: str) -> Optional[BackupMetadata]:
        """Load backup metadata from file."""
        metadata_file = self.backup_dir / f"{backup_id}.metadata.json"
        
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                metadata_dict = json.load(f)
            
            # Convert back to BackupMetadata object
            metadata_dict['timestamp'] = datetime.fromisoformat(metadata_dict['timestamp'])
            metadata_dict['retention_until'] = datetime.fromisoformat(metadata_dict['retention_until'])
            
            return BackupMetadata(**metadata_dict)
            
        except Exception as e:
            self.logger.error(f"Failed to load backup metadata: {e}")
            return None
    
    async def _validate_backup(self, metadata: BackupMetadata) -> bool:
        """Validate backup integrity."""
        try:
            backup_path = Path(metadata.storage_location)
            
            if not backup_path.exists():
                return False
            
            # Verify checksum
            current_checksum = await self._calculate_checksum(backup_path)
            if current_checksum != metadata.checksum:
                self.logger.error(f"Checksum mismatch for backup {metadata.backup_id}")
                return False
            
            # Additional validation could include:
            # - Attempting to extract and verify archive structure
            # - Testing decryption if encrypted
            # - Validating data format
            
            return True
            
        except Exception as e:
            self.logger.error(f"Backup validation failed: {e}")
            return False
    
    async def _upload_to_s3(self, file_path: Path, metadata: BackupMetadata):
        """Upload backup to S3."""
        if not self.s3_client:
            return
        
        s3_config = self.backup_config.get("s3", {})
        bucket = s3_config.get("bucket")
        
        if not bucket:
            return
        
        try:
            s3_key = f"backups/{metadata.backup_id}/{file_path.name}"
            
            self.s3_client.upload_file(
                str(file_path),
                bucket,
                s3_key,
                ExtraArgs={
                    'StorageClass': s3_config.get("storage_class", "STANDARD_IA"),
                    'ServerSideEncryption': 'AES256' if s3_config.get("server_side_encryption") else None
                }
            )
            
            # Upload metadata
            metadata_key = f"backups/{metadata.backup_id}/metadata.json"
            metadata_content = json.dumps(metadata.to_dict(), indent=2)
            
            self.s3_client.put_object(
                Bucket=bucket,
                Key=metadata_key,
                Body=metadata_content,
                ContentType='application/json'
            )
            
            self.logger.info(f"Backup uploaded to S3: {s3_key}")
            
        except Exception as e:
            self.logger.error(f"S3 upload failed: {e}")
    
    async def _download_from_s3(self, local_path: Path, metadata: BackupMetadata):
        """Download backup from S3."""
        if not self.s3_client:
            return
        
        s3_config = self.backup_config.get("s3", {})
        bucket = s3_config.get("bucket")
        
        if not bucket:
            return
        
        try:
            s3_key = f"backups/{metadata.backup_id}/{local_path.name}"
            
            self.s3_client.download_file(bucket, s3_key, str(local_path))
            self.logger.info(f"Backup downloaded from S3: {s3_key}")
            
        except Exception as e:
            self.logger.error(f"S3 download failed: {e}")
            raise
    
    async def _delete_from_s3(self, backup_id: str):
        """Delete backup from S3."""
        if not self.s3_client:
            return
        
        s3_config = self.backup_config.get("s3", {})
        bucket = s3_config.get("bucket")
        
        if not bucket:
            return
        
        try:
            # List and delete all objects with the backup prefix
            prefix = f"backups/{backup_id}/"
            
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            
            if 'Contents' in response:
                objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
                
                self.s3_client.delete_objects(
                    Bucket=bucket,
                    Delete={'Objects': objects_to_delete}
                )
                
                self.logger.info(f"Backup deleted from S3: {backup_id}")
            
        except Exception as e:
            self.logger.error(f"S3 deletion failed: {e}")
    
    async def _restore_database(self, backup_path: Path, cities: Optional[List[str]] = None):
        """Restore database from backup."""
        if not self.db_connection:
            raise Exception("Database connection not available")
        
        # This is a simplified restore - in production, you'd want more sophisticated logic
        # to handle schema changes, data conflicts, etc.
        
        for csv_file in backup_path.glob("*.csv"):
            city_name = csv_file.stem.replace("_listings", "").replace("_incremental", "")
            
            if cities and city_name not in cities:
                continue
            
            # Import CSV data
            # Note: This is a simplified approach - production would need more robust handling
            import_query = f"""
            CREATE OR REPLACE TABLE temp_import AS 
            SELECT * FROM read_csv_auto('{csv_file}')
            """
            
            self.db_connection.execute(import_query)
            
            # Merge with existing data (simplified)
            merge_query = """
            INSERT OR REPLACE INTO listings 
            SELECT * FROM temp_import
            """
            
            self.db_connection.execute(merge_query)
            self.db_connection.execute("DROP TABLE temp_import")
    
    async def _restore_configuration(self, backup_path: Path, target_path: Path):
        """Restore configuration files."""
        config_backup = backup_path / "config"
        if config_backup.exists():
            target_config = target_path / "config"
            if target_config.exists():
                shutil.rmtree(target_config)
            shutil.copytree(config_backup, target_config)
    
    async def _restore_logs(self, backup_path: Path, target_path: Path):
        """Restore log files."""
        target_logs = target_path / "logs"
        target_logs.mkdir(exist_ok=True)
        
        for log_file in backup_path.glob("*.log"):
            shutil.copy2(log_file, target_logs / log_file.name)
    
    def _estimate_restore_time(self, metadata_dict: Dict[str, Any]) -> int:
        """Estimate restore time in minutes based on backup size and type."""
        size_mb = metadata_dict['size_bytes'] / (1024 * 1024)
        backup_type = metadata_dict['backup_type']
        
        # Simple estimation - could be more sophisticated
        base_time = size_mb / 100  # Assume 100MB/minute processing
        
        if backup_type == "full":
            return int(base_time * 1.5)  # Full restores take longer
        elif backup_type == "incremental":
            return int(base_time * 0.8)  # Incremental restores are faster
        else:
            return int(base_time)


async def main():
    """Main backup function for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backup and disaster recovery manager")
    parser.add_argument("action", choices=["backup", "restore", "cleanup", "list"], help="Action to perform")
    parser.add_argument("--type", choices=["full", "incremental", "city"], default="full", help="Backup type")
    parser.add_argument("--city", help="City for city-specific operations")
    parser.add_argument("--backup-id", help="Backup ID for restore operations")
    parser.add_argument("--since", help="Since timestamp for incremental backup (ISO format)")
    
    args = parser.parse_args()
    
    backup_manager = BackupManager()
    
    if args.action == "backup":
        if args.type == "full":
            metadata = await backup_manager.create_full_backup()
            print(f"Full backup created: {metadata.backup_id}")
        elif args.type == "incremental":
            if not args.since:
                print("--since parameter required for incremental backup")
                return
            since = datetime.fromisoformat(args.since)
            metadata = await backup_manager.create_incremental_backup(since)
            print(f"Incremental backup created: {metadata.backup_id}")
        elif args.type == "city":
            if not args.city:
                print("--city parameter required for city backup")
                return
            metadata = await backup_manager.create_city_backup(args.city)
            print(f"City backup created: {metadata.backup_id}")
    
    elif args.action == "restore":
        if not args.backup_id:
            print("--backup-id parameter required for restore")
            return
        
        cities = [args.city] if args.city else None
        success = await backup_manager.restore_from_backup(args.backup_id, cities=cities)
        print(f"Restore {'successful' if success else 'failed'}")
    
    elif args.action == "cleanup":
        await backup_manager.cleanup_old_backups()
        print("Backup cleanup completed")
    
    elif args.action == "list":
        restore_points = await backup_manager.get_restore_points()
        print(f"Available restore points ({len(restore_points)}):")
        for rp in restore_points:
            print(f"  {rp.backup_id} - {rp.timestamp} - Cities: {', '.join(rp.cities)}")


if __name__ == "__main__":
    asyncio.run(main())
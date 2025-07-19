"""
Backup and Disaster Recovery System

This module provides comprehensive backup and disaster recovery capabilities
for the daily scraper automation system.
"""

import json
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from loguru import logger


class BackupManager:
    """Backup and disaster recovery system."""
    
    def __init__(self, config, credential_manager=None):
        """
        Initialize backup manager.
        
        Args:
            config: Security configuration
            credential_manager: Credential manager for encryption
        """
        self.config = config
        self.credential_manager = credential_manager
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Backup manager initialized")
    
    def create_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a comprehensive system backup.
        
        Args:
            backup_name: Optional backup name (generates timestamp-based name if None)
            
        Returns:
            Backup operation results
        """
        if not self.config.backup_enabled:
            return {"status": "disabled", "message": "Backup is disabled"}
        
        if backup_name is None:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating backup: {backup_name}")
        backup_start = datetime.now()
        
        results = {
            'backup_name': backup_name,
            'backup_path': str(backup_path),
            'timestamp': backup_start.isoformat(),
            'components': {},
            'total_size_mb': 0,
            'status': 'success'
        }
        
        try:
            # Backup database
            results['components']['database'] = self._backup_database(backup_path)
            
            # Backup configuration
            results['components']['configuration'] = self._backup_configuration(backup_path)
            
            # Backup logs (recent only)
            results['components']['logs'] = self._backup_logs(backup_path)
            
            # Backup security data
            results['components']['security'] = self._backup_security_data(backup_path)
            
            # Calculate total size
            total_size = sum(
                f.stat().st_size 
                for f in Path(backup_path).rglob('*') if f.is_file()
            )
            results['total_size_mb'] = total_size / (1024 * 1024)
            
            # Create backup manifest
            manifest = {
                'backup_name': backup_name,
                'created_at': backup_start.isoformat(),
                'components': results['components'],
                'total_size_mb': results['total_size_mb'],
                'backup_version': '1.0'
            }
            
            manifest_path = backup_path / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest, indent=2))
            
            # Encrypt backup if enabled
            if self.config.backup_encryption_enabled and self.credential_manager:
                results['encryption'] = self._encrypt_backup(backup_path)
            
            backup_duration = (datetime.now() - backup_start).total_seconds()
            results['duration_seconds'] = backup_duration
            
            logger.success(f"Backup completed: {backup_name} ({results['total_size_mb']:.1f} MB in {backup_duration:.1f}s)")
            
        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
            logger.error(f"Backup failed: {e}")
        
        return results
    
    def _backup_database(self, backup_path: Path) -> Dict[str, Any]:
        """Backup database files."""
        db_backup_path = backup_path / 'database'
        db_backup_path.mkdir(exist_ok=True)
        
        result = {'status': 'success', 'files': [], 'size_mb': 0}
        
        try:
            # Database files to backup
            db_files = [
                'data/real_estate.duckdb',
                'data/real_estate.duckdb.wal'
            ]
            
            for db_file in db_files:
                source_path = Path(db_file)
                if source_path.exists():
                    dest_path = db_backup_path / source_path.name
                    
                    # Copy file
                    shutil.copy2(source_path, dest_path)
                    
                    file_size = dest_path.stat().st_size / (1024 * 1024)
                    result['files'].append({
                        'file': db_file,
                        'size_mb': file_size
                    })
                    result['size_mb'] += file_size
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def _backup_configuration(self, backup_path: Path) -> Dict[str, Any]:
        """Backup configuration files."""
        config_backup_path = backup_path / 'configuration'
        config_backup_path.mkdir(exist_ok=True)
        
        result = {'status': 'success', 'files': [], 'size_mb': 0}
        
        try:
            # Configuration files to backup
            config_files = [
                'config/scraper_config.json',
                'config/scraper_config.local.json',
                'config/alert_config.json'
            ]
            
            for config_file in config_files:
                source_path = Path(config_file)
                if source_path.exists():
                    dest_path = config_backup_path / source_path.name
                    
                    shutil.copy2(source_path, dest_path)
                    
                    file_size = dest_path.stat().st_size / (1024 * 1024)
                    result['files'].append({
                        'file': config_file,
                        'size_mb': file_size
                    })
                    result['size_mb'] += file_size
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def _backup_logs(self, backup_path: Path) -> Dict[str, Any]:
        """Backup recent log files."""
        logs_backup_path = backup_path / 'logs'
        logs_backup_path.mkdir(exist_ok=True)
        
        result = {'status': 'success', 'files': [], 'size_mb': 0}
        
        try:
            # Get recent log files (last 7 days)
            logs_dir = Path('logs')
            if logs_dir.exists():
                cutoff_time = datetime.now() - timedelta(days=7)
                
                for log_file in logs_dir.glob('*.log*'):
                    if log_file.is_file():
                        file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                        if file_time >= cutoff_time:
                            dest_path = logs_backup_path / log_file.name
                            
                            shutil.copy2(log_file, dest_path)
                            
                            file_size = dest_path.stat().st_size / (1024 * 1024)
                            result['files'].append({
                                'file': str(log_file),
                                'size_mb': file_size
                            })
                            result['size_mb'] += file_size
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def _backup_security_data(self, backup_path: Path) -> Dict[str, Any]:
        """Backup security-related data."""
        security_backup_path = backup_path / 'security'
        security_backup_path.mkdir(exist_ok=True)
        
        result = {'status': 'success', 'files': [], 'size_mb': 0}
        
        try:
            # Security files to backup (encrypted credentials only, not keys)
            security_files = [
                '.security/credentials.enc'
            ]
            
            for security_file in security_files:
                source_path = Path(security_file)
                if source_path.exists():
                    dest_path = security_backup_path / source_path.name
                    
                    shutil.copy2(source_path, dest_path)
                    
                    file_size = dest_path.stat().st_size / (1024 * 1024)
                    result['files'].append({
                        'file': security_file,
                        'size_mb': file_size
                    })
                    result['size_mb'] += file_size
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def _encrypt_backup(self, backup_path: Path) -> Dict[str, Any]:
        """Encrypt backup directory."""
        result = {'status': 'success', 'encrypted_files': 0}
        
        try:
            # This is a placeholder for backup encryption
            # In production, you'd use tools like gpg or implement file-by-file encryption
            result['message'] = 'Backup encryption not implemented - use external tools'
            result['status'] = 'skipped'
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups."""
        backups = []
        
        try:
            for backup_dir in self.backup_dir.iterdir():
                if backup_dir.is_dir():
                    manifest_path = backup_dir / 'manifest.json'
                    
                    if manifest_path.exists():
                        try:
                            manifest = json.loads(manifest_path.read_text())
                            backups.append(manifest)
                        except Exception as e:
                            logger.warning(f"Failed to read backup manifest {manifest_path}: {e}")
                    else:
                        # Create basic info for backups without manifest
                        backups.append({
                            'backup_name': backup_dir.name,
                            'created_at': datetime.fromtimestamp(backup_dir.stat().st_mtime).isoformat(),
                            'has_manifest': False
                        })
        
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
        
        return sorted(backups, key=lambda x: x.get('created_at', ''), reverse=True)
    
    def cleanup_old_backups(self) -> Dict[str, Any]:
        """Clean up old backups based on retention policy."""
        if not self.config.backup_enabled:
            return {"status": "disabled", "message": "Backup is disabled"}
        
        result = {'deleted_backups': [], 'kept_backups': [], 'errors': []}
        
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.backup_retention_days)
            
            for backup_dir in self.backup_dir.iterdir():
                if backup_dir.is_dir():
                    try:
                        backup_time = datetime.fromtimestamp(backup_dir.stat().st_mtime)
                        
                        if backup_time < cutoff_date:
                            # Delete old backup
                            shutil.rmtree(backup_dir)
                            result['deleted_backups'].append({
                                'name': backup_dir.name,
                                'date': backup_time.isoformat()
                            })
                            logger.info(f"Deleted old backup: {backup_dir.name}")
                        else:
                            result['kept_backups'].append({
                                'name': backup_dir.name,
                                'date': backup_time.isoformat()
                            })
                    
                    except Exception as e:
                        result['errors'].append(f"Error processing {backup_dir.name}: {e}")
        
        except Exception as e:
            result['errors'].append(f"Error during cleanup: {e}")
        
        return result
#!/usr/bin/env python3
"""
Standalone Daily Automation Script for Oikotie Real Estate Scraper

This script runs the complete daily automation process, compares results with previous runs,
generates statistics, and sets up automated scheduling.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'automation_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from oikotie.database.manager import EnhancedDatabaseManager
    from oikotie.automation.production_deployment import create_production_deployment
    from oikotie.automation.deployment import DeploymentType
    from oikotie.automation.orchestrator import load_config_and_create_orchestrators
    from oikotie.automation.multi_city_orchestrator import create_multi_city_orchestrator
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure you're running from the project root directory")
    sys.exit(1)


class DailyAutomationRunner:
    """Standalone daily automation runner with statistics and scheduling."""
    
    def __init__(self):
        """Initialize the automation runner."""
        self.start_time = datetime.now()
        self.db_manager = None
        self.deployment_manager = None
        self.results_file = f"automation_results_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        self.stats_file = f"automation_stats_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        
        # Create required directories
        for directory in ['data', 'logs', 'output', 'backups', 'results']:
            Path(directory).mkdir(exist_ok=True)
        
        logger.info("Daily Automation Runner initialized")
    
    def get_current_database_state(self) -> Dict[str, Any]:
        """Get current database state before running automation."""
        logger.info("Checking current database state...")
        
        try:
            self.db_manager = EnhancedDatabaseManager()
            
            with self.db_manager.get_connection() as conn:
                # Get total listings count
                total_result = conn.execute('SELECT COUNT(*) FROM listings').fetchall()
                total_listings = total_result[0][0] if total_result else 0
                
                # Get listings by city
                city_result = conn.execute('''
                    SELECT city, COUNT(*) as count 
                    FROM listings 
                    WHERE city IS NOT NULL 
                    GROUP BY city 
                    ORDER BY count DESC
                ''').fetchall()
                
                city_stats = {row[0]: row[1] for row in city_result}
                
                # Get recent listings (last 24 hours)
                yesterday = datetime.now() - timedelta(days=1)
                recent_result = conn.execute('''
                    SELECT COUNT(*) 
                    FROM listings 
                    WHERE scraped_at > ?
                ''', (yesterday,)).fetchall()
                
                recent_listings = recent_result[0][0] if recent_result else 0
                
                # Get execution history
                exec_result = conn.execute('SELECT COUNT(*) FROM scraping_executions').fetchall()
                total_executions = exec_result[0][0] if exec_result else 0
                
                # Get last execution
                last_exec_result = conn.execute('''
                    SELECT started_at, city, listings_new, listings_failed, status
                    FROM scraping_executions 
                    ORDER BY started_at DESC 
                    LIMIT 1
                ''').fetchall()
                
                last_execution = None
                if last_exec_result:
                    row = last_exec_result[0]
                    last_execution = {
                        'started_at': str(row[0]),
                        'city': row[1],
                        'listings_new': row[2],
                        'listings_failed': row[3],
                        'status': row[4]
                    }
                
                state = {
                    'timestamp': self.start_time.isoformat(),
                    'total_listings': total_listings,
                    'city_breakdown': city_stats,
                    'recent_listings_24h': recent_listings,
                    'total_executions': total_executions,
                    'last_execution': last_execution
                }
                
                logger.info(f"Current database state: {total_listings} total listings")
                for city, count in city_stats.items():
                    logger.info(f"  {city}: {count} listings")
                
                return state
                
        except Exception as e:
            logger.error(f"Failed to get database state: {e}")
            return {
                'timestamp': self.start_time.isoformat(),
                'error': str(e),
                'total_listings': 0,
                'city_breakdown': {},
                'recent_listings_24h': 0,
                'total_executions': 0,
                'last_execution': None
            }
    
    def run_daily_automation(self) -> Dict[str, Any]:
        """Run the daily automation process using enhanced multi-city orchestrator."""
        logger.info("Starting enhanced multi-city daily automation process...")
        
        try:
            # Get Redis URL from global settings if available
            redis_url = None
            try:
                with open('config/config.json', 'r') as f:
                    config = json.load(f)
                    redis_url = config.get('global_settings', {}).get('cluster_coordination', {}).get('redis_url')
            except Exception:
                logger.info("No Redis configuration found, running without cluster coordination")
            
            # Create multi-city orchestrator
            orchestrator = create_multi_city_orchestrator(
                config_path='config/config.json',
                redis_url=redis_url,
                enable_cluster_coordination=redis_url is not None
            )
            
            # Run daily automation
            result = orchestrator.run_daily_automation()
            
            logger.info(f"Multi-city automation completed with status: {result.status.value}")
            logger.info(f"Execution ID: {result.execution_id}")
            logger.info(f"Cities: {result.successful_cities}/{result.total_cities} successful")
            logger.info(f"New listings: {result.total_listings_new}")
            
            # Convert result to dictionary format expected by existing code
            return {
                'status': result.status.value,
                'execution_id': result.execution_id,
                'started_at': result.started_at.isoformat(),
                'completed_at': result.completed_at.isoformat() if result.completed_at else None,
                'total_new': result.total_listings_new,
                'total_failed': result.total_listings_failed,
                'city_results': [
                    {
                        'city': city_result.city,
                        'status': city_result.status.value,
                        'listings_new': city_result.listings_new,
                        'listings_failed': city_result.listings_failed,
                        'execution_time': city_result.execution_time_seconds or 0
                    }
                    for city_result in result.city_results
                ]
            }
            
        except Exception as e:
            logger.error(f"Multi-city automation failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'execution_id': f"failed_{int(time.time())}",
                'started_at': self.start_time.isoformat(),
                'completed_at': datetime.now().isoformat(),
                'total_new': 0,
                'total_failed': 0,
                'city_results': []
            }
    
    def get_post_automation_state(self) -> Dict[str, Any]:
        """Get database state after automation."""
        logger.info("Checking post-automation database state...")
        
        try:
            with self.db_manager.get_connection() as conn:
                # Get updated total listings count
                total_result = conn.execute('SELECT COUNT(*) FROM listings').fetchall()
                total_listings = total_result[0][0] if total_result else 0
                
                # Get updated listings by city
                city_result = conn.execute('''
                    SELECT city, COUNT(*) as count 
                    FROM listings 
                    WHERE city IS NOT NULL 
                    GROUP BY city 
                    ORDER BY count DESC
                ''').fetchall()
                
                city_stats = {row[0]: row[1] for row in city_result}
                
                # Get very recent listings (last hour)
                one_hour_ago = datetime.now() - timedelta(hours=1)
                recent_result = conn.execute('''
                    SELECT COUNT(*) 
                    FROM listings 
                    WHERE scraped_at > ?
                ''', (one_hour_ago,)).fetchall()
                
                very_recent_listings = recent_result[0][0] if recent_result else 0
                
                state = {
                    'timestamp': datetime.now().isoformat(),
                    'total_listings': total_listings,
                    'city_breakdown': city_stats,
                    'very_recent_listings_1h': very_recent_listings
                }
                
                logger.info(f"Post-automation state: {total_listings} total listings")
                
                return state
                
        except Exception as e:
            logger.error(f"Failed to get post-automation state: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'total_listings': 0,
                'city_breakdown': {},
                'very_recent_listings_1h': 0
            }
    
    def calculate_statistics(self, 
                           pre_state: Dict[str, Any], 
                           post_state: Dict[str, Any], 
                           automation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive statistics."""
        logger.info("Calculating automation statistics...")
        
        # Calculate differences
        total_difference = post_state.get('total_listings', 0) - pre_state.get('total_listings', 0)
        
        # Calculate city-specific differences
        city_differences = {}
        pre_cities = pre_state.get('city_breakdown', {})
        post_cities = post_state.get('city_breakdown', {})
        
        all_cities = set(pre_cities.keys()) | set(post_cities.keys())
        for city in all_cities:
            pre_count = pre_cities.get(city, 0)
            post_count = post_cities.get(city, 0)
            city_differences[city] = post_count - pre_count
        
        # Calculate execution time
        start_time = datetime.fromisoformat(automation_result.get('started_at', self.start_time.isoformat()))
        end_time = datetime.fromisoformat(automation_result.get('completed_at', datetime.now().isoformat()))
        execution_time_seconds = (end_time - start_time).total_seconds()
        
        # Calculate success rate
        total_processed = automation_result.get('total_new', 0) + automation_result.get('total_failed', 0)
        success_rate = (automation_result.get('total_new', 0) / total_processed * 100) if total_processed > 0 else 0
        
        statistics = {
            'execution_summary': {
                'execution_id': automation_result.get('execution_id'),
                'status': automation_result.get('status'),
                'started_at': automation_result.get('started_at'),
                'completed_at': automation_result.get('completed_at'),
                'execution_time_seconds': execution_time_seconds,
                'execution_time_formatted': f"{execution_time_seconds:.1f}s"
            },
            'listing_changes': {
                'total_difference': total_difference,
                'reported_new': automation_result.get('total_new', 0),
                'reported_failed': automation_result.get('total_failed', 0),
                'city_differences': city_differences
            },
            'database_state': {
                'before': {
                    'total_listings': pre_state.get('total_listings', 0),
                    'city_breakdown': pre_state.get('city_breakdown', {}),
                    'recent_24h': pre_state.get('recent_listings_24h', 0)
                },
                'after': {
                    'total_listings': post_state.get('total_listings', 0),
                    'city_breakdown': post_state.get('city_breakdown', {}),
                    'very_recent_1h': post_state.get('very_recent_listings_1h', 0)
                }
            },
            'performance_metrics': {
                'success_rate_percent': round(success_rate, 2),
                'total_processed': total_processed,
                'processing_rate_per_second': round(total_processed / execution_time_seconds, 2) if execution_time_seconds > 0 else 0
            },
            'city_results': automation_result.get('city_results', [])
        }
        
        return statistics
    
    def save_results(self, 
                    pre_state: Dict[str, Any], 
                    post_state: Dict[str, Any], 
                    automation_result: Dict[str, Any], 
                    statistics: Dict[str, Any]) -> None:
        """Save all results to files."""
        logger.info("Saving automation results...")
        
        # Complete results file
        complete_results = {
            'automation_run': {
                'timestamp': self.start_time.isoformat(),
                'script_version': '1.0.0',
                'execution_id': automation_result.get('execution_id')
            },
            'pre_automation_state': pre_state,
            'automation_result': automation_result,
            'post_automation_state': post_state,
            'statistics': statistics
        }
        
        # Save complete results
        results_path = Path('results') / self.results_file
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(complete_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Complete results saved to: {results_path}")
        
        # Save statistics summary
        stats_path = Path('results') / self.stats_file
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(statistics, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Statistics saved to: {stats_path}")
        
        # Create human-readable summary
        summary_file = f"automation_summary_{self.start_time.strftime('%Y%m%d_%H%M%S')}.txt"
        summary_path = Path('results') / summary_file
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("OIKOTIE DAILY AUTOMATION SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Execution Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Execution ID: {automation_result.get('execution_id')}\n")
            f.write(f"Status: {automation_result.get('status', 'unknown').upper()}\n")
            f.write(f"Duration: {statistics['execution_summary']['execution_time_formatted']}\n\n")
            
            f.write("LISTING STATISTICS:\n")
            f.write("-" * 20 + "\n")
            f.write(f"Total listings before: {pre_state.get('total_listings', 0):,}\n")
            f.write(f"Total listings after:  {post_state.get('total_listings', 0):,}\n")
            f.write(f"Net change:           {statistics['listing_changes']['total_difference']:+,}\n")
            f.write(f"Reported new:         {automation_result.get('total_new', 0):,}\n")
            f.write(f"Reported failed:      {automation_result.get('total_failed', 0):,}\n\n")
            
            f.write("CITY BREAKDOWN:\n")
            f.write("-" * 15 + "\n")
            for city, difference in statistics['listing_changes']['city_differences'].items():
                before = pre_state.get('city_breakdown', {}).get(city, 0)
                after = post_state.get('city_breakdown', {}).get(city, 0)
                f.write(f"{city:12}: {before:6,} → {after:6,} ({difference:+,})\n")
            
            f.write(f"\nPERFORMANCE:\n")
            f.write("-" * 12 + "\n")
            f.write(f"Success rate:     {statistics['performance_metrics']['success_rate_percent']:.1f}%\n")
            f.write(f"Processing rate:  {statistics['performance_metrics']['processing_rate_per_second']:.1f} listings/sec\n")
            f.write(f"Total processed:  {statistics['performance_metrics']['total_processed']:,}\n\n")
            
            if automation_result.get('city_results'):
                f.write("CITY RESULTS:\n")
                f.write("-" * 13 + "\n")
                for city_result in automation_result['city_results']:
                    f.write(f"{city_result.get('city', 'Unknown'):12}: ")
                    f.write(f"{city_result.get('listings_new', 0):3} new, ")
                    f.write(f"{city_result.get('listings_failed', 0):3} failed, ")
                    f.write(f"{city_result.get('execution_time', 0):.1f}s\n")
            
            f.write(f"\nFiles generated:\n")
            f.write(f"- Complete results: {results_path}\n")
            f.write(f"- Statistics: {stats_path}\n")
            f.write(f"- Summary: {summary_path}\n")
        
        logger.info(f"Human-readable summary saved to: {summary_path}")
        
        # Print summary to console
        print("\n" + "=" * 60)
        print("AUTOMATION COMPLETED")
        print("=" * 60)
        print(f"Status: {automation_result.get('status', 'unknown').upper()}")
        print(f"Duration: {statistics['execution_summary']['execution_time_formatted']}")
        print(f"New listings: {automation_result.get('total_new', 0):,}")
        print(f"Failed: {automation_result.get('total_failed', 0):,}")
        print(f"Net database change: {statistics['listing_changes']['total_difference']:+,}")
        print(f"Success rate: {statistics['performance_metrics']['success_rate_percent']:.1f}%")
        print(f"\nResults saved to: results/")
        print("=" * 60)
    
    def setup_cron_job(self) -> bool:
        """Setup automated cron job for daily execution."""
        logger.info("Setting up automated scheduling...")
        
        try:
            script_path = Path(__file__).absolute()
            project_root = script_path.parent.parent.parent
            
            # Create wrapper script for cron
            wrapper_script = project_root / "run_daily_cron.sh"
            
            wrapper_content = f"""#!/bin/bash
# Oikotie Daily Automation Cron Wrapper
# Generated on {datetime.now().isoformat()}

cd "{project_root}"
export PATH="$PATH:{project_root}/.venv/bin"

# Log start
echo "$(date): Starting daily automation" >> logs/cron.log

# Run automation
python3 "{script_path}" >> logs/cron.log 2>&1

# Log completion
echo "$(date): Daily automation completed" >> logs/cron.log
"""
            
            with open(wrapper_script, 'w') as f:
                f.write(wrapper_content)
            
            # Make executable
            os.chmod(wrapper_script, 0o755)
            
            # Create cron entry
            cron_entry = f"0 6 * * * {wrapper_script}  # Oikotie daily automation at 6 AM"
            
            cron_file = project_root / "oikotie_cron.txt"
            with open(cron_file, 'w') as f:
                f.write(cron_entry + "\n")
            
            logger.info(f"Cron wrapper script created: {wrapper_script}")
            logger.info(f"Cron entry saved to: {cron_file}")
            
            print(f"\nTo enable daily automation at 6 AM, run:")
            print(f"crontab {cron_file}")
            print(f"\nOr manually add this line to your crontab:")
            print(f"{cron_entry}")
            
            # For Windows, create a task scheduler script
            if os.name == 'nt':
                task_script = project_root / "setup_windows_task.bat"
                task_content = f"""@echo off
REM Oikotie Daily Automation Windows Task Setup
REM Generated on {datetime.now().isoformat()}

echo Setting up Windows Task Scheduler for Oikotie Daily Automation...

schtasks /create /tn "Oikotie Daily Automation" /tr "python \\"{script_path}\\"" /sc daily /st 06:00 /f

echo Task created successfully!
echo The automation will run daily at 6:00 AM
pause
"""
                
                with open(task_script, 'w') as f:
                    f.write(task_content)
                
                logger.info(f"Windows task script created: {task_script}")
                print(f"\nFor Windows, run as administrator: {task_script}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup scheduling: {e}")
            return False
    
    def create_startup_script(self) -> bool:
        """Create startup script for system boot."""
        logger.info("Creating startup script...")
        
        try:
            script_path = Path(__file__).absolute()
            project_root = script_path.parent.parent.parent
            
            # Create systemd service file (Linux)
            service_content = f"""[Unit]
Description=Oikotie Daily Automation
After=network.target

[Service]
Type=oneshot
User={os.getenv('USER', 'oikotie')}
WorkingDirectory={project_root}
ExecStart=/usr/bin/python3 {script_path}
Environment=PATH={project_root}/.venv/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
"""
            
            service_file = project_root / "oikotie-automation.service"
            with open(service_file, 'w') as f:
                f.write(service_content)
            
            logger.info(f"Systemd service file created: {service_file}")
            
            print(f"\nTo enable startup automation (Linux), run as root:")
            print(f"cp {service_file} /etc/systemd/system/")
            print(f"systemctl enable oikotie-automation.service")
            print(f"systemctl start oikotie-automation.service")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create startup script: {e}")
            return False
    
    def run_complete_process(self) -> None:
        """Run the complete automation process."""
        logger.info("Starting complete daily automation process...")
        
        try:
            # Step 1: Get pre-automation state
            pre_state = self.get_current_database_state()
            
            # Step 2: Run daily automation
            automation_result = self.run_daily_automation()
            
            # Step 3: Get post-automation state
            post_state = self.get_post_automation_state()
            
            # Step 4: Calculate statistics
            statistics = self.calculate_statistics(pre_state, post_state, automation_result)
            
            # Step 5: Save all results
            self.save_results(pre_state, post_state, automation_result, statistics)
            
            # Step 6: Setup scheduling (only on first run or if requested)
            if '--setup-cron' in sys.argv:
                self.setup_cron_job()
            
            if '--setup-startup' in sys.argv:
                self.create_startup_script()
            
            # Step 7: Create backup if successful
            if automation_result.get('status') == 'completed' and self.deployment_manager:
                try:
                    backup_path = self.deployment_manager.create_backup()
                    logger.info(f"Backup created: {backup_path}")
                except Exception as e:
                    logger.warning(f"Backup creation failed: {e}")
            
            logger.info("Complete automation process finished successfully")
            
        except Exception as e:
            logger.error(f"Complete automation process failed: {e}")
            
            # Save error state
            error_result = {
                'status': 'failed',
                'error': str(e),
                'execution_id': f"error_{int(time.time())}",
                'started_at': self.start_time.isoformat(),
                'completed_at': datetime.now().isoformat(),
                'total_new': 0,
                'total_failed': 0,
                'city_results': []
            }
            
            try:
                post_state = self.get_post_automation_state()
                statistics = self.calculate_statistics({}, post_state, error_result)
                self.save_results({}, post_state, error_result, statistics)
            except Exception as save_error:
                logger.error(f"Failed to save error results: {save_error}")
            
            sys.exit(1)


def main():
    """Main entry point."""
    print("Oikotie Daily Automation Runner")
    print("=" * 40)
    
    # Check for setup flags
    if '--setup-cron' in sys.argv:
        print("Will setup cron job after automation")
    if '--setup-startup' in sys.argv:
        print("Will setup startup script after automation")
    
    # Run the complete process
    runner = DailyAutomationRunner()
    runner.run_complete_process()


if __name__ == "__main__":
    main()
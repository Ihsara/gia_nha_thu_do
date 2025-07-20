"""
Centralized psutil compatibility module for automation system.

This module provides a unified psutil import with fallback handling
to ensure all automation components work even when psutil is not available.
"""

from loguru import logger

# Import psutil with comprehensive fallback handling
try:
    import psutil
    # Check if psutil has the expected attributes
    if hasattr(psutil, 'cpu_percent') and hasattr(psutil, 'virtual_memory'):
        PSUTIL_AVAILABLE = True
        logger.debug("psutil available - full system monitoring enabled")
    else:
        logger.warning("psutil available but missing expected attributes - using mock system monitoring")
        PSUTIL_AVAILABLE = False
        raise ImportError("psutil missing expected attributes")
except ImportError:
    logger.warning("psutil not available - using mock system monitoring")
    PSUTIL_AVAILABLE = False
    
    # Comprehensive mock psutil for when it's not available
    class MockPsutil:
        @staticmethod
        def cpu_percent(interval=None):
            return 0.0
        
        @staticmethod
        def virtual_memory():
            class MockMemory:
                percent = 0.0
                total = 1024 * 1024 * 1024  # 1GB
                available = 1024 * 1024 * 1024
                used = 0
            return MockMemory()
        
        @staticmethod
        def disk_usage(path):
            class MockDisk:
                total = 100 * 1024 * 1024 * 1024  # 100GB
                used = 10 * 1024 * 1024 * 1024   # 10GB
                free = 90 * 1024 * 1024 * 1024   # 90GB
            return MockDisk()
        
        @staticmethod
        def Process():
            class MockProcess:
                def memory_info(self):
                    class MockMemInfo:
                        rss = 100 * 1024 * 1024  # 100MB
                        vms = 200 * 1024 * 1024  # 200MB
                    return MockMemInfo()
                
                def memory_percent(self):
                    return 5.0
                
                def cpu_percent(self):
                    return 10.0
            return MockProcess()
        
        @staticmethod
        def getloadavg():
            return (0.5, 0.6, 0.7)
        
        @staticmethod
        def cpu_count():
            return 4
        
        @staticmethod
        def net_io_counters():
            class MockNetwork:
                bytes_sent = 0
                bytes_recv = 0
            return MockNetwork()
        
        @staticmethod
        def net_connections():
            return []
        
        @staticmethod
        def boot_time():
            import time
            return time.time() - 3600  # 1 hour ago
        
        # Mock exception class
        AccessDenied = Exception
        NoSuchProcess = Exception
    
    psutil = MockPsutil()

# Export the psutil module (real or mock)
__all__ = ['psutil', 'PSUTIL_AVAILABLE']
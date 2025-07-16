"""
Automation package for the Oikotie Real Estate Analytics Platform.

This package provides automation capabilities including smart deduplication,
listing management, and intelligent scraping orchestration.
"""

from .deduplication import SmartDeduplicationManager
from .listing_manager import ListingManager
from .retry_manager import RetryManager

__all__ = [
    'SmartDeduplicationManager', 
    'ListingManager', 
    'RetryManager'
]
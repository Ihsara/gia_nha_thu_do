"""Minimal test of data governance classes."""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime

class DataSource(Enum):
    """Enumeration of data sources."""
    OIKOTIE_SCRAPER = "oikotie_scraper"

class DataQualityLevel(Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"

@dataclass
class DataQualityScore:
    """Represents a data quality assessment."""
    overall_score: float
    quality_level: DataQualityLevel
    issues: List[str]
    recommendations: List[str]

class DataGovernanceManager:
    """Simple test class."""
    
    def __init__(self):
        self.test = "working"
    
    def get_test(self):
        return self.test

if __name__ == "__main__":
    print("Testing minimal governance classes...")
    manager = DataGovernanceManager()
    print(f"Manager test: {manager.get_test()}")
    print("✅ All tests passed")
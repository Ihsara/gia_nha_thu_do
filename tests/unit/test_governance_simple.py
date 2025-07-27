#!/usr/bin/env python3
"""
Simple test for data governance functionality without database dependencies.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.automation.data_governance import (
    DataGovernanceManager, DataSource, DataQualityLevel, DataQualityScore
)
from oikotie.automation.governance_integration import (
    GovernanceIntegratedOrchestrator, GovernanceIntegrationConfig
)


def test_data_governance_manager_basic():
    """Test basic data governance manager functionality."""
    # Create manager without database
    manager = DataGovernanceManager(db_manager=None)
    
    assert manager is not None
    assert manager.governance_rules is not None
    assert len(manager.retention_policies) > 0
    print("✅ DataGovernanceManager basic initialization successful")


def test_data_quality_scoring():
    """Test data quality scoring functionality."""
    manager = DataGovernanceManager(db_manager=None)
    
    # Test high-quality listing data
    high_quality_data = {
        'url': 'https://oikotie.fi/listing/123',
        'title': 'Beautiful apartment in Helsinki',
        'city': 'Helsinki',
        'address': 'Mannerheimintie 123, 00100 Helsinki',
        'price_eur': 350000,
        'size_m2': 75.5,
        'rooms': 3,
        'year_built': 2010,
        'overview': 'Nice apartment with good location',
        'scraped_at': datetime.now()
    }
    
    quality_score = manager.calculate_data_quality_score(high_quality_data)
    
    assert quality_score.overall_score > 0.7
    assert quality_score.quality_level in [DataQualityLevel.EXCELLENT, DataQualityLevel.GOOD]
    assert len(quality_score.issues) == 0
    print(f"✅ High quality data scored: {quality_score.overall_score:.2f} ({quality_score.quality_level.value})")
    
    # Test low-quality listing data
    low_quality_data = {
        'url': 'https://oikotie.fi/listing/456',
        'title': '',  # Missing title
        'city': 'Helsinki',
        'price_eur': -1000,  # Invalid price
        'size_m2': 2000,  # Unrealistic size
        'rooms': 50,  # Unrealistic room count
    }
    
    quality_score = manager.calculate_data_quality_score(low_quality_data)
    
    assert quality_score.overall_score < 0.5
    assert quality_score.quality_level == DataQualityLevel.POOR
    assert len(quality_score.issues) > 0
    print(f"✅ Low quality data scored: {quality_score.overall_score:.2f} ({quality_score.quality_level.value})")
    print(f"   Issues found: {len(quality_score.issues)}")


def test_governance_integration():
    """Test governance integration functionality."""
    # Create a mock config
    class MockConfig:
        def __init__(self):
            self.city = "Helsinki"
            self.url = "https://oikotie.fi/test"
    
    config = MockConfig()
    governance_config = GovernanceIntegrationConfig(
        enable_lineage_tracking=True,
        enable_api_usage_tracking=True,
        enable_quality_scoring=True,
        enable_retention_enforcement=False,  # Disable for testing
        enable_compliance_reporting=True,
        quality_score_threshold=0.5
    )
    
    # Create governance-integrated orchestrator
    orchestrator = GovernanceIntegratedOrchestrator(
        config=config,
        db_manager=None,
        governance_config=governance_config
    )
    
    assert orchestrator is not None
    assert orchestrator.governance_manager is not None
    assert orchestrator.governance_config is not None
    print("✅ GovernanceIntegratedOrchestrator initialization successful")
    
    # Test listing processing with governance
    execution_id = "test_exec_123"
    
    listing_data = {
        'url': 'https://oikotie.fi/listing/test123',
        'title': 'Test Apartment',
        'city': 'Helsinki',
        'address': 'Test Street 123',
        'price_eur': 300000,
        'size_m2': 60,
        'rooms': 2
    }
    
    # Process listing with governance
    enhanced_data = orchestrator.process_listing_with_governance(
        listing_data, execution_id
    )
    
    # Verify governance metadata was added
    assert 'data_quality_score' in enhanced_data
    assert 'quality_level' in enhanced_data
    assert 'data_source' in enhanced_data
    assert 'fetch_timestamp' in enhanced_data
    assert 'execution_id' in enhanced_data
    
    assert enhanced_data['execution_id'] == execution_id
    assert enhanced_data['data_source'] == DataSource.OIKOTIE_SCRAPER.value
    print("✅ Listing processing with governance successful")
    print(f"   Quality score: {enhanced_data['data_quality_score']:.2f}")
    print(f"   Quality level: {enhanced_data['quality_level']}")


def test_compliance_report_generation():
    """Test compliance report generation."""
    manager = DataGovernanceManager(db_manager=None)
    
    # Generate report
    period_start = datetime.now() - timedelta(days=1)
    period_end = datetime.now()
    
    report = manager.generate_compliance_report(period_start, period_end)
    
    assert report is not None
    assert report.report_id is not None
    assert report.period_start == period_start
    assert report.period_end == period_end
    assert 'total_api_calls' in report.api_usage_summary
    assert isinstance(report.governance_violations, list)
    assert isinstance(report.recommendations, list)
    print("✅ Compliance report generation successful")
    print(f"   Report ID: {report.report_id}")


if __name__ == "__main__":
    print("🚀 Running simple data governance tests...")
    print()
    
    try:
        test_data_governance_manager_basic()
        print()
        
        test_data_quality_scoring()
        print()
        
        test_governance_integration()
        print()
        
        test_compliance_report_generation()
        print()
        
        print("🎉 All tests passed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
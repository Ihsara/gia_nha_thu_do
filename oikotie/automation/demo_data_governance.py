#!/usr/bin/env python3
"""
Data Governance Integration Demo

This script demonstrates the data governance and quality assurance integration
for the daily scraper automation system. It shows how to use the governance
features including lineage tracking, quality scoring, retention policies,
and compliance reporting.
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

from .data_governance import (
    DataGovernanceManager, DataSource, DataQualityLevel,
    create_data_governance_config
)
from .governance_integration import (
    GovernanceIntegratedOrchestrator, GovernanceIntegrationConfig
)
from .orchestrator import ScraperConfig
from ..database.manager import EnhancedDatabaseManager


def demo_data_governance_setup():
    """Demonstrate data governance setup and configuration."""
    logger.info("🔧 Setting up data governance system...")
    
    # Create data governance configuration
    config_path = create_data_governance_config()
    logger.info(f"✅ Created data governance configuration: {config_path}")
    
    # Initialize data governance manager
    governance_manager = DataGovernanceManager()
    logger.info("✅ Initialized data governance manager")
    
    # Display governance rules
    logger.info("📋 Data governance rules loaded:")
    logger.info(f"  • API rate limits: {len(governance_manager.governance_rules['api_rate_limits'])} domains")
    logger.info(f"  • Retention policies: {len(governance_manager.retention_policies)} tables")
    logger.info(f"  • Quality thresholds: {len(governance_manager.governance_rules['data_quality_thresholds'])} metrics")
    
    return governance_manager


def demo_data_lineage_tracking(governance_manager):
    """Demonstrate data lineage tracking."""
    logger.info("📊 Demonstrating data lineage tracking...")
    
    # Track various data sources
    test_cases = [
        {
            "table_name": "listings",
            "record_id": "oikotie_listing_12345",
            "data_source": DataSource.OIKOTIE_SCRAPER,
            "api_endpoint": "https://oikotie.fi/myytavat-asunnot/helsinki/12345",
            "request_parameters": {"city": "Helsinki", "listing_type": "apartment"},
            "response_metadata": {"scraped_at": datetime.now().isoformat(), "status": "success"}
        },
        {
            "table_name": "address_locations",
            "record_id": "helsinki_address_456",
            "data_source": DataSource.HELSINKI_OPEN_DATA,
            "api_endpoint": "https://hri.fi/api/address/456",
            "request_parameters": {"address": "Mannerheimintie 123"},
            "response_metadata": {"geocoded": True, "accuracy": "high"}
        },
        {
            "table_name": "osm_buildings",
            "record_id": "osm_building_789",
            "data_source": DataSource.OSM_OVERPASS,
            "api_endpoint": "https://overpass-api.de/api/interpreter",
            "request_parameters": {"bbox": "60.1,24.9,60.2,25.0"},
            "response_metadata": {"building_count": 150, "query_time": "2.3s"}
        }
    ]
    
    for case in test_cases:
        governance_manager.track_data_lineage(
            table_name=case["table_name"],
            record_id=case["record_id"],
            data_source=case["data_source"],
            execution_id="demo_exec_001",
            api_endpoint=case["api_endpoint"],
            request_parameters=case["request_parameters"],
            response_metadata=case["response_metadata"]
        )
        logger.info(f"  ✅ Tracked lineage: {case['table_name']}/{case['record_id']}")
    
    logger.info("📊 Data lineage tracking completed")


def demo_api_usage_tracking(governance_manager):
    """Demonstrate API usage tracking and rate limiting."""
    logger.info("🌐 Demonstrating API usage tracking...")
    
    # Simulate API calls
    api_calls = [
        {
            "endpoint": "https://oikotie.fi/api/listings",
            "status": 200,
            "response_time": 150,
            "records": 25
        },
        {
            "endpoint": "https://hri.fi/api/addresses",
            "status": 200,
            "response_time": 300,
            "records": 100
        },
        {
            "endpoint": "https://overpass-api.de/api/interpreter",
            "status": 200,
            "response_time": 2500,
            "records": 500
        },
        {
            "endpoint": "https://oikotie.fi/api/listings",
            "status": 429,  # Rate limited
            "response_time": 50,
            "records": 0
        }
    ]
    
    for call in api_calls:
        # Check rate limits before making call
        allowed = governance_manager.enforce_rate_limits(call["endpoint"])
        if allowed:
            logger.info(f"  ✅ API call allowed: {call['endpoint']}")
        else:
            logger.warning(f"  ⚠️ API call rate limited: {call['endpoint']}")
        
        # Track the API usage
        governance_manager.track_api_usage(
            api_endpoint=call["endpoint"],
            response_status=call["status"],
            response_time_ms=call["response_time"],
            records_fetched=call["records"],
            execution_id="demo_exec_001"
        )
        logger.info(f"  📝 Tracked API usage: {call['endpoint']} ({call['status']})")
    
    logger.info("🌐 API usage tracking completed")


def demo_data_quality_scoring(governance_manager):
    """Demonstrate data quality scoring."""
    logger.info("⭐ Demonstrating data quality scoring...")
    
    # Test different quality levels
    test_listings = [
        {
            "name": "High Quality Listing",
            "data": {
                'url': 'https://oikotie.fi/listing/excellent',
                'title': 'Beautiful 3-room apartment in Kamppi, Helsinki',
                'city': 'Helsinki',
                'address': 'Kampinkatu 15, 00100 Helsinki',
                'price_eur': 450000,
                'size_m2': 85.5,
                'rooms': 3,
                'year_built': 2015,
                'overview': 'Renovated apartment with modern amenities and excellent location',
                'full_description': 'This beautiful apartment offers...',
                'scraped_at': datetime.now()
            }
        },
        {
            "name": "Medium Quality Listing",
            "data": {
                'url': 'https://oikotie.fi/listing/medium',
                'title': 'Apartment for sale',
                'city': 'Helsinki',
                'address': 'Some street',
                'price_eur': 300000,
                'size_m2': 60,
                'rooms': 2,
                'scraped_at': datetime.now() - timedelta(days=7)  # Older data
            }
        },
        {
            "name": "Poor Quality Listing",
            "data": {
                'url': 'https://oikotie.fi/listing/poor',
                'title': '',  # Missing title
                'city': 'Helsinki',
                'price_eur': -50000,  # Invalid price
                'size_m2': 2000,  # Unrealistic size
                'rooms': 50,  # Unrealistic room count
                'year_built': 1500,  # Invalid year
            }
        }
    ]
    
    for listing in test_listings:
        quality_score = governance_manager.calculate_data_quality_score(listing["data"])
        
        logger.info(f"  📊 {listing['name']}:")
        logger.info(f"    • Overall Score: {quality_score.overall_score:.2f}")
        logger.info(f"    • Quality Level: {quality_score.quality_level.value}")
        logger.info(f"    • Completeness: {quality_score.completeness_score:.2f}")
        logger.info(f"    • Accuracy: {quality_score.accuracy_score:.2f}")
        logger.info(f"    • Consistency: {quality_score.consistency_score:.2f}")
        logger.info(f"    • Timeliness: {quality_score.timeliness_score:.2f}")
        
        if quality_score.issues:
            logger.info(f"    • Issues: {len(quality_score.issues)}")
            for issue in quality_score.issues[:2]:  # Show first 2 issues
                logger.info(f"      - {issue}")
        
        if quality_score.recommendations:
            logger.info(f"    • Recommendations: {len(quality_score.recommendations)}")
            for rec in quality_score.recommendations[:1]:  # Show first recommendation
                logger.info(f"      - {rec}")
        
        logger.info("")
    
    logger.info("⭐ Data quality scoring completed")


def demo_compliance_reporting(governance_manager):
    """Demonstrate compliance reporting."""
    logger.info("📋 Demonstrating compliance reporting...")
    
    # Generate compliance report for the last day
    period_start = datetime.now() - timedelta(days=1)
    period_end = datetime.now()
    
    try:
        report = governance_manager.generate_compliance_report(period_start, period_end)
        
        logger.info(f"  📊 Compliance Report Generated:")
        logger.info(f"    • Report ID: {report.report_id}")
        logger.info(f"    • Period: {report.period_start.date()} to {report.period_end.date()}")
        
        # API Usage Summary
        api_summary = report.api_usage_summary
        if 'total_api_calls' in api_summary:
            logger.info(f"    • Total API Calls: {api_summary['total_api_calls']}")
        
        if 'endpoint_statistics' in api_summary:
            logger.info(f"    • Endpoints Used: {len(api_summary['endpoint_statistics'])}")
        
        # Data Quality Summary
        quality_summary = report.data_quality_summary
        if 'average_quality_score' in quality_summary:
            logger.info(f"    • Average Quality Score: {quality_summary['average_quality_score']:.2f}")
        
        # Violations
        if report.governance_violations:
            logger.info(f"    • Governance Violations: {len(report.governance_violations)}")
            for violation in report.governance_violations[:2]:  # Show first 2
                logger.warning(f"      - {violation['severity'].upper()}: {violation['description']}")
        else:
            logger.info(f"    • Governance Violations: None ✅")
        
        # Recommendations
        if report.recommendations:
            logger.info(f"    • Recommendations: {len(report.recommendations)}")
            for rec in report.recommendations[:2]:  # Show first 2
                logger.info(f"      - {rec}")
        
        # Save report
        report_path = f"output/compliance/demo_compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report.__dict__, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"  💾 Report saved to: {report_path}")
        
    except Exception as e:
        logger.error(f"  ❌ Failed to generate compliance report: {e}")
    
    logger.info("📋 Compliance reporting completed")


def demo_retention_policies(governance_manager):
    """Demonstrate retention policy enforcement."""
    logger.info("🗂️ Demonstrating retention policy enforcement...")
    
    # Display configured retention policies
    logger.info("  📋 Configured Retention Policies:")
    for policy in governance_manager.retention_policies:
        logger.info(f"    • {policy.table_name}: {policy.retention_days} days")
        logger.info(f"      - Archive before delete: {policy.archive_before_delete}")
        if policy.conditions:
            logger.info(f"      - Conditions: {policy.conditions}")
    
    # Note: We won't actually run retention enforcement in the demo
    # as it could delete real data
    logger.info("  ⚠️ Retention enforcement skipped in demo mode")
    logger.info("  💡 Use 'uv run python -m oikotie.automation.governance_cli cleanup' to run retention")
    
    logger.info("🗂️ Retention policy demonstration completed")


def demo_governance_integration():
    """Demonstrate governance integration with orchestrator."""
    logger.info("🔗 Demonstrating governance integration with orchestrator...")
    
    # Create scraper configuration
    scraper_config = ScraperConfig(
        city="Helsinki",
        url="https://oikotie.fi/myytavat-asunnot/helsinki",
        listing_limit=5,  # Small limit for demo
        enable_smart_deduplication=True,
        enable_performance_monitoring=True
    )
    
    # Create governance configuration
    governance_config = GovernanceIntegrationConfig(
        enable_lineage_tracking=True,
        enable_api_usage_tracking=True,
        enable_quality_scoring=True,
        enable_retention_enforcement=False,  # Disabled for demo
        enable_compliance_reporting=True,
        quality_score_threshold=0.5
    )
    
    # Create governance-integrated orchestrator
    try:
        orchestrator = GovernanceIntegratedOrchestrator(
            config=scraper_config,
            governance_config=governance_config
        )
        
        logger.info("  ✅ Created governance-integrated orchestrator")
        logger.info(f"    • City: {orchestrator.config.city}")
        logger.info(f"    • Governance features enabled:")
        logger.info(f"      - Lineage tracking: {governance_config.enable_lineage_tracking}")
        logger.info(f"      - API usage tracking: {governance_config.enable_api_usage_tracking}")
        logger.info(f"      - Quality scoring: {governance_config.enable_quality_scoring}")
        logger.info(f"      - Compliance reporting: {governance_config.enable_compliance_reporting}")
        
        # Demonstrate listing processing with governance
        sample_listing = {
            'url': 'https://oikotie.fi/listing/demo123',
            'title': 'Demo Apartment',
            'city': 'Helsinki',
            'address': 'Demo Street 123',
            'price_eur': 350000,
            'size_m2': 70,
            'rooms': 3
        }
        
        enhanced_listing = orchestrator.process_listing_with_governance(
            sample_listing, "demo_exec_002"
        )
        
        logger.info("  📊 Sample listing processed with governance:")
        logger.info(f"    • Data quality score: {enhanced_listing.get('data_quality_score', 'N/A')}")
        logger.info(f"    • Quality level: {enhanced_listing.get('quality_level', 'N/A')}")
        logger.info(f"    • Data source: {enhanced_listing.get('data_source', 'N/A')}")
        logger.info(f"    • Execution ID: {enhanced_listing.get('execution_id', 'N/A')}")
        
    except Exception as e:
        logger.error(f"  ❌ Failed to create governance-integrated orchestrator: {e}")
    
    logger.info("🔗 Governance integration demonstration completed")


def main():
    """Run the complete data governance integration demo."""
    logger.info("🚀 Starting Data Governance Integration Demo")
    logger.info("=" * 60)
    
    try:
        # Setup
        governance_manager = demo_data_governance_setup()
        logger.info("")
        
        # Data lineage tracking
        demo_data_lineage_tracking(governance_manager)
        logger.info("")
        
        # API usage tracking
        demo_api_usage_tracking(governance_manager)
        logger.info("")
        
        # Data quality scoring
        demo_data_quality_scoring(governance_manager)
        logger.info("")
        
        # Compliance reporting
        demo_compliance_reporting(governance_manager)
        logger.info("")
        
        # Retention policies
        demo_retention_policies(governance_manager)
        logger.info("")
        
        # Governance integration
        demo_governance_integration()
        logger.info("")
        
        logger.success("🎉 Data Governance Integration Demo Completed Successfully!")
        logger.info("=" * 60)
        logger.info("📚 Next Steps:")
        logger.info("  • Review generated compliance report in output/compliance/")
        logger.info("  • Check data governance configuration in config/data_governance.json")
        logger.info("  • Use CLI commands: uv run python -m oikotie.automation.governance_cli --help")
        logger.info("  • Integrate with existing automation workflows")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    main()
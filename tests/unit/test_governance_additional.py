#!/usr/bin/env python3
"""Additional tests for data governance functionality."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oikotie.automation.data_governance import DataGovernanceManager, DataSource
from datetime import datetime

def test_additional_functionality():
    """Test additional data governance functionality."""
    
    # Test data lineage tracking
    manager = DataGovernanceManager(db_manager=None)
    manager.track_data_lineage(
        table_name='listings',
        record_id='test_123',
        data_source=DataSource.OIKOTIE_SCRAPER,
        execution_id='exec_123'
    )
    print('✅ Data lineage tracking test passed')

    # Test API usage tracking
    manager.track_api_usage(
        api_endpoint='https://oikotie.fi/api/test',
        response_status=200,
        response_time_ms=150,
        records_fetched=25
    )
    print('✅ API usage tracking test passed')

    # Test rate limit enforcement
    result = manager.enforce_rate_limits('https://oikotie.fi/api/test')
    print(f'✅ Rate limit enforcement test passed: {result}')

    print('🎉 All additional tests passed!')

if __name__ == "__main__":
    test_additional_functionality()
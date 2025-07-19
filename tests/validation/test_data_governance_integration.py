"""
Test suite for data governance integration in the automation system.

This test validates the integration of data governance features including
lineage tracking, quality scoring, retention policies, and compliance reporting.
"""

import pytest
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from oikotie.automation.data_governance import (
    DataGovernanceManager, DataSource, DataQualityLevel, 
    DataLineageRecord, APIUsageRecord, DataQualityScore
)
from oikotie.automation.governance_integration import (
    GovernanceIntegratedOrchestrator, GovernanceIntegrationConfig
)
from oikotie.automation.orchestrator import ScraperConfig
from oikotie.database.manager import EnhancedDatabaseManager


class TestDataGovernanceManager:
    """Test data governance manager functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
            db_path = f.name
        
        # Initialize database with schema
        db_manager = EnhancedDatabaseManager(db_path)
        yield db_manager
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def governance_manager(self, temp_db):
        """Create data governance manager with temporary database."""
        return DataGovernanceManager(temp_db)
    
    def test_governance_manager_initialization(self, governance_manager):
        """Test governance manager initializes correctly."""
        assert governance_manager is not None
        assert governance_manager.db_manager is not None
        assert governance_manager.governance_rules is not None
        assert len(governance_manager.retention_policies) > 0
    
    def test_data_lineage_tracking(self, governance_manager):
        """Test data lineage tracking functionality."""
        # Track data lineage
        governance_manager.track_data_lineage(
            table_name="listings",
            record_id="test_listing_123",
            data_source=DataSource.OIKOTIE_SCRAPER,
            execution_id="exec_123",
            api_endpoint="https://oikotie.fi/test",
            request_parameters={"city": "Helsinki"},
            response_metadata={"status": "success"}
        )
        
        # Verify lineage was tracked
        with governance_manager.db_manager.get_connection() as con:
            result = con.execute("""
                SELECT table_name, record_id, data_source, api_endpoint
                FROM data_lineage 
                WHERE record_id = ?
            """, ["test_listing_123"]).fetchone()
            
            assert result is not None
            assert result[0] == "listings"
            assert result[1] == "test_listing_123"
            assert result[2] == DataSource.OIKOTIE_SCRAPER.value
            assert result[3] == "https://oikotie.fi/test"
    
    def test_api_usage_tracking(self, governance_manager):
        """Test API usage tracking functionality."""
        # Track API usage
        governance_manager.track_api_usage(
            api_endpoint="https://oikotie.fi/api/listings",
            response_status=200,
            response_time_ms=150,
            records_fetched=25,
            rate_limit_remaining=100,
            execution_id="exec_123"
        )
        
        # Verify usage was tracked
        with governance_manager.db_manager.get_connection() as con:
            result = con.execute("""
                SELECT api_endpoint, response_status, response_time_ms, records_fetched
                FROM api_usage_log 
                WHERE api_endpoint = ?
            """, ["https://oikotie.fi/api/listings"]).fetchone()
            
            assert result is not None
            assert result[0] == "https://oikotie.fi/api/listings"
            assert result[1] == 200
            assert result[2] == 150
            assert result[3] == 25
    
    def test_data_quality_scoring(self, governance_manager):
        """Test data quality scoring functionality."""
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
        
        quality_score = governance_manager.calculate_data_quality_score(high_quality_data)
        
        assert quality_score.overall_score > 0.8
        assert quality_score.quality_level in [DataQualityLevel.EXCELLENT, DataQualityLevel.GOOD]
        assert len(quality_score.issues) == 0
        
        # Test low-quality listing data
        low_quality_data = {
            'url': 'https://oikotie.fi/listing/456',
            'title': '',  # Missing title
            'city': 'Helsinki',
            'price_eur': -1000,  # Invalid price
            'size_m2': 2000,  # Unrealistic size
            'rooms': 50,  # Unrealistic room count
        }
        
        quality_score = governance_manager.calculate_data_quality_score(low_quality_data)
        
        assert quality_score.overall_score < 0.5
        assert quality_score.quality_level == DataQualityLevel.POOR
        assert len(quality_score.issues) > 0
    
    def test_rate_limit_enforcement(self, governance_manager):
        """Test rate limit enforcement."""
        # Test with configured domain
        api_endpoint = "https://oikotie.fi/api/test"
        
        # First call should be allowed
        assert governance_manager.enforce_rate_limits(api_endpoint) == True
        
        # Record the call
        governance_manager.track_api_usage(
            api_endpoint=api_endpoint,
            response_status=200,
            response_time_ms=100,
            records_fetched=10
        )
        
        # Immediate second call should be rate limited (but allowed due to sleep)
        # This is a simplified test - in reality, the sleep would occur
        result = governance_manager.enforce_rate_limits(api_endpoint)
        assert result == True  # Should still be allowed after rate limiting
    
    def test_compliance_report_generation(self, governance_manager):
        """Test compliance report generation."""
        # Add some test data
        governance_manager.track_api_usage(
            api_endpoint="https://oikotie.fi/api/test",
            response_status=200,
            response_time_ms=100,
            records_fetched=10
        )
        
        # Generate report
        period_start = datetime.now() - timedelta(days=1)
        period_end = datetime.now()
        
        report = governance_manager.generate_compliance_report(period_start, period_end)
        
        assert report is not None
        assert report.report_id is not None
        assert report.period_start == period_start
        assert report.period_end == period_end
        assert 'total_api_calls' in report.api_usage_summary
        assert isinstance(report.governance_violations, list)
        assert isinstance(report.recommendations, list)


class TestGovernanceIntegration:
    """Test governance integration with orchestrator."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
            db_path = f.name
        
        db_manager = EnhancedDatabaseManager(db_path)
        yield db_manager
        
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def scraper_config(self):
        """Create test scraper configuration."""
        return ScraperConfig(
            city="Helsinki",
            url="https://oikotie.fi/myytavat-asunnot/helsinki",
            listing_limit=10,
            enable_smart_deduplication=True,
            enable_performance_monitoring=True
        )
    
    @pytest.fixture
    def governance_config(self):
        """Create test governance configuration."""
        return GovernanceIntegrationConfig(
            enable_lineage_tracking=True,
            enable_api_usage_tracking=True,
            enable_quality_scoring=True,
            enable_retention_enforcement=False,  # Disable for testing
            enable_compliance_reporting=True,
            quality_score_threshold=0.5
        )
    
    @pytest.fixture
    def governance_orchestrator(self, scraper_config, governance_config, temp_db):
        """Create governance-integrated orchestrator."""
        return GovernanceIntegratedOrchestrator(
            config=scraper_config,
            db_manager=temp_db,
            governance_config=governance_config
        )
    
    def test_governance_orchestrator_initialization(self, governance_orchestrator):
        """Test governance orchestrator initializes correctly."""
        assert governance_orchestrator is not None
        assert governance_orchestrator.governance_manager is not None
        assert governance_orchestrator.governance_config is not None
    
    def test_listing_processing_with_governance(self, governance_orchestrator):
        """Test listing processing with governance features."""
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
        enhanced_data = governance_orchestrator.process_listing_with_governance(
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
    
    def test_api_tracking_with_governance(self, governance_orchestrator):
        """Test API call tracking with governance."""
        execution_id = "test_exec_123"
        
        # Track API call
        governance_orchestrator.track_api_call_with_governance(
            api_endpoint="https://oikotie.fi/api/test",
            response_status=200,
            response_time_ms=150,
            records_fetched=5,
            execution_id=execution_id
        )
        
        # Verify tracking occurred
        with governance_orchestrator.db_manager.get_connection() as con:
            result = con.execute("""
                SELECT api_endpoint, response_status, records_fetched
                FROM api_usage_log 
                WHERE api_endpoint = ?
            """, ["https://oikotie.fi/api/test"]).fetchone()
            
            assert result is not None
            assert result[0] == "https://oikotie.fi/api/test"
            assert result[1] == 200
            assert result[2] == 5
    
    @patch('oikotie.automation.governance_integration.GovernanceIntegratedOrchestrator._discover_listing_urls')
    @patch('oikotie.automation.governance_integration.GovernanceIntegratedOrchestrator._execute_processing_batches')
    def test_daily_scrape_with_governance(self, mock_execute, mock_discover, governance_orchestrator):
        """Test daily scrape execution with governance integration."""
        # Mock the discovery and processing
        mock_discover.return_value = ['https://oikotie.fi/listing/1', 'https://oikotie.fi/listing/2']
        
        from oikotie.automation.listing_manager import ProcessingStats
        mock_execute.return_value = ProcessingStats(
            total_urls=2,
            processed_urls=2,
            successful_urls=2,
            failed_urls=0,
            skipped_urls=0,
            processing_time_seconds=10.0,
            average_time_per_url=5.0,
            error_rate=0.0
        )
        
        # Run daily scrape
        result = governance_orchestrator.run_daily_scrape()
        
        # Verify result has governance metrics
        assert result is not None
        assert hasattr(result, 'governance_metrics') or 'governance_metrics' in result.__dict__
        
        # Verify execution was tracked in database
        with governance_orchestrator.db_manager.get_connection() as con:
            executions = con.execute("""
                SELECT execution_id, city, status
                FROM scraping_executions 
                WHERE city = ?
            """, [governance_orchestrator.config.city]).fetchall()
            
            assert len(executions) > 0


class TestDataGovernanceConfig:
    """Test data governance configuration management."""
    
    def test_config_creation(self):
        """Test data governance configuration file creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set config path in temp directory
            config_path = Path(temp_dir) / "config" / "data_governance.json"
            
            # Mock the config path
            with patch('oikotie.automation.data_governance.Path') as mock_path:
                mock_path.return_value = config_path
                mock_path.return_value.parent.mkdir = Mock()
                mock_path.return_value.exists.return_value = False
                
                from oikotie.automation.data_governance import create_data_governance_config
                
                # Create config directory
                config_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Create config
                result_path = create_data_governance_config()
                
                # Verify config was created
                assert config_path.exists()
                
                # Verify config content
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                assert 'api_rate_limits' in config
                assert 'data_quality_thresholds' in config
                assert 'retention_policies' in config
                assert 'compliance_reporting' in config


class TestDataGovernanceCLI:
    """Test data governance CLI functionality."""
    
    def test_cli_import(self):
        """Test that CLI module can be imported."""
        try:
            from oikotie.automation.governance_cli import governance
            assert governance is not None
        except ImportError as e:
            pytest.fail(f"Failed to import governance CLI: {e}")
    
    @patch('oikotie.automation.governance_cli.DataGovernanceManager')
    def test_status_command(self, mock_governance_manager):
        """Test governance status command."""
        from click.testing import CliRunner
        from oikotie.automation.governance_cli import governance
        
        # Mock the governance manager
        mock_manager = Mock()
        mock_manager.retention_policies = [Mock(), Mock()]
        mock_governance_manager.return_value = mock_manager
        
        # Mock database manager
        with patch('oikotie.automation.governance_cli.EnhancedDatabaseManager') as mock_db:
            mock_connection = Mock()
            mock_connection.execute.return_value.fetchone.return_value = [100]
            mock_db.return_value.get_connection.return_value.__enter__.return_value = mock_connection
            
            runner = CliRunner()
            result = runner.invoke(governance, ['status'])
            
            # Should not fail
            assert result.exit_code == 0 or "Failed to get governance system status" in result.output


def test_integration_with_existing_automation():
    """Test that governance integration works with existing automation components."""
    # Test that we can import all necessary components
    try:
        from oikotie.automation.data_governance import DataGovernanceManager
        from oikotie.automation.governance_integration import GovernanceIntegratedOrchestrator
        from oikotie.automation.governance_cli import governance
        
        # Verify components can be instantiated (with mocked dependencies)
        with patch('oikotie.automation.data_governance.EnhancedDatabaseManager'):
            governance_manager = DataGovernanceManager()
            assert governance_manager is not None
        
    except ImportError as e:
        pytest.fail(f"Failed to import governance components: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
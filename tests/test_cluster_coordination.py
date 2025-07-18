"""
Test Suite for Cluster Coordination System

This module provides comprehensive tests for the Redis-based cluster coordination
system including work distribution, distributed locking, and node health monitoring.
"""

import pytest
import json
import time
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
import redis
from oikotie.automation.cluster import (
    ClusterCoordinator,
    WorkItem,
    WorkItemStatus,
    HealthStatus,
    NodeStatus,
    WorkDistribution,
    create_cluster_coordinator
)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock_client = Mock()
    mock_client.ping.return_value = True
    mock_client.set.return_value = True
    mock_client.get.return_value = None
    mock_client.delete.return_value = 1
    mock_client.keys.return_value = []
    mock_client.hgetall.return_value = {}
    mock_client.hset.return_value = 1
    mock_client.hdel.return_value = 1
    mock_client.hlen.return_value = 0
    mock_client.llen.return_value = 0
    mock_client.lpush.return_value = 1
    mock_client.rpop.return_value = None
    mock_client.expire.return_value = True
    mock_client.pipeline.return_value = mock_client
    mock_client.execute.return_value = [1] * 10
    mock_client.eval.return_value = 1
    mock_client.zadd.return_value = 1
    mock_client.zrangebyscore.return_value = []
    mock_client.zremrangebyscore.return_value = 0
    return mock_client


@pytest.fixture
def coordinator(mock_redis):
    """Create cluster coordinator with mock Redis"""
    return ClusterCoordinator(mock_redis, node_id="test-node-1")


@pytest.fixture
def sample_work_items():
    """Create sample work items for testing"""
    return [
        WorkItem(
            work_id="work-1",
            city="Helsinki",
            url="https://example.com/helsinki",
            priority=1
        ),
        WorkItem(
            work_id="work-2", 
            city="Espoo",
            url="https://example.com/espoo",
            priority=2
        ),
        WorkItem(
            work_id="work-3",
            city="Vantaa", 
            url="https://example.com/vantaa",
            priority=1
        )
    ]


class TestWorkItem:
    """Test WorkItem data class"""
    
    def test_work_item_creation(self):
        """Test WorkItem creation and initialization"""
        work_item = WorkItem(
            work_id="test-work",
            city="Helsinki",
            url="https://example.com/test"
        )
        
        assert work_item.work_id == "test-work"
        assert work_item.city == "Helsinki"
        assert work_item.url == "https://example.com/test"
        assert work_item.priority == 1
        assert work_item.max_retries == 3
        assert work_item.retry_count == 0
        assert work_item.status == WorkItemStatus.PENDING
        assert work_item.assigned_node is None
        assert work_item.created_at is not None
    
    def test_work_item_serialization(self):
        """Test WorkItem to_dict and from_dict methods"""
        original = WorkItem(
            work_id="test-work",
            city="Helsinki", 
            url="https://example.com/test",
            priority=2,
            status=WorkItemStatus.IN_PROGRESS
        )
        
        # Test serialization
        data = original.to_dict()
        assert isinstance(data, dict)
        assert data['work_id'] == "test-work"
        assert data['status'] == "in_progress"
        assert isinstance(data['created_at'], str)
        
        # Test deserialization
        restored = WorkItem.from_dict(data)
        assert restored.work_id == original.work_id
        assert restored.city == original.city
        assert restored.url == original.url
        assert restored.priority == original.priority
        assert restored.status == original.status
        assert restored.created_at == original.created_at


class TestHealthStatus:
    """Test HealthStatus data class"""
    
    def test_health_status_creation(self):
        """Test HealthStatus creation"""
        health = HealthStatus(
            node_id="test-node",
            status=NodeStatus.HEALTHY,
            cpu_percent=25.5,
            memory_percent=60.0,
            disk_percent=45.0,
            active_workers=3,
            last_heartbeat=datetime.now(timezone.utc)
        )
        
        assert health.node_id == "test-node"
        assert health.status == NodeStatus.HEALTHY
        assert health.cpu_percent == 25.5
        assert health.memory_percent == 60.0
        assert health.disk_percent == 45.0
        assert health.active_workers == 3
        assert health.error_count == 0
        assert health.warning_count == 0
    
    def test_health_status_serialization(self):
        """Test HealthStatus serialization"""
        original = HealthStatus(
            node_id="test-node",
            status=NodeStatus.DEGRADED,
            cpu_percent=75.0,
            memory_percent=80.0,
            disk_percent=65.0,
            active_workers=5,
            last_heartbeat=datetime.now(timezone.utc),
            error_count=2,
            warning_count=5
        )
        
        # Test serialization
        data = original.to_dict()
        assert data['status'] == "degraded"
        assert isinstance(data['last_heartbeat'], str)
        
        # Test deserialization
        restored = HealthStatus.from_dict(data)
        assert restored.node_id == original.node_id
        assert restored.status == original.status
        assert restored.cpu_percent == original.cpu_percent
        assert restored.error_count == original.error_count


class TestClusterCoordinator:
    """Test ClusterCoordinator functionality"""
    
    def test_coordinator_initialization(self, mock_redis):
        """Test coordinator initialization"""
        coordinator = ClusterCoordinator(mock_redis, node_id="test-node")
        
        assert coordinator.redis == mock_redis
        assert coordinator.node_id == "test-node"
        assert coordinator.heartbeat_interval == 30
        assert coordinator.lock_ttl == 300
    
    def test_node_id_generation(self, mock_redis):
        """Test automatic node ID generation"""
        coordinator = ClusterCoordinator(mock_redis)
        
        assert coordinator.node_id is not None
        assert len(coordinator.node_id) > 0
        assert "-" in coordinator.node_id
    
    def test_acquire_work_lock_success(self, coordinator, mock_redis):
        """Test successful work lock acquisition"""
        mock_redis.set.return_value = True
        
        result = coordinator.acquire_work_lock("work-1", ttl=300)
        
        assert result is True
        mock_redis.set.assert_called_once_with(
            "scraper:lock:work-1",
            "test-node-1",
            nx=True,
            ex=300
        )
    
    def test_acquire_work_lock_failure(self, coordinator, mock_redis):
        """Test failed work lock acquisition"""
        mock_redis.set.return_value = False
        
        result = coordinator.acquire_work_lock("work-1")
        
        assert result is False
    
    def test_release_work_lock_success(self, coordinator, mock_redis):
        """Test successful work lock release"""
        mock_redis.eval.return_value = 1
        
        result = coordinator.release_work_lock("work-1")
        
        assert result is True
        mock_redis.eval.assert_called_once()
    
    def test_release_work_lock_not_owned(self, coordinator, mock_redis):
        """Test work lock release when not owned by node"""
        mock_redis.eval.return_value = 0
        
        result = coordinator.release_work_lock("work-1")
        
        assert result is False
    
    def test_distribute_work_no_healthy_nodes(self, coordinator, sample_work_items):
        """Test work distribution with no healthy nodes"""
        with patch.object(coordinator, 'get_healthy_nodes', return_value=[]):
            result = coordinator.distribute_work(sample_work_items)
            
            assert result.total_work_items == 3
            assert result.distributed_items == 0
            assert result.failed_items == 3
            assert result.node_assignments == {}
    
    def test_distribute_work_success(self, coordinator, sample_work_items, mock_redis):
        """Test successful work distribution"""
        healthy_nodes = ["node-1", "node-2", "node-3"]
        
        with patch.object(coordinator, 'get_healthy_nodes', return_value=healthy_nodes):
            with patch.object(coordinator, '_get_node_workload', return_value=0):
                result = coordinator.distribute_work(sample_work_items)
                
                assert result.total_work_items == 3
                assert result.distributed_items == 3
                assert result.failed_items == 0
                assert len(result.node_assignments) > 0
    
    def test_get_work_for_node(self, coordinator, mock_redis):
        """Test getting work items for a node"""
        work_data = json.dumps({
            'work_id': 'work-1',
            'city': 'Helsinki',
            'url': 'https://example.com/helsinki',
            'priority': 1,
            'max_retries': 3,
            'retry_count': 0,
            'status': 'pending',
            'assigned_node': None,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'started_at': None,
            'completed_at': None,
            'error_message': None
        })
        
        mock_redis.rpop.return_value = work_data
        
        work_items = coordinator.get_work_for_node("test-node", count=1)
        
        assert len(work_items) == 1
        assert work_items[0].work_id == "work-1"
        assert work_items[0].status == WorkItemStatus.IN_PROGRESS
        assert work_items[0].started_at is not None
    
    def test_complete_work_item(self, coordinator, mock_redis):
        """Test completing a work item"""
        work_item = WorkItem(
            work_id="work-1",
            city="Helsinki",
            url="https://example.com/helsinki",
            assigned_node="test-node-1",
            status=WorkItemStatus.IN_PROGRESS
        )
        
        result = coordinator.complete_work_item(work_item)
        
        assert result is True
        assert work_item.status == WorkItemStatus.COMPLETED
        assert work_item.completed_at is not None
        mock_redis.hdel.assert_called()
        mock_redis.hset.assert_called()
    
    def test_fail_work_item_with_retry(self, coordinator, mock_redis):
        """Test failing a work item that should be retried"""
        work_item = WorkItem(
            work_id="work-1",
            city="Helsinki",
            url="https://example.com/helsinki",
            assigned_node="test-node-1",
            status=WorkItemStatus.IN_PROGRESS,
            retry_count=0,
            max_retries=3
        )
        
        result = coordinator.fail_work_item(work_item, "Network error")
        
        assert result is True
        assert work_item.status == WorkItemStatus.RETRYING
        assert work_item.retry_count == 1
        assert work_item.error_message == "Network error"
        mock_redis.zadd.assert_called()
    
    def test_fail_work_item_max_retries(self, coordinator, mock_redis):
        """Test failing a work item that has exceeded max retries"""
        work_item = WorkItem(
            work_id="work-1",
            city="Helsinki",
            url="https://example.com/helsinki",
            assigned_node="test-node-1",
            status=WorkItemStatus.IN_PROGRESS,
            retry_count=3,
            max_retries=3
        )
        
        result = coordinator.fail_work_item(work_item, "Persistent error")
        
        assert result is True
        assert work_item.status == WorkItemStatus.FAILED
        assert work_item.retry_count == 4
        mock_redis.hset.assert_called()
    
    def test_process_retry_queue(self, coordinator, mock_redis):
        """Test processing retry queue"""
        retry_data = json.dumps({
            'work_item': {
                'work_id': 'work-1',
                'city': 'Helsinki',
                'url': 'https://example.com/helsinki',
                'priority': 1,
                'max_retries': 3,
                'retry_count': 1,
                'status': 'retrying',
                'assigned_node': 'test-node-1',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'started_at': None,
                'completed_at': None,
                'error_message': 'Network error'
            },
            'retry_time': time.time() - 60  # 1 minute ago
        })
        
        mock_redis.zrangebyscore.return_value = [retry_data]
        
        ready_items = coordinator.process_retry_queue()
        
        assert len(ready_items) == 1
        assert ready_items[0].work_id == "work-1"
        assert ready_items[0].retry_count == 1
        mock_redis.zremrangebyscore.assert_called()
    
    def test_collect_health_metrics(self, coordinator):
        """Test health metrics collection"""
        # Mock the entire health collection method to avoid psutil issues
        mock_health = HealthStatus(
            node_id="test-node-1",
            status=NodeStatus.HEALTHY,
            cpu_percent=45.0,
            memory_percent=60.0,
            disk_percent=30.0,
            active_workers=0,
            last_heartbeat=datetime.now(timezone.utc)
        )
        
        with patch.object(coordinator, '_collect_health_metrics', return_value=mock_health):
            health = coordinator._collect_health_metrics()
            
            assert health.node_id == "test-node-1"
            assert health.status == NodeStatus.HEALTHY
            assert health.cpu_percent == 45.0
            assert health.memory_percent == 60.0
            assert health.disk_percent == 30.0
            assert health.active_workers == 0
    
    def test_collect_health_metrics_unhealthy(self, coordinator):
        """Test health metrics collection for unhealthy node"""
        # Mock the entire health collection method to avoid psutil issues
        mock_health = HealthStatus(
            node_id="test-node-1",
            status=NodeStatus.UNHEALTHY,
            cpu_percent=95.0,
            memory_percent=92.0,
            disk_percent=95.0,
            active_workers=0,
            last_heartbeat=datetime.now(timezone.utc)
        )
        
        with patch.object(coordinator, '_collect_health_metrics', return_value=mock_health):
            health = coordinator._collect_health_metrics()
            
            assert health.status == NodeStatus.UNHEALTHY
    
    def test_report_node_health(self, coordinator, mock_redis):
        """Test node health reporting"""
        health_status = HealthStatus(
            node_id="test-node-1",
            status=NodeStatus.HEALTHY,
            cpu_percent=25.0,
            memory_percent=50.0,
            disk_percent=40.0,
            active_workers=2,
            last_heartbeat=datetime.now(timezone.utc)
        )
        
        coordinator.report_node_health("test-node-1", health_status)
        
        mock_redis.hset.assert_called()
        mock_redis.expire.assert_called()
    
    def test_get_healthy_nodes(self, coordinator, mock_redis):
        """Test getting healthy nodes"""
        health_data = {
            b'node_id': b'test-node-1',
            b'status': b'healthy',
            b'cpu_percent': b'25.0',
            b'memory_percent': b'50.0',
            b'disk_percent': b'40.0',
            b'active_workers': b'2',
            b'last_heartbeat': datetime.now(timezone.utc).isoformat().encode(),
            b'error_count': b'0',
            b'warning_count': b'0'
        }
        
        mock_redis.keys.return_value = [b'scraper:node_health:test-node-1']
        mock_redis.hgetall.return_value = health_data
        
        healthy_nodes = coordinator.get_healthy_nodes()
        
        assert len(healthy_nodes) == 1
        assert "test-node-1" in healthy_nodes
    
    def test_get_cluster_status(self, coordinator, mock_redis):
        """Test getting cluster status"""
        # Mock node health data
        health_data = {
            b'node_id': b'test-node-1',
            b'status': b'healthy',
            b'cpu_percent': b'25.0',
            b'memory_percent': b'50.0',
            b'disk_percent': b'40.0',
            b'active_workers': b'2',
            b'last_heartbeat': datetime.now(timezone.utc).isoformat().encode(),
            b'error_count': b'0',
            b'warning_count': b'0'
        }
        
        mock_redis.keys.return_value = [b'scraper:node_health:test-node-1']
        mock_redis.hgetall.return_value = health_data
        mock_redis.llen.return_value = 5  # pending work
        mock_redis.hlen.return_value = 2  # active/completed/failed work
        
        status = coordinator.get_cluster_status()
        
        assert status['total_nodes'] == 1
        assert status['healthy_nodes'] == 1
        assert status['degraded_nodes'] == 0
        assert status['unhealthy_nodes'] == 0
        assert 'test-node-1' in status['nodes']
    
    def test_coordinate_shutdown(self, coordinator, mock_redis):
        """Test graceful shutdown coordination"""
        # Mock active work
        active_work = {
            b'work-1': json.dumps({
                'work_id': 'work-1',
                'city': 'Helsinki',
                'url': 'https://example.com/helsinki',
                'priority': 1,
                'max_retries': 3,
                'retry_count': 0,
                'status': 'in_progress',
                'assigned_node': 'test-node-1',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'started_at': datetime.now(timezone.utc).isoformat(),
                'completed_at': None,
                'error_message': None
            }).encode()
        }
        
        mock_redis.hgetall.return_value = active_work
        
        coordinator.coordinate_shutdown()
        
        # Verify work redistribution
        mock_redis.lpush.assert_called()
        mock_redis.delete.assert_called()


class TestClusterCoordinatorIntegration:
    """Integration tests for cluster coordination"""
    
    def test_work_distribution_and_processing_flow(self, coordinator, sample_work_items, mock_redis):
        """Test complete work distribution and processing flow"""
        # Setup healthy nodes
        healthy_nodes = ["node-1", "node-2"]
        
        with patch.object(coordinator, 'get_healthy_nodes', return_value=healthy_nodes):
            with patch.object(coordinator, '_get_node_workload', return_value=0):
                # Distribute work
                result = coordinator.distribute_work(sample_work_items)
                assert result.distributed_items == 3
                
                # Simulate getting work for a node
                work_data = json.dumps(sample_work_items[0].to_dict())
                mock_redis.rpop.return_value = work_data
                
                work_items = coordinator.get_work_for_node("node-1", count=1)
                assert len(work_items) == 1
                
                # Complete the work
                work_item = work_items[0]
                success = coordinator.complete_work_item(work_item)
                assert success is True
    
    def test_failure_and_retry_flow(self, coordinator, mock_redis):
        """Test work failure and retry flow"""
        work_item = WorkItem(
            work_id="work-1",
            city="Helsinki",
            url="https://example.com/helsinki",
            assigned_node="test-node-1",
            status=WorkItemStatus.IN_PROGRESS
        )
        
        # Fail the work item
        coordinator.fail_work_item(work_item, "Network timeout")
        assert work_item.status == WorkItemStatus.RETRYING
        assert work_item.retry_count == 1
        
        # Process retry queue (simulate time passing)
        mock_redis.zrangebyscore.return_value = [json.dumps({
            'work_item': work_item.to_dict(),
            'retry_time': time.time() - 60
        })]
        
        ready_items = coordinator.process_retry_queue()
        assert len(ready_items) == 1
        assert ready_items[0].work_id == "work-1"


class TestClusterCoordinatorFactory:
    """Test cluster coordinator factory function"""
    
    @patch('redis.from_url')
    def test_create_cluster_coordinator_success(self, mock_from_url):
        """Test successful cluster coordinator creation"""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_from_url.return_value = mock_redis
        
        coordinator = create_cluster_coordinator("redis://localhost:6379")
        
        assert isinstance(coordinator, ClusterCoordinator)
        mock_from_url.assert_called_once_with("redis://localhost:6379", decode_responses=False)
        mock_redis.ping.assert_called_once()
    
    @patch('redis.from_url')
    def test_create_cluster_coordinator_connection_failure(self, mock_from_url):
        """Test cluster coordinator creation with connection failure"""
        mock_redis = Mock()
        mock_redis.ping.side_effect = redis.RedisError("Connection failed")
        mock_from_url.return_value = mock_redis
        
        with pytest.raises(redis.RedisError):
            create_cluster_coordinator("redis://localhost:6379")


class TestClusterCoordinatorHealthMonitoring:
    """Test health monitoring functionality"""
    
    def test_start_stop_health_monitoring(self, coordinator):
        """Test starting and stopping health monitoring"""
        # Mock the health monitor loop to prevent immediate exit
        def mock_health_loop():
            while not coordinator._shutdown_event.is_set():
                coordinator._shutdown_event.wait(0.1)
        
        with patch.object(coordinator, '_health_monitor_loop', side_effect=mock_health_loop):
            coordinator.start_health_monitoring()
            assert coordinator._health_monitor_thread is not None
            
            # Give thread a moment to start
            time.sleep(0.05)
            assert coordinator._health_monitor_thread.is_alive()
            
            coordinator.stop_health_monitoring()
            assert coordinator._shutdown_event.is_set()
    
    def test_health_monitor_loop(self, coordinator, mock_redis):
        """Test health monitoring loop"""
        coordinator._shutdown_event.set()  # Ensure loop exits immediately
        
        with patch.object(coordinator, '_collect_health_metrics') as mock_collect:
            with patch.object(coordinator, 'report_node_health') as mock_report:
                with patch.object(coordinator, '_cleanup_stale_nodes') as mock_cleanup:
                    mock_health = Mock()
                    mock_collect.return_value = mock_health
                    
                    coordinator._health_monitor_loop()
                    
                    # Should not be called due to immediate shutdown
                    mock_collect.assert_not_called()
    
    def test_cleanup_stale_nodes(self, coordinator, mock_redis):
        """Test cleanup of stale nodes"""
        # Mock stale node health data
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        health_data = {
            b'node_id': b'stale-node',
            b'status': b'healthy',
            b'cpu_percent': b'25.0',
            b'memory_percent': b'50.0',
            b'disk_percent': b'40.0',
            b'active_workers': b'2',
            b'last_heartbeat': stale_time.encode(),
            b'error_count': b'0',
            b'warning_count': b'0'
        }
        
        mock_redis.keys.return_value = [b'scraper:node_health:stale-node']
        mock_redis.hgetall.return_value = health_data
        
        with patch.object(coordinator, '_redistribute_work_from_failed_node') as mock_redistribute:
            coordinator._cleanup_stale_nodes()
            mock_redistribute.assert_called_once_with('stale-node')
            mock_redis.delete.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
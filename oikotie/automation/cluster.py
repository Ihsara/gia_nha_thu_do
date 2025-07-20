"""
Cluster Coordination Module for Daily Scraper Automation

This module provides Redis-based cluster coordination for distributed scraping execution,
including work distribution, distributed locking, node health reporting, and failure detection.
"""

import json
import time
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import redis
from loguru import logger
import threading
from .psutil_compat import psutil
import socket


class NodeStatus(Enum):
    """Node health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class WorkItemStatus(Enum):
    """Work item status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WorkItem:
    """Represents a unit of work to be distributed across cluster nodes"""
    work_id: str
    city: str
    url: str
    priority: int = 1
    max_retries: int = 3
    retry_count: int = 0
    status: WorkItemStatus = WorkItemStatus.PENDING
    assigned_node: Optional[str] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat() if value else None
            elif isinstance(value, WorkItemStatus):
                data[key] = value.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkItem':
        """Create WorkItem from dictionary"""
        # Convert ISO strings back to datetime objects
        for key in ['created_at', 'started_at', 'completed_at']:
            if data.get(key):
                data[key] = datetime.fromisoformat(data[key])
        
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = WorkItemStatus(data['status'])
        
        return cls(**data)


@dataclass
class HealthStatus:
    """Node health status information"""
    node_id: str
    status: NodeStatus
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    active_workers: int
    last_heartbeat: datetime
    error_count: int = 0
    warning_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage"""
        data = asdict(self)
        data['status'] = self.status.value
        data['last_heartbeat'] = self.last_heartbeat.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HealthStatus':
        """Create HealthStatus from dictionary"""
        data['status'] = NodeStatus(data['status'])
        data['last_heartbeat'] = datetime.fromisoformat(data['last_heartbeat'])
        return cls(**data)


@dataclass
class WorkDistribution:
    """Result of work distribution operation"""
    total_work_items: int
    distributed_items: int
    failed_items: int
    node_assignments: Dict[str, int]
    distribution_time: float


class ClusterCoordinator:
    """
    Redis-based cluster coordinator for distributed scraping execution.
    
    Provides work distribution, distributed locking, node health reporting,
    and failure detection for cluster deployments.
    """
    
    def __init__(self, redis_client: redis.Redis, node_id: Optional[str] = None):
        """
        Initialize cluster coordinator.
        
        Args:
            redis_client: Redis client instance
            node_id: Unique node identifier (auto-generated if None)
        """
        self.redis = redis_client
        self.node_id = node_id or self._generate_node_id()
        self.heartbeat_interval = 30  # seconds
        self.lock_ttl = 300  # 5 minutes default lock TTL
        self.work_queue_key = "scraper:work_queue"
        self.active_work_key = "scraper:active_work"
        self.completed_work_key = "scraper:completed_work"
        self.failed_work_key = "scraper:failed_work"
        self.node_health_key = "scraper:node_health"
        self.cluster_config_key = "scraper:cluster_config"
        
        # Health monitoring
        self._health_monitor_thread = None
        self._shutdown_event = threading.Event()
        
        logger.info(f"Cluster coordinator initialized for node: {self.node_id}")
    
    def _generate_node_id(self) -> str:
        """Generate unique node identifier"""
        hostname = socket.gethostname()
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        return f"{hostname}-{timestamp}-{unique_id}"
    
    def start_health_monitoring(self) -> None:
        """Start background health monitoring thread"""
        if self._health_monitor_thread and self._health_monitor_thread.is_alive():
            logger.warning("Health monitoring already running")
            return
        
        self._shutdown_event.clear()
        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True
        )
        self._health_monitor_thread.start()
        logger.info("Health monitoring started")
    
    def stop_health_monitoring(self) -> None:
        """Stop background health monitoring thread"""
        self._shutdown_event.set()
        if self._health_monitor_thread:
            self._health_monitor_thread.join(timeout=5)
        logger.info("Health monitoring stopped")
    
    def _health_monitor_loop(self) -> None:
        """Background health monitoring loop"""
        while not self._shutdown_event.is_set():
            try:
                health_status = self._collect_health_metrics()
                self.report_node_health(self.node_id, health_status)
                self._cleanup_stale_nodes()
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
            
            self._shutdown_event.wait(self.heartbeat_interval)
    
    def _collect_health_metrics(self) -> HealthStatus:
        """Collect current node health metrics"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Get disk usage - handle Windows vs Unix paths
        try:
            if hasattr(psutil, 'disk_usage'):
                # Try current directory first (works on Windows)
                disk = psutil.disk_usage('.')
            else:
                # Fallback for systems without disk_usage
                disk = type('DiskUsage', (), {'percent': 0})()
        except (OSError, AttributeError):
            # Fallback if disk usage fails
            disk = type('DiskUsage', (), {'percent': 0})()
        
        # Determine status based on resource usage
        status = NodeStatus.HEALTHY
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
            status = NodeStatus.UNHEALTHY
        elif cpu_percent > 70 or memory.percent > 70 or disk.percent > 80:
            status = NodeStatus.DEGRADED
        
        # Get active worker count from Redis
        active_workers = len(self.get_active_work_for_node(self.node_id))
        
        return HealthStatus(
            node_id=self.node_id,
            status=status,
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            active_workers=active_workers,
            last_heartbeat=datetime.now(timezone.utc)
        )
    
    def acquire_work_lock(self, work_id: str, ttl: int = None) -> bool:
        """
        Acquire distributed lock for work item.
        
        Args:
            work_id: Unique work item identifier
            ttl: Lock time-to-live in seconds
            
        Returns:
            True if lock acquired, False otherwise
        """
        ttl = ttl or self.lock_ttl
        lock_key = f"scraper:lock:{work_id}"
        
        try:
            # Use SET with NX (only if not exists) and EX (expiration)
            result = self.redis.set(
                lock_key, 
                self.node_id, 
                nx=True, 
                ex=ttl
            )
            
            if result:
                logger.debug(f"Acquired lock for work item {work_id}")
                return True
            else:
                logger.debug(f"Failed to acquire lock for work item {work_id}")
                return False
                
        except redis.RedisError as e:
            logger.error(f"Redis error acquiring lock for {work_id}: {e}")
            return False
    
    def release_work_lock(self, work_id: str) -> bool:
        """
        Release distributed lock for work item.
        
        Args:
            work_id: Unique work item identifier
            
        Returns:
            True if lock released, False otherwise
        """
        lock_key = f"scraper:lock:{work_id}"
        
        try:
            # Use Lua script to ensure we only delete our own lock
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = self.redis.eval(lua_script, 1, lock_key, self.node_id)
            
            if result:
                logger.debug(f"Released lock for work item {work_id}")
                return True
            else:
                logger.warning(f"Could not release lock for {work_id} (not owned by this node)")
                return False
                
        except redis.RedisError as e:
            logger.error(f"Redis error releasing lock for {work_id}: {e}")
            return False
    
    def distribute_work(self, work_items: List[WorkItem]) -> WorkDistribution:
        """
        Distribute work items across cluster nodes.
        
        Args:
            work_items: List of work items to distribute
            
        Returns:
            WorkDistribution result
        """
        start_time = time.time()
        distributed_count = 0
        failed_count = 0
        node_assignments = {}
        
        # Get healthy nodes
        healthy_nodes = self.get_healthy_nodes()
        if not healthy_nodes:
            logger.error("No healthy nodes available for work distribution")
            return WorkDistribution(
                total_work_items=len(work_items),
                distributed_items=0,
                failed_items=len(work_items),
                node_assignments={},
                distribution_time=time.time() - start_time
            )
        
        logger.info(f"Distributing {len(work_items)} work items across {len(healthy_nodes)} nodes")
        
        # Sort nodes by current workload (ascending)
        node_workloads = {node_id: self._get_node_workload(node_id) for node_id in healthy_nodes}
        sorted_nodes = sorted(healthy_nodes, key=lambda x: node_workloads[x])
        
        try:
            pipe = self.redis.pipeline()
            
            for i, work_item in enumerate(work_items):
                # Round-robin assignment to nodes with lowest workload
                assigned_node = sorted_nodes[i % len(sorted_nodes)]
                work_item.assigned_node = assigned_node
                work_item.status = WorkItemStatus.PENDING
                
                # Add to work queue
                queue_key = f"{self.work_queue_key}:{assigned_node}"
                pipe.lpush(queue_key, json.dumps(work_item.to_dict()))
                
                # Track assignment
                node_assignments[assigned_node] = node_assignments.get(assigned_node, 0) + 1
                distributed_count += 1
            
            # Execute pipeline
            pipe.execute()
            logger.success(f"Successfully distributed {distributed_count} work items")
            
        except redis.RedisError as e:
            logger.error(f"Redis error during work distribution: {e}")
            failed_count = len(work_items) - distributed_count
        
        return WorkDistribution(
            total_work_items=len(work_items),
            distributed_items=distributed_count,
            failed_items=failed_count,
            node_assignments=node_assignments,
            distribution_time=time.time() - start_time
        )
    
    def get_work_for_node(self, node_id: str, count: int = 1) -> List[WorkItem]:
        """
        Get work items assigned to a specific node.
        
        Args:
            node_id: Node identifier
            count: Maximum number of work items to retrieve
            
        Returns:
            List of work items
        """
        queue_key = f"{self.work_queue_key}:{node_id}"
        work_items = []
        
        try:
            for _ in range(count):
                work_data = self.redis.rpop(queue_key)
                if not work_data:
                    break
                
                work_item = WorkItem.from_dict(json.loads(work_data))
                work_item.status = WorkItemStatus.IN_PROGRESS
                work_item.started_at = datetime.now(timezone.utc)
                
                # Move to active work tracking
                active_key = f"{self.active_work_key}:{node_id}"
                self.redis.hset(active_key, work_item.work_id, json.dumps(work_item.to_dict()))
                
                work_items.append(work_item)
                
        except redis.RedisError as e:
            logger.error(f"Redis error getting work for node {node_id}: {e}")
        
        return work_items
    
    def complete_work_item(self, work_item: WorkItem) -> bool:
        """
        Mark work item as completed.
        
        Args:
            work_item: Completed work item
            
        Returns:
            True if successfully marked as completed
        """
        try:
            work_item.status = WorkItemStatus.COMPLETED
            work_item.completed_at = datetime.now(timezone.utc)
            
            # Remove from active work
            active_key = f"{self.active_work_key}:{work_item.assigned_node}"
            self.redis.hdel(active_key, work_item.work_id)
            
            # Add to completed work
            completed_key = f"{self.completed_work_key}:{work_item.assigned_node}"
            self.redis.hset(completed_key, work_item.work_id, json.dumps(work_item.to_dict()))
            
            # Set expiration for completed work (24 hours)
            self.redis.expire(completed_key, 86400)
            
            logger.debug(f"Marked work item {work_item.work_id} as completed")
            return True
            
        except redis.RedisError as e:
            logger.error(f"Redis error completing work item {work_item.work_id}: {e}")
            return False
    
    def fail_work_item(self, work_item: WorkItem, error_message: str) -> bool:
        """
        Mark work item as failed and handle retry logic.
        
        Args:
            work_item: Failed work item
            error_message: Error description
            
        Returns:
            True if successfully handled
        """
        try:
            work_item.error_message = error_message
            work_item.retry_count += 1
            
            # Remove from active work
            active_key = f"{self.active_work_key}:{work_item.assigned_node}"
            self.redis.hdel(active_key, work_item.work_id)
            
            if work_item.retry_count < work_item.max_retries:
                # Retry with exponential backoff
                work_item.status = WorkItemStatus.RETRYING
                delay = min(300, 30 * (2 ** work_item.retry_count))  # Max 5 minutes
                
                # Schedule retry
                retry_time = time.time() + delay
                retry_key = f"scraper:retry_queue"
                retry_data = {
                    'work_item': work_item.to_dict(),
                    'retry_time': retry_time
                }
                self.redis.zadd(retry_key, {json.dumps(retry_data): retry_time})
                
                logger.info(f"Scheduled retry for work item {work_item.work_id} in {delay} seconds")
            else:
                # Max retries exceeded
                work_item.status = WorkItemStatus.FAILED
                failed_key = f"{self.failed_work_key}:{work_item.assigned_node}"
                self.redis.hset(failed_key, work_item.work_id, json.dumps(work_item.to_dict()))
                
                logger.error(f"Work item {work_item.work_id} failed permanently after {work_item.retry_count} retries")
            
            return True
            
        except redis.RedisError as e:
            logger.error(f"Redis error failing work item {work_item.work_id}: {e}")
            return False
    
    def process_retry_queue(self) -> List[WorkItem]:
        """
        Process retry queue and return items ready for retry.
        
        Returns:
            List of work items ready for retry
        """
        retry_key = "scraper:retry_queue"
        current_time = time.time()
        ready_items = []
        
        try:
            # Get items ready for retry
            ready_data = self.redis.zrangebyscore(retry_key, 0, current_time)
            
            if ready_data:
                # Remove processed items from retry queue
                self.redis.zremrangebyscore(retry_key, 0, current_time)
                
                for data in ready_data:
                    retry_info = json.loads(data)
                    work_item = WorkItem.from_dict(retry_info['work_item'])
                    ready_items.append(work_item)
                
                logger.info(f"Found {len(ready_items)} items ready for retry")
            
        except redis.RedisError as e:
            logger.error(f"Redis error processing retry queue: {e}")
        
        return ready_items
    
    def report_node_health(self, node_id: str, health_status: HealthStatus) -> None:
        """
        Report node health status to cluster.
        
        Args:
            node_id: Node identifier
            health_status: Current health status
        """
        try:
            health_key = f"{self.node_health_key}:{node_id}"
            self.redis.hset(health_key, mapping=health_status.to_dict())
            self.redis.expire(health_key, self.heartbeat_interval * 3)  # 3x heartbeat interval
            
            logger.debug(f"Reported health for node {node_id}: {health_status.status.value}")
            
        except redis.RedisError as e:
            logger.error(f"Redis error reporting health for node {node_id}: {e}")
    
    def get_healthy_nodes(self) -> List[str]:
        """
        Get list of healthy cluster nodes.
        
        Returns:
            List of healthy node IDs
        """
        healthy_nodes = []
        
        try:
            # Get all node health keys
            health_keys = self.redis.keys(f"{self.node_health_key}:*")
            
            for key in health_keys:
                node_id = key.decode().split(':')[-1]
                health_data = self.redis.hgetall(key)
                
                if health_data:
                    # Convert bytes to strings
                    health_dict = {k.decode(): v.decode() for k, v in health_data.items()}
                    health_status = HealthStatus.from_dict(health_dict)
                    
                    # Check if node is healthy and recent
                    if (health_status.status in [NodeStatus.HEALTHY, NodeStatus.DEGRADED] and
                        datetime.now(timezone.utc) - health_status.last_heartbeat < timedelta(minutes=2)):
                        healthy_nodes.append(node_id)
            
        except redis.RedisError as e:
            logger.error(f"Redis error getting healthy nodes: {e}")
        
        return healthy_nodes
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """
        Get comprehensive cluster status information.
        
        Returns:
            Cluster status dictionary
        """
        status = {
            'total_nodes': 0,
            'healthy_nodes': 0,
            'degraded_nodes': 0,
            'unhealthy_nodes': 0,
            'total_work_items': 0,
            'pending_work_items': 0,
            'active_work_items': 0,
            'completed_work_items': 0,
            'failed_work_items': 0,
            'nodes': {}
        }
        
        try:
            # Get node health information
            health_keys = self.redis.keys(f"{self.node_health_key}:*")
            
            for key in health_keys:
                node_id = key.decode().split(':')[-1]
                health_data = self.redis.hgetall(key)
                
                if health_data:
                    health_dict = {k.decode(): v.decode() for k, v in health_data.items()}
                    health_status = HealthStatus.from_dict(health_dict)
                    
                    status['total_nodes'] += 1
                    status['nodes'][node_id] = health_status.to_dict()
                    
                    # Count by status
                    if health_status.status == NodeStatus.HEALTHY:
                        status['healthy_nodes'] += 1
                    elif health_status.status == NodeStatus.DEGRADED:
                        status['degraded_nodes'] += 1
                    else:
                        status['unhealthy_nodes'] += 1
            
            # Get work queue statistics
            for node_id in status['nodes'].keys():
                pending = self.redis.llen(f"{self.work_queue_key}:{node_id}")
                active = self.redis.hlen(f"{self.active_work_key}:{node_id}")
                completed = self.redis.hlen(f"{self.completed_work_key}:{node_id}")
                failed = self.redis.hlen(f"{self.failed_work_key}:{node_id}")
                
                status['pending_work_items'] += pending
                status['active_work_items'] += active
                status['completed_work_items'] += completed
                status['failed_work_items'] += failed
                
                status['nodes'][node_id].update({
                    'pending_work': pending,
                    'active_work': active,
                    'completed_work': completed,
                    'failed_work': failed
                })
            
            status['total_work_items'] = (
                status['pending_work_items'] + 
                status['active_work_items'] + 
                status['completed_work_items'] + 
                status['failed_work_items']
            )
            
        except redis.RedisError as e:
            logger.error(f"Redis error getting cluster status: {e}")
        
        return status
    
    def coordinate_shutdown(self) -> None:
        """Coordinate graceful shutdown across cluster"""
        logger.info(f"Initiating graceful shutdown for node {self.node_id}")
        
        try:
            # Stop health monitoring
            self.stop_health_monitoring()
            
            # Move active work back to queue for redistribution
            active_key = f"{self.active_work_key}:{self.node_id}"
            active_work = self.redis.hgetall(active_key)
            
            if active_work:
                logger.info(f"Redistributing {len(active_work)} active work items")
                
                for work_id, work_data in active_work.items():
                    work_item = WorkItem.from_dict(json.loads(work_data))
                    work_item.status = WorkItemStatus.PENDING
                    work_item.assigned_node = None
                    work_item.started_at = None
                    
                    # Add back to general work queue for redistribution
                    self.redis.lpush(self.work_queue_key, json.dumps(work_item.to_dict()))
                
                # Clear active work for this node
                self.redis.delete(active_key)
            
            # Remove node health information
            health_key = f"{self.node_health_key}:{self.node_id}"
            self.redis.delete(health_key)
            
            logger.info(f"Graceful shutdown completed for node {self.node_id}")
            
        except redis.RedisError as e:
            logger.error(f"Redis error during shutdown coordination: {e}")
    
    def _get_node_workload(self, node_id: str) -> int:
        """Get current workload for a node"""
        try:
            pending = self.redis.llen(f"{self.work_queue_key}:{node_id}")
            active = self.redis.hlen(f"{self.active_work_key}:{node_id}")
            return pending + active
        except redis.RedisError:
            return 0
    
    def get_active_work_for_node(self, node_id: str) -> List[WorkItem]:
        """Get active work items for a specific node"""
        active_work = []
        try:
            active_key = f"{self.active_work_key}:{node_id}"
            work_data = self.redis.hgetall(active_key)
            
            for work_id, data in work_data.items():
                work_item = WorkItem.from_dict(json.loads(data))
                active_work.append(work_item)
                
        except redis.RedisError as e:
            logger.error(f"Redis error getting active work for node {node_id}: {e}")
        
        return active_work
    
    def _cleanup_stale_nodes(self) -> None:
        """Clean up stale node information"""
        try:
            health_keys = self.redis.keys(f"{self.node_health_key}:*")
            stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
            
            for key in health_keys:
                health_data = self.redis.hgetall(key)
                if health_data:
                    health_dict = {k.decode(): v.decode() for k, v in health_data.items()}
                    health_status = HealthStatus.from_dict(health_dict)
                    
                    if health_status.last_heartbeat < stale_threshold:
                        node_id = key.decode().split(':')[-1]
                        logger.warning(f"Cleaning up stale node: {node_id}")
                        
                        # Redistribute work from stale node
                        self._redistribute_work_from_failed_node(node_id)
                        
                        # Remove stale health information
                        self.redis.delete(key)
                        
        except redis.RedisError as e:
            logger.error(f"Redis error during stale node cleanup: {e}")
    
    def _redistribute_work_from_failed_node(self, failed_node_id: str) -> None:
        """Redistribute work from a failed node"""
        try:
            # Get active work from failed node
            active_key = f"{self.active_work_key}:{failed_node_id}"
            active_work = self.redis.hgetall(active_key)
            
            # Get pending work from failed node
            queue_key = f"{self.work_queue_key}:{failed_node_id}"
            pending_work = []
            
            while True:
                work_data = self.redis.rpop(queue_key)
                if not work_data:
                    break
                pending_work.append(json.loads(work_data))
            
            # Redistribute all work
            all_work = []
            
            # Add active work (reset to pending)
            for work_id, work_data in active_work.items():
                work_item = WorkItem.from_dict(json.loads(work_data))
                work_item.status = WorkItemStatus.PENDING
                work_item.assigned_node = None
                work_item.started_at = None
                all_work.append(work_item)
            
            # Add pending work
            for work_data in pending_work:
                work_item = WorkItem.from_dict(work_data)
                all_work.append(work_item)
            
            if all_work:
                logger.info(f"Redistributing {len(all_work)} work items from failed node {failed_node_id}")
                self.distribute_work(all_work)
            
            # Clean up failed node's work queues
            self.redis.delete(active_key)
            self.redis.delete(queue_key)
            
        except redis.RedisError as e:
            logger.error(f"Redis error redistributing work from failed node {failed_node_id}: {e}")


def create_cluster_coordinator(redis_url: str = "redis://localhost:6379", **kwargs) -> ClusterCoordinator:
    """
    Factory function to create cluster coordinator with Redis connection.
    
    Args:
        redis_url: Redis connection URL
        **kwargs: Additional arguments for ClusterCoordinator
        
    Returns:
        ClusterCoordinator instance
    """
    try:
        redis_client = redis.from_url(redis_url, decode_responses=False)
        
        # Test connection
        redis_client.ping()
        logger.info(f"Connected to Redis at {redis_url}")
        
        return ClusterCoordinator(redis_client, **kwargs)
        
    except redis.RedisError as e:
        logger.error(f"Failed to connect to Redis at {redis_url}: {e}")
        raise
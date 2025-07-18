# Cluster Coordination System

## Overview

The cluster coordination system provides Redis-based distributed execution capabilities for the Oikotie scraper automation. It enables multiple scraper nodes to work together efficiently while preventing duplicate work and providing failure recovery.

## Architecture

### Core Components

1. **ClusterCoordinator**: Main coordination class that manages distributed operations
2. **WorkItem**: Represents a unit of work (e.g., scraping a city)
3. **HealthStatus**: Node health monitoring and reporting
4. **WorkDistribution**: Work assignment across cluster nodes
5. **Distributed Locking**: Prevents duplicate work execution

### Key Features

- **Work Distribution**: Intelligent assignment of scraping tasks across nodes
- **Distributed Locking**: Redis-based locks prevent duplicate work
- **Health Monitoring**: Continuous node health tracking and reporting
- **Failure Detection**: Automatic detection and handling of failed nodes
- **Work Redistribution**: Failed work is reassigned to healthy nodes
- **Retry Logic**: Exponential backoff for failed work items
- **Graceful Shutdown**: Coordinated shutdown with work redistribution

## Usage

### Basic Setup

```python
from oikotie.automation.cluster import create_cluster_coordinator, WorkItem

# Create cluster coordinator
coordinator = create_cluster_coordinator("redis://localhost:6379")

# Start health monitoring
coordinator.start_health_monitoring()
```

### Work Distribution

```python
# Create work items
work_items = [
    WorkItem(work_id="helsinki-1", city="Helsinki", url="https://..."),
    WorkItem(work_id="espoo-1", city="Espoo", url="https://..."),
    WorkItem(work_id="vantaa-1", city="Vantaa", url="https://...")
]

# Distribute work across cluster
result = coordinator.distribute_work(work_items)
print(f"Distributed {result.distributed_items} items to {len(result.node_assignments)} nodes")
```

### Processing Work

```python
# Get work for this node
work_items = coordinator.get_work_for_node(coordinator.node_id, count=5)

for work_item in work_items:
    try:
        # Acquire lock for work item
        if coordinator.acquire_work_lock(work_item.work_id):
            # Process the work item
            result = process_scraping_work(work_item)
            
            # Mark as completed
            coordinator.complete_work_item(work_item)
            
            # Release lock
            coordinator.release_work_lock(work_item.work_id)
        else:
            print(f"Could not acquire lock for {work_item.work_id}")
            
    except Exception as e:
        # Handle failure with retry logic
        coordinator.fail_work_item(work_item, str(e))
```

### Health Monitoring

```python
# Get cluster status
status = coordinator.get_cluster_status()
print(f"Cluster has {status['healthy_nodes']} healthy nodes")
print(f"Total work items: {status['total_work_items']}")

# Get healthy nodes
healthy_nodes = coordinator.get_healthy_nodes()
print(f"Healthy nodes: {healthy_nodes}")
```

### Graceful Shutdown

```python
# Coordinate shutdown (redistributes active work)
coordinator.coordinate_shutdown()
```

## Data Models

### WorkItem

Represents a unit of work to be processed:

```python
@dataclass
class WorkItem:
    work_id: str              # Unique identifier
    city: str                 # City to scrape
    url: str                  # URL to process
    priority: int = 1         # Priority (higher = more important)
    max_retries: int = 3      # Maximum retry attempts
    retry_count: int = 0      # Current retry count
    status: WorkItemStatus    # Current status
    assigned_node: str        # Node assigned to process
    created_at: datetime      # Creation timestamp
    started_at: datetime      # Processing start time
    completed_at: datetime    # Completion timestamp
    error_message: str        # Last error message
```

### HealthStatus

Node health information:

```python
@dataclass
class HealthStatus:
    node_id: str              # Node identifier
    status: NodeStatus        # Health status (HEALTHY/DEGRADED/UNHEALTHY)
    cpu_percent: float        # CPU usage percentage
    memory_percent: float     # Memory usage percentage
    disk_percent: float       # Disk usage percentage
    active_workers: int       # Number of active work items
    last_heartbeat: datetime  # Last heartbeat timestamp
    error_count: int = 0      # Number of errors
    warning_count: int = 0    # Number of warnings
```

## Redis Data Structure

The system uses the following Redis keys:

### Work Queues
- `scraper:work_queue:{node_id}` - Pending work for specific node
- `scraper:active_work:{node_id}` - Currently processing work
- `scraper:completed_work:{node_id}` - Completed work (24h TTL)
- `scraper:failed_work:{node_id}` - Failed work items
- `scraper:retry_queue` - Work items scheduled for retry

### Coordination
- `scraper:lock:{work_id}` - Distributed locks for work items
- `scraper:node_health:{node_id}` - Node health information
- `scraper:cluster_config` - Cluster configuration

## Configuration

### Environment Variables

- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379`)
- `NODE_ID`: Custom node identifier (auto-generated if not set)
- `HEARTBEAT_INTERVAL`: Health check interval in seconds (default: 30)
- `LOCK_TTL`: Lock time-to-live in seconds (default: 300)

### Cluster Configuration

```python
coordinator = ClusterCoordinator(
    redis_client=redis_client,
    node_id="custom-node-id",
    heartbeat_interval=30,
    lock_ttl=300
)
```

## Monitoring and Observability

### Cluster Status

```python
status = coordinator.get_cluster_status()
# Returns:
{
    'total_nodes': 3,
    'healthy_nodes': 2,
    'degraded_nodes': 1,
    'unhealthy_nodes': 0,
    'total_work_items': 150,
    'pending_work_items': 45,
    'active_work_items': 12,
    'completed_work_items': 88,
    'failed_work_items': 5,
    'nodes': {
        'node-1': {
            'status': 'healthy',
            'cpu_percent': 45.0,
            'memory_percent': 60.0,
            'pending_work': 15,
            'active_work': 4
        }
    }
}
```

### Health Metrics

Each node reports:
- CPU usage percentage
- Memory usage percentage  
- Disk usage percentage
- Number of active workers
- Error and warning counts
- Last heartbeat timestamp

## Error Handling

### Failure Scenarios

1. **Node Failure**: Detected via missed heartbeats, work redistributed
2. **Work Item Failure**: Retry with exponential backoff up to max retries
3. **Redis Connection Loss**: Graceful degradation, local fallback
4. **Lock Timeout**: Automatic lock release, work redistribution

### Retry Logic

Failed work items are retried with exponential backoff:
- Retry 1: 30 seconds delay
- Retry 2: 60 seconds delay  
- Retry 3: 120 seconds delay
- Max delay: 300 seconds (5 minutes)

### Recovery Mechanisms

- **Stale Node Cleanup**: Removes nodes that haven't reported in 5+ minutes
- **Work Redistribution**: Moves work from failed nodes to healthy ones
- **Lock Recovery**: Expired locks are automatically released
- **Health Recovery**: Degraded nodes can recover to healthy status

## Best Practices

### Node Management

1. **Unique Node IDs**: Ensure each node has a unique identifier
2. **Health Monitoring**: Always start health monitoring on node startup
3. **Graceful Shutdown**: Use `coordinate_shutdown()` before terminating
4. **Resource Monitoring**: Monitor CPU, memory, and disk usage

### Work Distribution

1. **Appropriate Batch Sizes**: Don't create too many small work items
2. **Priority Assignment**: Use priority for time-sensitive work
3. **Retry Limits**: Set reasonable max_retries based on work complexity
4. **Lock TTL**: Set lock TTL longer than expected work duration

### Redis Configuration

1. **Persistence**: Enable Redis persistence for work queue durability
2. **Memory Management**: Configure appropriate Redis memory limits
3. **Connection Pooling**: Use connection pooling for high-throughput scenarios
4. **Monitoring**: Monitor Redis performance and memory usage

## Troubleshooting

### Common Issues

1. **Work Not Distributed**: Check if nodes are healthy and reporting
2. **Duplicate Work**: Verify distributed locking is working correctly
3. **High Retry Rates**: Check for network issues or resource constraints
4. **Node Not Responding**: Verify Redis connectivity and health monitoring

### Debugging Commands

```python
# Check cluster status
status = coordinator.get_cluster_status()

# Get healthy nodes
healthy = coordinator.get_healthy_nodes()

# Check active work for node
active = coordinator.get_active_work_for_node("node-id")

# Process retry queue
ready_items = coordinator.process_retry_queue()
```

### Logging

The system uses structured logging with loguru:
- DEBUG: Lock acquisition/release, work assignment
- INFO: Work distribution, node health changes
- WARNING: Failed lock acquisition, degraded nodes
- ERROR: Work failures, Redis connection issues
- CRITICAL: System failures, coordination errors

## Integration with Scraper

The cluster coordination integrates with the existing scraper through:

1. **Work Item Creation**: Convert scraping tasks to WorkItems
2. **Processing Integration**: Wrap scraper execution with coordination
3. **Error Handling**: Map scraper errors to coordination failures
4. **Status Reporting**: Report scraping progress through health metrics

Example integration:

```python
class ClusterAwareScraper:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.scraper = OikotieScraper()
    
    def process_work_items(self):
        work_items = self.coordinator.get_work_for_node(
            self.coordinator.node_id, 
            count=5
        )
        
        for work_item in work_items:
            if self.coordinator.acquire_work_lock(work_item.work_id):
                try:
                    # Execute scraping
                    results = self.scraper.scrape_city(work_item.city, work_item.url)
                    
                    # Mark completed
                    self.coordinator.complete_work_item(work_item)
                    
                except Exception as e:
                    # Handle failure
                    self.coordinator.fail_work_item(work_item, str(e))
                
                finally:
                    self.coordinator.release_work_lock(work_item.work_id)
```

This integration enables the scraper to work efficiently in a distributed environment while maintaining data consistency and reliability.
"""
Daily Scraper Automation Package

This package provides automation capabilities for the Oikotie scraper including:
- Cluster coordination and distributed execution
- Smart deduplication and scheduling
- Status reporting and monitoring
- Deployment management
"""

from .cluster import (
    ClusterCoordinator,
    WorkItem,
    WorkItemStatus,
    HealthStatus,
    NodeStatus,
    WorkDistribution,
    create_cluster_coordinator
)

__all__ = [
    'ClusterCoordinator',
    'WorkItem', 
    'WorkItemStatus',
    'HealthStatus',
    'NodeStatus',
    'WorkDistribution',
    'create_cluster_coordinator'
]
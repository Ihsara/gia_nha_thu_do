"""
Circuit Breaker Pattern Implementation for Multi-City Automation

This module provides circuit breaker functionality to prevent cascading failures
and provide graceful degradation when services are experiencing issues.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, Any, Type, Dict
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class CircuitBreakerState(Enum):
    """Circuit breaker state enumeration."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics for monitoring."""
    state: CircuitBreakerState
    failure_count: int
    success_count: int
    last_failure_time: Optional[datetime]
    last_success_time: Optional[datetime]
    total_requests: int
    failure_rate: float
    uptime_percentage: float
    state_changes: int
    time_in_open_state: float  # seconds


class CircuitBreaker:
    """
    Circuit breaker implementation with configurable failure thresholds
    and recovery mechanisms.
    
    The circuit breaker prevents cascading failures by:
    1. Monitoring failure rates
    2. Opening the circuit when failure threshold is exceeded
    3. Allowing limited requests in half-open state to test recovery
    4. Closing the circuit when service recovers
    """
    
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: Type[Exception] = Exception,
                 success_threshold: int = 3):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open state
            expected_exception: Exception type that triggers circuit breaker
            success_threshold: Successful requests needed to close circuit from half-open
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        
        # State tracking
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.now()
        self.state_changes = 0
        self.total_requests = 0
        
        # Thread safety
        self.lock = threading.Lock()
        
        logger.debug(f"Circuit breaker initialized: "
                    f"failure_threshold={failure_threshold}, "
                    f"recovery_timeout={recovery_timeout}s")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenException: When circuit is open
            Original exception: When function fails
        """
        with self.lock:
            # Check if circuit should transition to half-open
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise CircuitBreakerOpenException(
                        f"Circuit breaker is open. Last failure: {self.last_failure_time}"
                    )
            
            # In half-open state, only allow limited requests
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()
        
        # Execute the function
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
            
        except self.expected_exception as e:
            self.record_failure()
            raise e
    
    def record_success(self) -> None:
        """Record a successful operation."""
        with self.lock:
            self.success_count += 1
            self.total_requests += 1
            self.last_success_time = datetime.now()
            
            # Reset consecutive failure count on success (but keep total failure count)
            if self.state == CircuitBreakerState.CLOSED:
                self.failure_count = 0  # Reset consecutive failures
            
            # Transition from half-open to closed if enough successes
            elif self.state == CircuitBreakerState.HALF_OPEN:
                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()
            
            logger.debug(f"Circuit breaker recorded success: "
                        f"state={self.state.value}, "
                        f"success_count={self.success_count}")
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        with self.lock:
            self.failure_count += 1
            self.total_requests += 1
            self.last_failure_time = datetime.now()
            
            # Transition to open if failure threshold exceeded
            if (self.state == CircuitBreakerState.CLOSED and 
                self.failure_count >= self.failure_threshold):
                self._transition_to_open()
            
            # Transition back to open from half-open on failure
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self._transition_to_open()
            
            logger.debug(f"Circuit breaker recorded failure: "
                        f"state={self.state.value}, "
                        f"failure_count={self.failure_count}")
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset to half-open."""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout
    
    def _transition_to_open(self) -> None:
        """Transition circuit breaker to open state."""
        if self.state != CircuitBreakerState.OPEN:
            logger.warning(f"Circuit breaker opening: "
                          f"failure_count={self.failure_count}, "
                          f"threshold={self.failure_threshold}")
            
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0  # Reset success count
            self.last_state_change = datetime.now()
            self.state_changes += 1
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to half-open state."""
        logger.info("Circuit breaker transitioning to half-open state")
        
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0  # Reset success count for testing
        self.last_state_change = datetime.now()
        self.state_changes += 1
    
    def _transition_to_closed(self) -> None:
        """Transition circuit breaker to closed state."""
        logger.info(f"Circuit breaker closing: "
                   f"success_count={self.success_count}, "
                   f"threshold={self.success_threshold}")
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0  # Reset failure count
        self.success_count = 0  # Reset success count
        self.last_state_change = datetime.now()
        self.state_changes += 1
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """
        Get current circuit breaker metrics.
        
        Returns:
            CircuitBreakerMetrics with current state and statistics
        """
        with self.lock:
            # Calculate failure rate
            failure_rate = 0.0
            if self.total_requests > 0:
                total_failures = self.failure_count
                if self.state == CircuitBreakerState.CLOSED:
                    # For closed state, use historical failure count
                    pass
                failure_rate = total_failures / self.total_requests
            
            # Calculate uptime percentage
            uptime_percentage = 100.0
            if self.last_failure_time and self.last_success_time:
                total_time = (datetime.now() - min(self.last_failure_time, self.last_success_time)).total_seconds()
                if total_time > 0:
                    # Simplified uptime calculation
                    if self.state == CircuitBreakerState.OPEN:
                        open_time = (datetime.now() - self.last_state_change).total_seconds()
                        uptime_percentage = max(0, 100 - (open_time / total_time * 100))
            
            # Calculate time in open state
            time_in_open_state = 0.0
            if self.state == CircuitBreakerState.OPEN and self.last_state_change:
                time_in_open_state = (datetime.now() - self.last_state_change).total_seconds()
            
            return CircuitBreakerMetrics(
                state=self.state,
                failure_count=self.failure_count,
                success_count=self.success_count,
                last_failure_time=self.last_failure_time,
                last_success_time=self.last_success_time,
                total_requests=self.total_requests,
                failure_rate=failure_rate,
                uptime_percentage=uptime_percentage,
                state_changes=self.state_changes,
                time_in_open_state=time_in_open_state
            )
    
    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        with self.lock:
            logger.info("Circuit breaker manually reset")
            
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_state_change = datetime.now()
            self.state_changes += 1
    
    def force_open(self) -> None:
        """Force circuit breaker to open state."""
        with self.lock:
            logger.warning("Circuit breaker manually forced open")
            
            self.state = CircuitBreakerState.OPEN
            self.last_failure_time = datetime.now()
            self.last_state_change = datetime.now()
            self.state_changes += 1
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed."""
        return self.state == CircuitBreakerState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == CircuitBreakerState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        return self.state == CircuitBreakerState.HALF_OPEN


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers with centralized monitoring.
    """
    
    def __init__(self):
        """Initialize circuit breaker manager."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.lock = threading.Lock()
        
        logger.info("Circuit breaker manager initialized")
    
    def get_circuit_breaker(self, 
                           name: str,
                           failure_threshold: int = 5,
                           recovery_timeout: int = 60,
                           expected_exception: Type[Exception] = Exception,
                           success_threshold: int = 3) -> CircuitBreaker:
        """
        Get or create a circuit breaker by name.
        
        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open state
            expected_exception: Exception type that triggers circuit breaker
            success_threshold: Successful requests needed to close circuit
            
        Returns:
            CircuitBreaker instance
        """
        with self.lock:
            if name not in self.circuit_breakers:
                self.circuit_breakers[name] = CircuitBreaker(
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    expected_exception=expected_exception,
                    success_threshold=success_threshold
                )
                logger.debug(f"Created circuit breaker: {name}")
            
            return self.circuit_breakers[name]
    
    def get_all_metrics(self) -> Dict[str, CircuitBreakerMetrics]:
        """
        Get metrics for all circuit breakers.
        
        Returns:
            Dictionary mapping circuit breaker names to their metrics
        """
        with self.lock:
            return {
                name: cb.get_metrics() 
                for name, cb in self.circuit_breakers.items()
            }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for all circuit breakers.
        
        Returns:
            Summary statistics dictionary
        """
        with self.lock:
            total_breakers = len(self.circuit_breakers)
            open_breakers = sum(1 for cb in self.circuit_breakers.values() if cb.is_open)
            half_open_breakers = sum(1 for cb in self.circuit_breakers.values() if cb.is_half_open)
            closed_breakers = sum(1 for cb in self.circuit_breakers.values() if cb.is_closed)
            
            total_requests = sum(cb.total_requests for cb in self.circuit_breakers.values())
            total_failures = sum(cb.failure_count for cb in self.circuit_breakers.values())
            
            overall_failure_rate = (total_failures / total_requests) if total_requests > 0 else 0.0
            
            return {
                'total_circuit_breakers': total_breakers,
                'open_breakers': open_breakers,
                'half_open_breakers': half_open_breakers,
                'closed_breakers': closed_breakers,
                'overall_failure_rate': overall_failure_rate,
                'total_requests': total_requests,
                'total_failures': total_failures,
                'health_percentage': (closed_breakers / total_breakers * 100) if total_breakers > 0 else 100.0
            }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers to closed state."""
        with self.lock:
            for name, cb in self.circuit_breakers.items():
                cb.reset()
                logger.info(f"Reset circuit breaker: {name}")
    
    def reset_circuit_breaker(self, name: str) -> bool:
        """
        Reset a specific circuit breaker.
        
        Args:
            name: Circuit breaker name
            
        Returns:
            True if reset successfully, False if not found
        """
        with self.lock:
            if name in self.circuit_breakers:
                self.circuit_breakers[name].reset()
                logger.info(f"Reset circuit breaker: {name}")
                return True
            return False


# Global circuit breaker manager instance
_circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """
    Get a circuit breaker by name using the global manager.
    
    Args:
        name: Circuit breaker name
        **kwargs: Circuit breaker configuration parameters
        
    Returns:
        CircuitBreaker instance
    """
    return _circuit_breaker_manager.get_circuit_breaker(name, **kwargs)


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """
    Get the global circuit breaker manager.
    
    Returns:
        CircuitBreakerManager instance
    """
    return _circuit_breaker_manager
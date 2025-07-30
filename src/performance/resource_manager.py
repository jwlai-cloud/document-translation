"""Resource management and optimization for document translation."""

import threading
import time
import psutil
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager
from enum import Enum
import queue
import weakref


class ResourceType(Enum):
    """Types of system resources."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    THREADS = "threads"
    FILE_HANDLES = "file_handles"


@dataclass
class ResourceLimits:
    """Resource usage limits configuration."""
    max_cpu_percent: float = 80.0
    max_memory_mb: int = 2048
    max_memory_percent: float = 85.0
    max_threads: int = 50
    max_file_handles: int = 1000
    max_disk_io_mb_per_sec: float = 100.0
    max_network_io_mb_per_sec: float = 50.0
    
    # Soft limits (warnings)
    soft_cpu_percent: float = 60.0
    soft_memory_percent: float = 70.0
    soft_threads: int = 30


@dataclass
class ResourceUsage:
    """Current resource usage information."""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    threads_count: int = 0
    file_handles_count: int = 0
    disk_io_read_mb_per_sec: float = 0.0
    disk_io_write_mb_per_sec: float = 0.0
    network_io_sent_mb_per_sec: float = 0.0
    network_io_recv_mb_per_sec: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp,
            'cpu_percent': self.cpu_percent,
            'memory_mb': self.memory_mb,
            'memory_percent': self.memory_percent,
            'threads_count': self.threads_count,
            'file_handles_count': self.file_handles_count,
            'disk_io_read_mb_per_sec': self.disk_io_read_mb_per_sec,
            'disk_io_write_mb_per_sec': self.disk_io_write_mb_per_sec,
            'network_io_sent_mb_per_sec': self.network_io_sent_mb_per_sec,
            'network_io_recv_mb_per_sec': self.network_io_recv_mb_per_sec
        }


class ResourceManager:
    """Comprehensive resource management and throttling system."""
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        """Initialize resource manager.
        
        Args:
            limits: Resource limits configuration
        """
        self.limits = limits or ResourceLimits()
        self.logger = logging.getLogger(__name__)
        
        # Resource monitoring
        self.current_usage = ResourceUsage()
        self._usage_history: List[ResourceUsage] = []
        self._monitoring_thread = None
        self._shutdown_event = threading.Event()
        
        # Resource allocation tracking
        self._allocated_resources: Dict[str, Dict[ResourceType, float]] = {}
        self._resource_locks: Dict[ResourceType, threading.Semaphore] = {}
        self._allocation_lock = threading.Lock()
        
        # Throttling and queuing
        self._throttle_queues: Dict[ResourceType, queue.Queue] = {}
        self._throttle_active = False
        
        # Callbacks for resource events
        self._resource_callbacks: Dict[str, List[Callable]] = {
            'limit_exceeded': [],
            'resource_available': [],
            'throttle_activated': [],
            'throttle_deactivated': []
        }
        
        # Initialize resource locks
        self._initialize_resource_locks()
        
        # Start monitoring
        self.start_monitoring()
    
    def _initialize_resource_locks(self):
        """Initialize semaphores for resource types."""
        self._resource_locks = {
            ResourceType.CPU: threading.Semaphore(int(self.limits.max_cpu_percent)),
            ResourceType.MEMORY: threading.Semaphore(self.limits.max_memory_mb),
            ResourceType.THREADS: threading.Semaphore(self.limits.max_threads),
            ResourceType.FILE_HANDLES: threading.Semaphore(self.limits.max_file_handles),
            ResourceType.DISK_IO: threading.Semaphore(int(self.limits.max_disk_io_mb_per_sec)),
            ResourceType.NETWORK_IO: threading.Semaphore(int(self.limits.max_network_io_mb_per_sec))
        }
    
    def start_monitoring(self):
        """Start resource monitoring."""
        if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
            self._shutdown_event.clear()
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="resource_monitor"
            )
            self._monitoring_thread.start()
            self.logger.info("Resource monitoring started")
    
    def stop_monitoring(self):
        """Stop resource monitoring."""
        self._shutdown_event.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5.0)
        self.logger.info("Resource monitoring stopped")
    
    def _monitoring_loop(self):
        """Main resource monitoring loop."""
        last_io_stats = None
        
        while not self._shutdown_event.is_set():
            try:
                # Collect current usage
                usage = self._collect_resource_usage(last_io_stats)
                self.current_usage = usage
                
                # Store in history
                self._usage_history.append(usage)
                if len(self._usage_history) > 1000:  # Keep last 1000 samples
                    self._usage_history.pop(0)
                
                # Check limits and trigger actions
                self._check_resource_limits(usage)
                
                # Update last I/O stats for rate calculation
                try:
                    last_io_stats = psutil.disk_io_counters(), psutil.net_io_counters()
                except Exception:
                    pass
                
                # Sleep until next check
                self._shutdown_event.wait(5.0)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Resource monitoring error: {e}")
                time.sleep(10.0)
    
    def _collect_resource_usage(self, last_io_stats=None) -> ResourceUsage:
        """Collect current resource usage."""
        usage = ResourceUsage()
        
        try:
            # CPU usage
            usage.cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            usage.memory_mb = (memory.total - memory.available) / 1024 / 1024
            usage.memory_percent = memory.percent
            
            # Thread count
            usage.threads_count = threading.active_count()
            
            # File handles (approximate)
            try:
                process = psutil.Process()
                usage.file_handles_count = process.num_fds() if hasattr(process, 'num_fds') else 0
            except Exception:
                usage.file_handles_count = 0
            
            # I/O rates (if we have previous stats)
            if last_io_stats:
                try:
                    prev_disk, prev_net = last_io_stats
                    current_disk = psutil.disk_io_counters()
                    current_net = psutil.net_io_counters()
                    
                    if current_disk and prev_disk:
                        time_diff = 5.0  # 5 second interval
                        read_diff = current_disk.read_bytes - prev_disk.read_bytes
                        write_diff = current_disk.write_bytes - prev_disk.write_bytes
                        
                        usage.disk_io_read_mb_per_sec = (read_diff / time_diff) / 1024 / 1024
                        usage.disk_io_write_mb_per_sec = (write_diff / time_diff) / 1024 / 1024
                    
                    if current_net and prev_net:
                        time_diff = 5.0
                        sent_diff = current_net.bytes_sent - prev_net.bytes_sent
                        recv_diff = current_net.bytes_recv - prev_net.bytes_recv
                        
                        usage.network_io_sent_mb_per_sec = (sent_diff / time_diff) / 1024 / 1024
                        usage.network_io_recv_mb_per_sec = (recv_diff / time_diff) / 1024 / 1024
                
                except Exception as e:
                    self.logger.debug(f"I/O rate calculation error: {e}")
            
        except Exception as e:
            self.logger.error(f"Resource usage collection error: {e}")
        
        return usage
    
    def _check_resource_limits(self, usage: ResourceUsage):
        """Check resource usage against limits."""
        
        # Check CPU limit
        if usage.cpu_percent > self.limits.max_cpu_percent:
            self._trigger_limit_exceeded('cpu', usage.cpu_percent, self.limits.max_cpu_percent)
            self._activate_throttling(ResourceType.CPU)
        elif usage.cpu_percent < self.limits.soft_cpu_percent and self._throttle_active:
            self._deactivate_throttling(ResourceType.CPU)
        
        # Check memory limit
        if usage.memory_percent > self.limits.max_memory_percent:
            self._trigger_limit_exceeded('memory', usage.memory_percent, self.limits.max_memory_percent)
            self._activate_throttling(ResourceType.MEMORY)
        elif usage.memory_percent < self.limits.soft_memory_percent and self._throttle_active:
            self._deactivate_throttling(ResourceType.MEMORY)
        
        # Check thread limit
        if usage.threads_count > self.limits.max_threads:
            self._trigger_limit_exceeded('threads', usage.threads_count, self.limits.max_threads)
            self._activate_throttling(ResourceType.THREADS)
        elif usage.threads_count < self.limits.soft_threads and self._throttle_active:
            self._deactivate_throttling(ResourceType.THREADS)
        
        # Check disk I/O limit
        total_disk_io = usage.disk_io_read_mb_per_sec + usage.disk_io_write_mb_per_sec
        if total_disk_io > self.limits.max_disk_io_mb_per_sec:
            self._trigger_limit_exceeded('disk_io', total_disk_io, self.limits.max_disk_io_mb_per_sec)
            self._activate_throttling(ResourceType.DISK_IO)
    
    def _trigger_limit_exceeded(self, resource_name: str, current_value: float, limit: float):
        """Trigger limit exceeded event."""
        self.logger.warning(f"Resource limit exceeded: {resource_name} = {current_value:.2f}, limit = {limit:.2f}")
        
        for callback in self._resource_callbacks['limit_exceeded']:
            try:
                callback(resource_name, current_value, limit)
            except Exception as e:
                self.logger.error(f"Resource callback error: {e}")
    
    def _activate_throttling(self, resource_type: ResourceType):
        """Activate throttling for resource type."""
        if not self._throttle_active:
            self._throttle_active = True
            self.logger.warning(f"Throttling activated for {resource_type.value}")
            
            for callback in self._resource_callbacks['throttle_activated']:
                try:
                    callback(resource_type)
                except Exception as e:
                    self.logger.error(f"Throttle callback error: {e}")
    
    def _deactivate_throttling(self, resource_type: ResourceType):
        """Deactivate throttling for resource type."""
        if self._throttle_active:
            self._throttle_active = False
            self.logger.info(f"Throttling deactivated for {resource_type.value}")
            
            for callback in self._resource_callbacks['throttle_deactivated']:
                try:
                    callback(resource_type)
                except Exception as e:
                    self.logger.error(f"Throttle callback error: {e}")
    
    @contextmanager
    def allocate_resources(self, resource_id: str, requirements: Dict[ResourceType, float]):
        """Allocate resources for a task.
        
        Args:
            resource_id: Unique identifier for the resource allocation
            requirements: Dictionary of resource type to amount required
        """
        allocated = {}
        
        try:
            # Try to acquire all required resources
            for resource_type, amount in requirements.items():
                if resource_type in self._resource_locks:
                    # Wait for resource availability with timeout
                    if not self._resource_locks[resource_type].acquire(timeout=30.0):
                        raise ResourceError(f"Timeout waiting for {resource_type.value} resource")
                    allocated[resource_type] = amount
            
            # Track allocation
            with self._allocation_lock:
                self._allocated_resources[resource_id] = allocated.copy()
            
            self.logger.debug(f"Resources allocated for {resource_id}: {allocated}")
            yield
            
        finally:
            # Release all allocated resources
            for resource_type in allocated:
                if resource_type in self._resource_locks:
                    self._resource_locks[resource_type].release()
            
            # Remove from tracking
            with self._allocation_lock:
                self._allocated_resources.pop(resource_id, None)
            
            self.logger.debug(f"Resources released for {resource_id}")
    
    @contextmanager
    def memory_limit_context(self, limit_mb: int):
        """Context manager for temporary memory limit.
        
        Args:
            limit_mb: Memory limit in MB
        """
        original_limit = self.limits.max_memory_mb
        self.limits.max_memory_mb = limit_mb
        
        try:
            yield
        finally:
            self.limits.max_memory_mb = original_limit
    
    @contextmanager
    def cpu_limit_context(self, limit_percent: float):
        """Context manager for temporary CPU limit.
        
        Args:
            limit_percent: CPU limit percentage
        """
        original_limit = self.limits.max_cpu_percent
        self.limits.max_cpu_percent = limit_percent
        
        try:
            yield
        finally:
            self.limits.max_cpu_percent = original_limit
    
    def add_resource_callback(self, event_type: str, callback: Callable):
        """Add callback for resource events.
        
        Args:
            event_type: Type of event ('limit_exceeded', 'resource_available', etc.)
            callback: Callback function
        """
        if event_type in self._resource_callbacks:
            self._resource_callbacks[event_type].append(callback)
    
    def get_current_usage(self) -> ResourceUsage:
        """Get current resource usage."""
        return self.current_usage
    
    def get_usage_history(self, minutes: int = 60) -> List[ResourceUsage]:
        """Get resource usage history.
        
        Args:
            minutes: Number of minutes of history to return
            
        Returns:
            List of resource usage samples
        """
        cutoff_time = time.time() - (minutes * 60)
        return [usage for usage in self._usage_history if usage.timestamp >= cutoff_time]
    
    def get_resource_allocation_summary(self) -> Dict[str, Any]:
        """Get summary of current resource allocations."""
        with self._allocation_lock:
            return {
                'active_allocations': len(self._allocated_resources),
                'allocations': dict(self._allocated_resources),
                'throttle_active': self._throttle_active
            }
    
    def is_resource_available(self, resource_type: ResourceType, amount: float) -> bool:
        """Check if resource is available.
        
        Args:
            resource_type: Type of resource
            amount: Amount of resource needed
            
        Returns:
            True if resource is available
        """
        if resource_type == ResourceType.CPU:
            return self.current_usage.cpu_percent + amount <= self.limits.max_cpu_percent
        elif resource_type == ResourceType.MEMORY:
            return self.current_usage.memory_mb + amount <= self.limits.max_memory_mb
        elif resource_type == ResourceType.THREADS:
            return self.current_usage.threads_count + amount <= self.limits.max_threads
        else:
            return True  # Other resources are harder to predict
    
    def wait_for_resource_availability(self, resource_type: ResourceType, 
                                     amount: float, timeout: float = 60.0) -> bool:
        """Wait for resource to become available.
        
        Args:
            resource_type: Type of resource
            amount: Amount of resource needed
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if resource became available, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_resource_available(resource_type, amount):
                return True
            
            time.sleep(1.0)  # Check every second
        
        return False
    
    def optimize_for_large_task(self):
        """Optimize resource limits for large task processing."""
        # Temporarily increase limits
        self.limits.max_memory_mb = min(self.limits.max_memory_mb * 2, 4096)
        self.limits.max_cpu_percent = min(self.limits.max_cpu_percent * 1.2, 95.0)
        self.limits.max_threads = min(self.limits.max_threads * 2, 100)
        
        self.logger.info("Resource limits optimized for large task")
    
    def get_resource_recommendations(self) -> List[str]:
        """Get resource optimization recommendations."""
        recommendations = []
        usage = self.current_usage
        
        if usage.cpu_percent > self.limits.soft_cpu_percent:
            recommendations.append(f"High CPU usage ({usage.cpu_percent:.1f}%). Consider reducing concurrent operations.")
        
        if usage.memory_percent > self.limits.soft_memory_percent:
            recommendations.append(f"High memory usage ({usage.memory_percent:.1f}%). Consider enabling memory optimization.")
        
        if usage.threads_count > self.limits.soft_threads:
            recommendations.append(f"High thread count ({usage.threads_count}). Consider reducing concurrent tasks.")
        
        if not recommendations:
            recommendations.append("Resource usage is within optimal ranges.")
        
        return recommendations
    
    def shutdown(self):
        """Shutdown resource manager."""
        self.stop_monitoring()
        
        # Release all allocated resources
        with self._allocation_lock:
            for resource_id in list(self._allocated_resources.keys()):
                self.logger.warning(f"Force releasing resources for {resource_id}")
                del self._allocated_resources[resource_id]
        
        self.logger.info("Resource manager shutdown complete")


class ResourceError(Exception):
    """Exception raised when resource allocation fails."""
    pass


class ResourcePool:
    """Pool of reusable resources."""
    
    def __init__(self, resource_factory: Callable, max_size: int = 10):
        """Initialize resource pool.
        
        Args:
            resource_factory: Function to create new resources
            max_size: Maximum pool size
        """
        self.resource_factory = resource_factory
        self.max_size = max_size
        self.logger = logging.getLogger(__name__)
        
        self._pool: queue.Queue = queue.Queue(maxsize=max_size)
        self._created_count = 0
        self._pool_lock = threading.Lock()
    
    def acquire(self, timeout: Optional[float] = None) -> Any:
        """Acquire resource from pool.
        
        Args:
            timeout: Maximum time to wait for resource
            
        Returns:
            Resource object
        """
        try:
            # Try to get from pool first
            return self._pool.get_nowait()
        except queue.Empty:
            pass
        
        # Create new resource if pool is empty and we haven't hit limit
        with self._pool_lock:
            if self._created_count < self.max_size:
                resource = self.resource_factory()
                self._created_count += 1
                self.logger.debug(f"Created new resource (total: {self._created_count})")
                return resource
        
        # Wait for resource to become available
        if timeout is not None:
            try:
                return self._pool.get(timeout=timeout)
            except queue.Empty:
                raise ResourceError(f"Timeout waiting for resource from pool")
        else:
            return self._pool.get()
    
    def release(self, resource: Any):
        """Release resource back to pool.
        
        Args:
            resource: Resource to release
        """
        try:
            self._pool.put_nowait(resource)
        except queue.Full:
            # Pool is full, discard resource
            self.logger.debug("Pool full, discarding resource")
    
    def size(self) -> int:
        """Get current pool size."""
        return self._pool.qsize()
    
    def clear(self):
        """Clear all resources from pool."""
        while not self._pool.empty():
            try:
                self._pool.get_nowait()
            except queue.Empty:
                break
        
        with self._pool_lock:
            self._created_count = 0
        
        self.logger.info("Resource pool cleared")


# Context managers for resource management
@contextmanager
def managed_resources(limits: Optional[ResourceLimits] = None):
    """Context manager for managed resource usage."""
    manager = ResourceManager(limits)
    
    try:
        yield manager
    finally:
        manager.shutdown()


@contextmanager
def resource_limited_execution(cpu_limit: float = 80.0, memory_limit_mb: int = 2048):
    """Context manager for resource-limited execution."""
    limits = ResourceLimits(
        max_cpu_percent=cpu_limit,
        max_memory_mb=memory_limit_mb
    )
    
    with managed_resources(limits) as manager:
        yield manager
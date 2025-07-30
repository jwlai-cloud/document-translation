"""Memory optimization and management for document translation."""

import gc
import sys
import threading
import time
import weakref
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field
from contextlib import contextmanager
import psutil
import logging
from collections import defaultdict, OrderedDict


@dataclass
class MemoryConfig:
    """Configuration for memory optimization."""
    max_memory_mb: int = 2048  # Maximum memory usage in MB
    gc_threshold: float = 0.8  # Trigger GC when memory usage exceeds this ratio
    cache_size_limit: int = 100  # Maximum number of cached items
    cleanup_interval: int = 300  # Cleanup interval in seconds
    enable_monitoring: bool = True  # Enable memory monitoring
    log_memory_usage: bool = False  # Log memory usage details


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    current_usage_mb: float = 0.0
    peak_usage_mb: float = 0.0
    available_mb: float = 0.0
    gc_collections: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    objects_cleaned: int = 0
    last_cleanup_time: float = 0.0


class MemoryOptimizer:
    """Memory optimization and garbage collection manager."""
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        """Initialize memory optimizer.
        
        Args:
            config: Memory optimization configuration
        """
        self.config = config or MemoryConfig()
        self.logger = logging.getLogger(__name__)
        self.stats = MemoryStats()
        
        # Memory monitoring
        self._monitoring_thread = None
        self._shutdown_event = threading.Event()
        self._memory_callbacks: List[Callable[[float], None]] = []
        
        # Object tracking
        self._tracked_objects: Set[weakref.ref] = set()
        self._object_sizes: Dict[int, int] = {}
        
        if self.config.enable_monitoring:
            self._start_monitoring()
    
    def _start_monitoring(self):
        """Start memory monitoring thread."""
        self._monitoring_thread = threading.Thread(
            target=self._monitor_memory,
            daemon=True,
            name="memory_monitor"
        )
        self._monitoring_thread.start()
    
    def _monitor_memory(self):
        """Monitor memory usage and trigger optimizations."""
        while not self._shutdown_event.is_set():
            try:
                current_usage = self._get_memory_usage_mb()
                self.stats.current_usage_mb = current_usage
                
                if current_usage > self.stats.peak_usage_mb:
                    self.stats.peak_usage_mb = current_usage
                
                # Check if we need to trigger garbage collection
                memory_ratio = current_usage / self.config.max_memory_mb
                if memory_ratio > self.config.gc_threshold:
                    self.logger.warning(f"Memory usage high: {current_usage:.1f}MB ({memory_ratio:.1%})")
                    self.force_garbage_collection()
                
                # Notify callbacks
                for callback in self._memory_callbacks:
                    try:
                        callback(current_usage)
                    except Exception as e:
                        self.logger.error(f"Memory callback error: {e}")
                
                # Log memory usage if enabled
                if self.config.log_memory_usage:
                    self.logger.debug(f"Memory usage: {current_usage:.1f}MB")
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Memory monitoring error: {e}")
                time.sleep(10)  # Wait longer on error
    
    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def force_garbage_collection(self) -> int:
        """Force garbage collection and return number of objects collected."""
        try:
            # Run garbage collection
            collected = gc.collect()
            self.stats.gc_collections += 1
            
            if collected > 0:
                self.logger.info(f"Garbage collection freed {collected} objects")
            
            return collected
            
        except Exception as e:
            self.logger.error(f"Garbage collection failed: {e}")
            return 0
    
    def add_memory_callback(self, callback: Callable[[float], None]):
        """Add callback for memory usage notifications.
        
        Args:
            callback: Function to call with current memory usage (MB)
        """
        self._memory_callbacks.append(callback)
    
    def track_object(self, obj: Any) -> None:
        """Track object for memory monitoring.
        
        Args:
            obj: Object to track
        """
        try:
            obj_id = id(obj)
            obj_size = sys.getsizeof(obj)
            
            # Create weak reference
            weak_ref = weakref.ref(obj, self._object_cleanup_callback)
            self._tracked_objects.add(weak_ref)
            self._object_sizes[obj_id] = obj_size
            
        except Exception as e:
            self.logger.error(f"Object tracking failed: {e}")
    
    def _object_cleanup_callback(self, weak_ref: weakref.ref):
        """Callback when tracked object is garbage collected."""
        try:
            self._tracked_objects.discard(weak_ref)
            self.stats.objects_cleaned += 1
        except Exception:
            pass
    
    @contextmanager
    def memory_limit_context(self, limit_mb: int):
        """Context manager for temporary memory limit.
        
        Args:
            limit_mb: Temporary memory limit in MB
        """
        original_limit = self.config.max_memory_mb
        self.config.max_memory_mb = limit_mb
        
        try:
            yield
        finally:
            self.config.max_memory_mb = original_limit
    
    def optimize_for_large_document(self):
        """Optimize memory settings for large document processing."""
        # Increase memory limit temporarily
        self.config.max_memory_mb = min(self.config.max_memory_mb * 2, 4096)
        
        # Lower GC threshold for more aggressive cleanup
        self.config.gc_threshold = 0.7
        
        # Force immediate garbage collection
        self.force_garbage_collection()
        
        self.logger.info("Memory optimized for large document processing")
    
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        # Update current usage
        self.stats.current_usage_mb = self._get_memory_usage_mb()
        
        # Update available memory
        try:
            virtual_memory = psutil.virtual_memory()
            self.stats.available_mb = virtual_memory.available / 1024 / 1024
        except Exception:
            self.stats.available_mb = 0.0
        
        return self.stats
    
    def cleanup_resources(self):
        """Cleanup resources and optimize memory."""
        # Force garbage collection
        collected = self.force_garbage_collection()
        
        # Clear tracked objects
        self._tracked_objects.clear()
        self._object_sizes.clear()
        
        self.stats.last_cleanup_time = time.time()
        self.logger.info(f"Resource cleanup completed, freed {collected} objects")
    
    def shutdown(self):
        """Shutdown memory optimizer."""
        self._shutdown_event.set()
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5.0)
        
        self.cleanup_resources()


class MemoryManager:
    """Advanced memory management with caching and optimization."""
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        """Initialize memory manager.
        
        Args:
            config: Memory configuration
        """
        self.config = config or MemoryConfig()
        self.optimizer = MemoryOptimizer(config)
        self.logger = logging.getLogger(__name__)
        
        # Caching
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._cache_sizes: Dict[str, int] = {}
        self._cache_lock = threading.RLock()
        
        # Memory pools for reusable objects
        self._object_pools: Dict[str, List[Any]] = defaultdict(list)
        self._pool_lock = threading.Lock()
        
        # Cleanup scheduling
        self._last_cleanup = time.time()
        
        # Register memory callback
        self.optimizer.add_memory_callback(self._memory_pressure_callback)
    
    def cache_object(self, key: str, obj: Any, size_hint: Optional[int] = None) -> None:
        """Cache object with automatic size management.
        
        Args:
            key: Cache key
            obj: Object to cache
            size_hint: Optional size hint in bytes
        """
        with self._cache_lock:
            # Calculate object size
            obj_size = size_hint or sys.getsizeof(obj)
            
            # Check if we need to make room
            while (len(self._cache) >= self.config.cache_size_limit or 
                   self._get_total_cache_size() + obj_size > self.config.max_memory_mb * 1024 * 1024 * 0.1):
                
                if not self._cache:
                    break
                
                # Remove oldest item
                old_key, old_obj = self._cache.popitem(last=False)
                old_size = self._cache_sizes.pop(old_key, 0)
                
                self.logger.debug(f"Evicted cache item: {old_key} ({old_size} bytes)")
            
            # Add new item
            self._cache[key] = obj
            self._cache_sizes[key] = obj_size
            self.optimizer.stats.cache_misses += 1
    
    def get_cached_object(self, key: str) -> Optional[Any]:
        """Get object from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached object or None if not found
        """
        with self._cache_lock:
            if key in self._cache:
                # Move to end (most recently used)
                obj = self._cache.pop(key)
                self._cache[key] = obj
                self.optimizer.stats.cache_hits += 1
                return obj
            
            self.optimizer.stats.cache_misses += 1
            return None
    
    def _get_total_cache_size(self) -> int:
        """Get total cache size in bytes."""
        return sum(self._cache_sizes.values())
    
    def clear_cache(self):
        """Clear all cached objects."""
        with self._cache_lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            self._cache_sizes.clear()
            
            self.logger.info(f"Cleared {cleared_count} cached objects")
    
    def get_object_from_pool(self, pool_name: str, factory: Callable[[], Any]) -> Any:
        """Get object from pool or create new one.
        
        Args:
            pool_name: Name of object pool
            factory: Factory function to create new object
            
        Returns:
            Object from pool or newly created
        """
        with self._pool_lock:
            pool = self._object_pools[pool_name]
            
            if pool:
                return pool.pop()
            else:
                return factory()
    
    def return_object_to_pool(self, pool_name: str, obj: Any, reset_func: Optional[Callable[[Any], None]] = None):
        """Return object to pool for reuse.
        
        Args:
            pool_name: Name of object pool
            obj: Object to return
            reset_func: Optional function to reset object state
        """
        with self._pool_lock:
            pool = self._object_pools[pool_name]
            
            # Limit pool size
            if len(pool) < 10:  # Max 10 objects per pool
                if reset_func:
                    reset_func(obj)
                pool.append(obj)
    
    def _memory_pressure_callback(self, memory_usage_mb: float):
        """Handle memory pressure by cleaning up resources."""
        memory_ratio = memory_usage_mb / self.config.max_memory_mb
        
        if memory_ratio > 0.9:  # Very high memory usage
            self.logger.warning(f"High memory pressure: {memory_usage_mb:.1f}MB")
            
            # Aggressive cleanup
            self.clear_cache()
            self._clear_object_pools()
            self.optimizer.force_garbage_collection()
            
        elif memory_ratio > 0.8:  # Moderate memory pressure
            # Reduce cache size
            with self._cache_lock:
                target_size = len(self._cache) // 2
                while len(self._cache) > target_size:
                    self._cache.popitem(last=False)
    
    def _clear_object_pools(self):
        """Clear all object pools."""
        with self._pool_lock:
            cleared_pools = len(self._object_pools)
            total_objects = sum(len(pool) for pool in self._object_pools.values())
            
            self._object_pools.clear()
            
            self.logger.info(f"Cleared {cleared_pools} object pools with {total_objects} objects")
    
    @contextmanager
    def low_memory_mode(self):
        """Context manager for low memory processing mode."""
        # Save original settings
        original_cache_limit = self.config.cache_size_limit
        original_gc_threshold = self.config.gc_threshold
        
        try:
            # Enable low memory mode
            self.config.cache_size_limit = 10  # Reduce cache size
            self.config.gc_threshold = 0.6  # More aggressive GC
            
            # Clear current cache
            self.clear_cache()
            
            self.logger.info("Enabled low memory mode")
            yield
            
        finally:
            # Restore original settings
            self.config.cache_size_limit = original_cache_limit
            self.config.gc_threshold = original_gc_threshold
            
            self.logger.info("Disabled low memory mode")
    
    def schedule_cleanup(self):
        """Schedule periodic cleanup if needed."""
        current_time = time.time()
        
        if current_time - self._last_cleanup > self.config.cleanup_interval:
            self._perform_scheduled_cleanup()
            self._last_cleanup = current_time
    
    def _perform_scheduled_cleanup(self):
        """Perform scheduled cleanup operations."""
        self.logger.debug("Performing scheduled cleanup")
        
        # Clean up cache if it's getting large
        with self._cache_lock:
            if len(self._cache) > self.config.cache_size_limit * 0.8:
                # Remove 25% of oldest items
                remove_count = len(self._cache) // 4
                for _ in range(remove_count):
                    if self._cache:
                        self._cache.popitem(last=False)
        
        # Clean up object pools
        with self._pool_lock:
            for pool_name, pool in self._object_pools.items():
                if len(pool) > 5:  # Keep max 5 objects per pool
                    self._object_pools[pool_name] = pool[:5]
        
        # Force garbage collection if memory usage is high
        memory_usage = self.optimizer._get_memory_usage_mb()
        if memory_usage > self.config.max_memory_mb * 0.7:
            self.optimizer.force_garbage_collection()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._cache_lock:
            return {
                'cache_size': len(self._cache),
                'cache_limit': self.config.cache_size_limit,
                'total_cache_bytes': self._get_total_cache_size(),
                'cache_hits': self.optimizer.stats.cache_hits,
                'cache_misses': self.optimizer.stats.cache_misses,
                'hit_ratio': (self.optimizer.stats.cache_hits / 
                            max(self.optimizer.stats.cache_hits + self.optimizer.stats.cache_misses, 1))
            }
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get object pool statistics."""
        with self._pool_lock:
            return {
                'pool_count': len(self._object_pools),
                'total_pooled_objects': sum(len(pool) for pool in self._object_pools.values()),
                'pools': {name: len(pool) for name, pool in self._object_pools.items()}
            }
    
    def shutdown(self):
        """Shutdown memory manager."""
        self.clear_cache()
        self._clear_object_pools()
        self.optimizer.shutdown()


# Context managers for memory optimization
@contextmanager
def optimized_memory_context(config: Optional[MemoryConfig] = None):
    """Context manager for optimized memory usage."""
    manager = MemoryManager(config)
    
    try:
        yield manager
    finally:
        manager.shutdown()


@contextmanager
def large_document_memory_context():
    """Context manager optimized for large document processing."""
    config = MemoryConfig(
        max_memory_mb=4096,  # Allow more memory
        gc_threshold=0.7,    # More aggressive GC
        cache_size_limit=50, # Smaller cache
        cleanup_interval=60  # More frequent cleanup
    )
    
    with optimized_memory_context(config) as manager:
        manager.optimizer.optimize_for_large_document()
        yield manager
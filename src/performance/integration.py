"""Integration of performance optimization components with the translation system."""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .concurrent_processor import ConcurrentDocumentProcessor, ProcessingConfig
from .memory_optimizer import MemoryManager, MemoryConfig
from .performance_monitor import PerformanceMonitor, PerformanceAlerter
from .cache_manager import MultiLevelCache, CacheConfig, DocumentCache, TranslationCache
from .resource_manager import ResourceManager, ResourceLimits


@dataclass
class PerformanceOptimizationConfig:
    """Configuration for integrated performance optimization."""
    
    # Concurrent processing
    max_workers: int = 4
    chunk_size: int = 10
    enable_process_pool: bool = False
    
    # Memory management
    max_memory_mb: int = 2048
    memory_gc_threshold: float = 0.8
    cache_size_limit: int = 100
    
    # Performance monitoring
    monitoring_interval: int = 5
    enable_alerts: bool = True
    
    # Resource limits
    max_cpu_percent: float = 80.0
    max_threads: int = 50
    
    # Caching
    enable_document_cache: bool = True
    enable_translation_cache: bool = True
    document_cache_size: int = 20
    translation_cache_size: int = 500


class PerformanceOptimizedSystem:
    """Integrated performance optimization system for document translation."""
    
    def __init__(self, config: Optional[PerformanceOptimizationConfig] = None):
        """Initialize performance optimization system.
        
        Args:
            config: Performance optimization configuration
        """
        self.config = config or PerformanceOptimizationConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self._initialize_components()
        
        # Setup integration
        self._setup_integration()
        
        self.logger.info("Performance optimization system initialized")
    
    def _initialize_components(self):
        """Initialize all performance components."""
        
        # Concurrent processing
        processing_config = ProcessingConfig(
            max_workers=self.config.max_workers,
            chunk_size=self.config.chunk_size,
            use_process_pool=self.config.enable_process_pool
        )
        self.concurrent_processor = ConcurrentDocumentProcessor(processing_config)
        
        # Memory management
        memory_config = MemoryConfig(
            max_memory_mb=self.config.max_memory_mb,
            gc_threshold=self.config.memory_gc_threshold,
            cache_size_limit=self.config.cache_size_limit,
            enable_monitoring=True
        )
        self.memory_manager = MemoryManager(memory_config)
        
        # Performance monitoring
        self.performance_monitor = PerformanceMonitor(
            collection_interval=self.config.monitoring_interval
        )
        
        if self.config.enable_alerts:
            self.performance_alerter = PerformanceAlerter(self.performance_monitor)
            self._setup_alert_channels()
        
        # Resource management
        resource_limits = ResourceLimits(
            max_cpu_percent=self.config.max_cpu_percent,
            max_memory_mb=self.config.max_memory_mb,
            max_threads=self.config.max_threads
        )
        self.resource_manager = ResourceManager(resource_limits)
        
        # Caching system
        self._setup_caching()
    
    def _setup_caching(self):
        """Setup multi-level caching system."""
        
        # L1 cache (fast, small)
        l1_config = CacheConfig(
            max_size=50,
            max_memory_mb=128,
            default_ttl=1800  # 30 minutes
        )
        
        # L2 cache (larger, persistent)
        l2_config = CacheConfig(
            max_size=200,
            max_memory_mb=512,
            default_ttl=7200,  # 2 hours
            persistence_file="translation_cache_l2.pkl"
        )
        
        self.multi_level_cache = MultiLevelCache(l1_config, l2_config)
        
        # Specialized caches
        if self.config.enable_document_cache:
            self.document_cache = DocumentCache()
        
        if self.config.enable_translation_cache:
            self.translation_cache = TranslationCache()
    
    def _setup_integration(self):
        """Setup integration between components."""
        
        # Memory pressure callback
        def memory_pressure_callback(memory_usage_mb: float):
            """Handle memory pressure by optimizing caches."""
            memory_ratio = memory_usage_mb / self.config.max_memory_mb
            
            if memory_ratio > 0.9:
                self.logger.warning(f"High memory pressure: {memory_usage_mb:.1f}MB")
                
                # Clear caches to free memory
                if hasattr(self, 'multi_level_cache'):
                    self.multi_level_cache.l1_cache.clear()
                
                if hasattr(self, 'document_cache'):
                    self.document_cache.clear()
                
                # Force garbage collection
                self.memory_manager.optimizer.force_garbage_collection()
        
        self.memory_manager.optimizer.add_memory_callback(memory_pressure_callback)
        
        # Resource limit callbacks
        def resource_limit_callback(resource_name: str, current_value: float, limit: float):
            """Handle resource limit exceeded."""
            self.logger.warning(f"Resource limit exceeded: {resource_name}")
            
            if resource_name == 'memory':
                # Enable low memory mode
                self.memory_manager.low_memory_mode().__enter__()
            elif resource_name == 'cpu':
                # Reduce concurrent processing
                if hasattr(self.concurrent_processor, 'config'):
                    self.concurrent_processor.config.max_workers = max(1, 
                        self.concurrent_processor.config.max_workers - 1)
        
        self.resource_manager.add_resource_callback('limit_exceeded', resource_limit_callback)
    
    def _setup_alert_channels(self):
        """Setup alert notification channels."""
        
        def log_alert_channel(alert):
            """Log alert to system logger."""
            level = logging.WARNING if alert.level == 'warning' else logging.ERROR
            self.logger.log(level, f"Performance Alert: {alert.message}")
        
        self.performance_alerter.add_notification_channel(log_alert_channel)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system performance status."""
        
        status = {
            'timestamp': self.performance_monitor.get_current_metrics().timestamp,
            'performance': {
                'current_metrics': self.performance_monitor.get_current_metrics().to_dict(),
                'active_alerts': len(self.performance_monitor.get_active_alerts()),
                'summary': self.performance_monitor.get_performance_summary()
            },
            'memory': {
                'stats': self.memory_manager.optimizer.get_memory_stats().__dict__,
                'cache_stats': self.memory_manager.get_cache_stats(),
                'pool_stats': self.memory_manager.get_pool_stats()
            },
            'resources': {
                'current_usage': self.resource_manager.get_current_usage().to_dict(),
                'allocation_summary': self.resource_manager.get_resource_allocation_summary(),
                'recommendations': self.resource_manager.get_resource_recommendations()
            },
            'processing': {
                'metrics': self.concurrent_processor.get_performance_metrics().__dict__
            }
        }
        
        # Add cache statistics if available
        if hasattr(self, 'multi_level_cache'):
            status['caching'] = {
                'multi_level': self.multi_level_cache.get_stats()
            }
        
        if hasattr(self, 'document_cache'):
            status['caching']['document_cache'] = self.document_cache.get_stats().__dict__
        
        if hasattr(self, 'translation_cache'):
            status['caching']['translation_cache'] = self.translation_cache.get_stats().__dict__
        
        return status
    
    def optimize_for_large_document(self):
        """Optimize system for large document processing."""
        
        self.logger.info("Optimizing system for large document processing")
        
        # Optimize memory settings
        self.memory_manager.optimizer.optimize_for_large_document()
        
        # Optimize resource limits
        self.resource_manager.optimize_for_large_task()
        
        # Clear caches to free memory
        if hasattr(self, 'multi_level_cache'):
            self.multi_level_cache.l1_cache.clear()
        
        # Reduce concurrent processing to save memory
        if self.concurrent_processor.config.max_workers > 2:
            self.concurrent_processor.config.max_workers = 2
    
    def optimize_for_high_throughput(self):
        """Optimize system for high throughput processing."""
        
        self.logger.info("Optimizing system for high throughput processing")
        
        # Increase concurrent processing
        self.concurrent_processor.config.max_workers = min(
            self.concurrent_processor.config.max_workers * 2,
            self.config.max_threads
        )
        
        # Optimize caching for throughput
        if hasattr(self, 'multi_level_cache'):
            # Increase L1 cache size
            self.multi_level_cache.l1_cache.config.max_size *= 2
        
        # Adjust memory settings for higher throughput
        self.memory_manager.optimizer.config.gc_threshold = 0.9  # Less aggressive GC
    
    def get_optimization_recommendations(self) -> Dict[str, Any]:
        """Get system optimization recommendations."""
        
        recommendations = {
            'memory': [],
            'cpu': [],
            'caching': [],
            'processing': [],
            'general': []
        }
        
        # Get current metrics
        current_metrics = self.performance_monitor.get_current_metrics()
        memory_stats = self.memory_manager.optimizer.get_memory_stats()
        resource_usage = self.resource_manager.get_current_usage()
        
        # Memory recommendations
        if memory_stats.current_usage_mb > self.config.max_memory_mb * 0.8:
            recommendations['memory'].append("High memory usage detected. Consider enabling low memory mode.")
        
        if memory_stats.cache_hits > 0 and memory_stats.cache_misses > 0:
            hit_ratio = memory_stats.cache_hits / (memory_stats.cache_hits + memory_stats.cache_misses)
            if hit_ratio < 0.7:
                recommendations['caching'].append("Low cache hit ratio. Consider increasing cache size.")
        
        # CPU recommendations
        if current_metrics.cpu_usage_percent > self.config.max_cpu_percent * 0.8:
            recommendations['cpu'].append("High CPU usage. Consider reducing concurrent processing.")
        
        # Processing recommendations
        processing_metrics = self.concurrent_processor.get_performance_metrics()
        if processing_metrics.failed_items > 0:
            failure_rate = processing_metrics.failed_items / max(processing_metrics.total_items, 1)
            if failure_rate > 0.1:
                recommendations['processing'].append("High processing failure rate. Check error logs.")
        
        # General recommendations
        if current_metrics.response_time_ms > 10000:  # 10 seconds
            recommendations['general'].append("High response times detected. Consider system optimization.")
        
        # Add resource manager recommendations
        recommendations['general'].extend(self.resource_manager.get_resource_recommendations())
        
        return recommendations
    
    def export_performance_report(self, filename: str):
        """Export comprehensive performance report."""
        
        report_data = {
            'system_status': self.get_system_status(),
            'optimization_recommendations': self.get_optimization_recommendations(),
            'configuration': {
                'performance_config': self.config.__dict__,
                'processing_config': self.concurrent_processor.config.__dict__,
                'memory_config': self.memory_manager.config.__dict__,
                'resource_limits': self.resource_manager.limits.__dict__
            }
        }
        
        # Export performance metrics
        self.performance_monitor.export_metrics(f"{filename}_metrics.json")
        
        # Export main report
        import json
        with open(f"{filename}_report.json", 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        self.logger.info(f"Performance report exported to {filename}")
    
    def shutdown(self):
        """Shutdown all performance optimization components."""
        
        self.logger.info("Shutting down performance optimization system")
        
        # Shutdown components in reverse order
        if hasattr(self, 'translation_cache'):
            self.translation_cache.shutdown()
        
        if hasattr(self, 'document_cache'):
            self.document_cache.shutdown()
        
        if hasattr(self, 'multi_level_cache'):
            self.multi_level_cache.shutdown()
        
        self.resource_manager.shutdown()
        self.performance_monitor.shutdown()
        self.memory_manager.shutdown()
        self.concurrent_processor.shutdown()
        
        self.logger.info("Performance optimization system shutdown complete")


# Global performance optimization instance
_performance_system: Optional[PerformanceOptimizedSystem] = None


def get_performance_system(config: Optional[PerformanceOptimizationConfig] = None) -> PerformanceOptimizedSystem:
    """Get or create global performance optimization system."""
    global _performance_system
    
    if _performance_system is None:
        _performance_system = PerformanceOptimizedSystem(config)
    
    return _performance_system


def shutdown_performance_system():
    """Shutdown global performance optimization system."""
    global _performance_system
    
    if _performance_system is not None:
        _performance_system.shutdown()
        _performance_system = None


# Context manager for performance optimization
class PerformanceOptimizationContext:
    """Context manager for performance-optimized operations."""
    
    def __init__(self, config: Optional[PerformanceOptimizationConfig] = None):
        """Initialize performance optimization context."""
        self.config = config
        self.system = None
    
    def __enter__(self) -> PerformanceOptimizedSystem:
        """Enter performance optimization context."""
        self.system = PerformanceOptimizedSystem(self.config)
        return self.system
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit performance optimization context."""
        if self.system:
            self.system.shutdown()


# Decorator for performance monitoring
def monitor_performance(operation_name: str):
    """Decorator to monitor performance of operations."""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            system = get_performance_system()
            
            with system.performance_monitor.PerformanceContext(system.performance_monitor, operation_name):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator
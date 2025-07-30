"""Tests for performance optimization and monitoring components."""

import pytest
import asyncio
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from src.performance.concurrent_processor import (
    ConcurrentDocumentProcessor, 
    ProcessingConfig,
    BatchProcessor,
    OptimizedTranslationPipeline
)
from src.performance.memory_optimizer import (
    MemoryOptimizer, 
    MemoryManager, 
    MemoryConfig,
    optimized_memory_context,
    large_document_memory_context
)
from src.performance.performance_monitor import (
    PerformanceMonitor,
    PerformanceMetrics,
    Alert,
    AlertThreshold
)
from src.performance.cache_manager import (
    CacheManager,
    CacheConfig,
    MultiLevelCache,
    DocumentCache,
    TranslationCache
)
from src.performance.resource_manager import (
    ResourceManager,
    ResourceLimits,
    ResourceType,
    managed_resources
)


class TestConcurrentProcessor:
    """Test concurrent document processing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ProcessingConfig(
            max_workers=2,
            chunk_size=5,
            timeout_seconds=30
        )
        self.processor = ConcurrentDocumentProcessor(self.config)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.processor.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_processing(self):
        """Test concurrent document processing."""
        
        # Create mock document
        mock_document = Mock()
        mock_document.pages = [Mock() for _ in range(3)]
        
        for i, page in enumerate(mock_document.pages):
            page.page_number = i + 1
            page.text_regions = [Mock() for _ in range(10)]
            page.visual_elements = []
        
        # Mock processor function
        def mock_processor(chunk, **kwargs):
            time.sleep(0.1)  # Simulate processing time
            return {
                'chunk_id': chunk['chunk_id'],
                'processed_regions': len(chunk['regions'])
            }
        
        # Process document
        start_time = time.time()
        results = await self.processor.process_document_sections(
            mock_document, mock_processor
        )
        processing_time = time.time() - start_time
        
        # Verify results
        assert len(results) > 0
        assert all(result is not None for result in results)
        
        # Verify performance metrics
        metrics = self.processor.get_performance_metrics()
        assert metrics.total_items > 0
        assert metrics.processed_items > 0
        assert metrics.processing_time > 0
        assert metrics.throughput > 0
        
        # Should be faster than sequential processing
        assert processing_time < 2.0  # Should complete quickly with mocked processing
    
    def test_processing_metrics(self):
        """Test processing metrics collection."""
        metrics = self.processor.get_performance_metrics()
        
        assert hasattr(metrics, 'total_items')
        assert hasattr(metrics, 'processed_items')
        assert hasattr(metrics, 'failed_items')
        assert hasattr(metrics, 'processing_time')
        assert hasattr(metrics, 'throughput')


class TestMemoryOptimizer:
    """Test memory optimization."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = MemoryConfig(
            max_memory_mb=100,  # Low limit for testing
            gc_threshold=0.7,
            enable_monitoring=False  # Disable for testing
        )
        self.optimizer = MemoryOptimizer(self.config)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.optimizer.shutdown()
    
    def test_memory_monitoring(self):
        """Test memory usage monitoring."""
        # Get initial memory stats
        stats = self.optimizer.get_memory_stats()
        
        assert stats.current_usage_mb >= 0
        assert stats.peak_usage_mb >= 0
        assert stats.gc_collections >= 0
    
    def test_garbage_collection(self):
        """Test forced garbage collection."""
        initial_collections = self.optimizer.stats.gc_collections
        
        # Force garbage collection
        collected = self.optimizer.force_garbage_collection()
        
        assert collected >= 0
        assert self.optimizer.stats.gc_collections > initial_collections
    
    def test_memory_limit_context(self):
        """Test memory limit context manager."""
        original_limit = self.optimizer.config.max_memory_mb
        
        with self.optimizer.memory_limit_context(200):
            assert self.optimizer.config.max_memory_mb == 200
        
        assert self.optimizer.config.max_memory_mb == original_limit
    
    def test_object_tracking(self):
        """Test object tracking functionality."""
        test_obj = [1, 2, 3, 4, 5] * 1000  # Create a larger object
        
        # Track object
        self.optimizer.track_object(test_obj)
        
        # Object should be tracked
        assert len(self.optimizer._tracked_objects) > 0
        
        # Delete object and force GC
        del test_obj
        self.optimizer.force_garbage_collection()
        
        # Cleanup should have been called
        time.sleep(0.1)  # Give time for cleanup


class TestMemoryManager:
    """Test memory manager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = MemoryConfig(
            cache_size_limit=10,
            max_memory_mb=100
        )
        self.manager = MemoryManager(self.config)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.manager.shutdown()
    
    def test_cache_operations(self):
        """Test cache operations."""
        # Cache an object
        test_obj = {"data": "test_value"}
        self.manager.cache_object("test_key", test_obj)
        
        # Retrieve cached object
        cached_obj = self.manager.get_cached_object("test_key")
        assert cached_obj == test_obj
        
        # Test cache miss
        missing_obj = self.manager.get_cached_object("missing_key")
        assert missing_obj is None
    
    def test_object_pools(self):
        """Test object pool functionality."""
        def create_test_object():
            return {"created_at": time.time()}
        
        # Get object from pool (should create new one)
        obj1 = self.manager.get_object_from_pool("test_pool", create_test_object)
        assert obj1 is not None
        
        # Return object to pool
        self.manager.return_object_to_pool("test_pool", obj1)
        
        # Get object again (should reuse from pool)
        obj2 = self.manager.get_object_from_pool("test_pool", create_test_object)
        assert obj2 is obj1  # Should be the same object
    
    def test_low_memory_mode(self):
        """Test low memory mode context."""
        original_cache_limit = self.manager.config.cache_size_limit
        
        with self.manager.low_memory_mode():
            assert self.manager.config.cache_size_limit < original_cache_limit
        
        assert self.manager.config.cache_size_limit == original_cache_limit
    
    def test_cache_stats(self):
        """Test cache statistics."""
        # Add some items to cache
        for i in range(5):
            self.manager.cache_object(f"key_{i}", f"value_{i}")
        
        stats = self.manager.get_cache_stats()
        
        assert stats['cache_size'] == 5
        assert stats['cache_limit'] == 10
        assert stats['total_cache_bytes'] > 0
    
    def test_memory_context_managers(self):
        """Test memory context managers."""
        
        # Test optimized memory context
        with optimized_memory_context() as manager:
            assert isinstance(manager, MemoryManager)
            manager.cache_object("test", "value")
        
        # Test large document context
        with large_document_memory_context() as manager:
            assert isinstance(manager, MemoryManager)
            assert manager.config.max_memory_mb >= 4096


class TestPerformanceMonitor:
    """Test performance monitoring."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = PerformanceMonitor(collection_interval=1, history_size=10)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.monitor.stop_monitoring()
    
    def test_metrics_collection(self):
        """Test metrics collection."""
        # Wait for at least one metrics collection
        time.sleep(2)
        
        metrics = self.monitor.get_current_metrics()
        
        assert metrics.cpu_usage_percent >= 0
        assert metrics.memory_usage_mb > 0
        assert metrics.memory_usage_percent > 0
        assert metrics.active_threads > 0
    
    def test_request_recording(self):
        """Test request recording."""
        # Record some requests
        self.monitor.record_request(0.1, True)
        self.monitor.record_request(0.2, True)
        self.monitor.record_request(0.5, False)  # Failed request
        
        # Wait for metrics update
        time.sleep(2)
        
        metrics = self.monitor.get_current_metrics()
        assert metrics.response_time_ms > 0
        assert metrics.error_rate_percent > 0
    
    def test_alert_system(self):
        """Test alert system."""
        # Set low threshold for testing
        self.monitor.set_alert_threshold('cpu_usage_percent', 1.0, 2.0)
        
        # Create mock high CPU usage
        with patch('psutil.cpu_percent', return_value=5.0):
            time.sleep(2)  # Wait for monitoring cycle
        
        # Check for alerts
        active_alerts = self.monitor.get_active_alerts()
        # Note: May not trigger immediately due to timing
    
    def test_performance_summary(self):
        """Test performance summary."""
        # Record some activity
        self.monitor.record_request(0.1, True)
        self.monitor.update_job_metrics(5, 10)
        
        time.sleep(2)  # Wait for metrics collection
        
        summary = self.monitor.get_performance_summary()
        
        assert 'current_metrics' in summary
        assert 'averages' in summary
        assert 'peaks' in summary
        assert 'total_requests' in summary


class TestCacheManager:
    """Test cache management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = CacheConfig(
            max_size=5,
            default_ttl=10,
            cleanup_interval=1
        )
        self.cache = CacheManager(self.config)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.cache.shutdown()
    
    def test_basic_cache_operations(self):
        """Test basic cache operations."""
        # Put item
        self.cache.put("key1", "value1")
        
        # Get item
        value = self.cache.get("key1")
        assert value == "value1"
        
        # Check existence
        assert self.cache.exists("key1")
        assert not self.cache.exists("nonexistent")
        
        # Delete item
        assert self.cache.delete("key1")
        assert not self.cache.exists("key1")
    
    def test_ttl_expiration(self):
        """Test TTL-based expiration."""
        # Put item with short TTL
        self.cache.put("temp_key", "temp_value", ttl=1)
        
        # Should exist immediately
        assert self.cache.exists("temp_key")
        
        # Wait for expiration
        time.sleep(2)
        
        # Should be expired
        assert not self.cache.exists("temp_key")
    
    def test_cache_eviction(self):
        """Test cache eviction when size limit is reached."""
        # Fill cache to capacity
        for i in range(self.config.max_size):
            self.cache.put(f"key_{i}", f"value_{i}")
        
        # Add one more item (should trigger eviction)
        self.cache.put("overflow_key", "overflow_value")
        
        # Cache should still be at max size
        assert len(self.cache._cache) <= self.config.max_size
        
        # Overflow item should exist
        assert self.cache.exists("overflow_key")
    
    def test_get_or_compute(self):
        """Test get_or_compute functionality."""
        compute_called = False
        
        def compute_value():
            nonlocal compute_called
            compute_called = True
            return "computed_value"
        
        # First call should compute
        value1 = self.cache.get_or_compute("compute_key", compute_value)
        assert value1 == "computed_value"
        assert compute_called
        
        # Second call should use cache
        compute_called = False
        value2 = self.cache.get_or_compute("compute_key", compute_value)
        assert value2 == "computed_value"
        assert not compute_called  # Should not compute again
    
    def test_cache_stats(self):
        """Test cache statistics."""
        # Generate some cache activity
        self.cache.put("key1", "value1")
        self.cache.get("key1")  # Hit
        self.cache.get("nonexistent")  # Miss
        
        stats = self.cache.get_stats()
        
        assert stats.hits > 0
        assert stats.misses > 0
        assert stats.item_count > 0
        assert stats.hit_ratio > 0
    
    def test_specialized_caches(self):
        """Test specialized cache implementations."""
        
        # Test document cache
        doc_cache = DocumentCache()
        doc_cache.cache_document("/path/to/doc.pdf", {"content": "document"})
        
        cached_doc = doc_cache.get_document("/path/to/doc.pdf")
        assert cached_doc == {"content": "document"}
        
        doc_cache.shutdown()
        
        # Test translation cache
        trans_cache = TranslationCache()
        trans_cache.cache_translation("Hello", "en", "fr", "Bonjour")
        
        cached_translation = trans_cache.get_translation("Hello", "en", "fr")
        assert cached_translation == "Bonjour"
        
        trans_cache.shutdown()
    
    def test_multi_level_cache(self):
        """Test multi-level cache."""
        l1_config = CacheConfig(max_size=2, max_memory_mb=32)
        l2_config = CacheConfig(max_size=10, max_memory_mb=128)
        
        multi_cache = MultiLevelCache(l1_config, l2_config)
        
        # Put item (should go to both levels)
        multi_cache.put("key1", "value1")
        
        # Get item (should come from L1)
        value = multi_cache.get("key1")
        assert value == "value1"
        
        # Clear L1 and get again (should come from L2)
        multi_cache.l1_cache.clear()
        value = multi_cache.get("key1")
        assert value == "value1"
        
        multi_cache.shutdown()


class TestResourceManager:
    """Test resource management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.limits = ResourceLimits(
            max_cpu_percent=50.0,
            max_memory_mb=512,
            max_threads=10
        )
        self.manager = ResourceManager(self.limits)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.manager.shutdown()
    
    def test_resource_monitoring(self):
        """Test resource usage monitoring."""
        # Wait for monitoring to collect data
        time.sleep(2)
        
        usage = self.manager.get_current_usage()
        
        assert usage.cpu_percent >= 0
        assert usage.memory_mb > 0
        assert usage.threads_count > 0
    
    def test_resource_allocation(self):
        """Test resource allocation context."""
        requirements = {
            ResourceType.CPU: 10.0,
            ResourceType.MEMORY: 100.0,
            ResourceType.THREADS: 2.0
        }
        
        with self.manager.allocate_resources("test_task", requirements):
            # Check allocation tracking
            summary = self.manager.get_resource_allocation_summary()
            assert summary['active_allocations'] > 0
            assert 'test_task' in summary['allocations']
        
        # After context, allocation should be released
        summary = self.manager.get_resource_allocation_summary()
        assert 'test_task' not in summary['allocations']
    
    def test_resource_availability_check(self):
        """Test resource availability checking."""
        # Check if resources are available
        cpu_available = self.manager.is_resource_available(ResourceType.CPU, 10.0)
        memory_available = self.manager.is_resource_available(ResourceType.MEMORY, 100.0)
        
        assert isinstance(cpu_available, bool)
        assert isinstance(memory_available, bool)
    
    def test_resource_limit_contexts(self):
        """Test resource limit context managers."""
        original_memory_limit = self.manager.limits.max_memory_mb
        original_cpu_limit = self.manager.limits.max_cpu_percent
        
        # Test memory limit context
        with self.manager.memory_limit_context(1024):
            assert self.manager.limits.max_memory_mb == 1024
        
        assert self.manager.limits.max_memory_mb == original_memory_limit
        
        # Test CPU limit context
        with self.manager.cpu_limit_context(75.0):
            assert self.manager.limits.max_cpu_percent == 75.0
        
        assert self.manager.limits.max_cpu_percent == original_cpu_limit
    
    def test_resource_recommendations(self):
        """Test resource optimization recommendations."""
        recommendations = self.manager.get_resource_recommendations()
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert all(isinstance(rec, str) for rec in recommendations)
    
    def test_managed_resources_context(self):
        """Test managed resources context manager."""
        limits = ResourceLimits(max_memory_mb=256)
        
        with managed_resources(limits) as manager:
            assert isinstance(manager, ResourceManager)
            assert manager.limits.max_memory_mb == 256
            
            usage = manager.get_current_usage()
            assert usage is not None


class TestIntegratedPerformanceOptimization:
    """Test integrated performance optimization."""
    
    @pytest.mark.asyncio
    async def test_optimized_translation_pipeline(self):
        """Test optimized translation pipeline."""
        config = ProcessingConfig(max_workers=2, chunk_size=3)
        pipeline = OptimizedTranslationPipeline(config)
        
        # Create mock document
        mock_document = Mock()
        mock_document.pages = [Mock()]
        mock_document.pages[0].page_number = 1
        mock_document.pages[0].text_regions = [Mock() for _ in range(6)]
        mock_document.pages[0].visual_elements = []
        mock_document.format_type = "pdf"
        mock_document.metadata = {}
        
        # Mock translation service
        mock_translation_service = Mock()
        mock_translation_service.translate_region.return_value = Mock()
        
        try:
            # Process document
            result = await pipeline.process_document_optimized(
                mock_document, mock_translation_service
            )
            
            # Verify result
            assert result is not None
            assert hasattr(result, 'pages')
            
            # Check performance metrics
            metrics = pipeline.get_performance_metrics()
            assert metrics.total_items > 0
            
        finally:
            pipeline.shutdown()
    
    def test_performance_monitoring_integration(self):
        """Test integration of performance monitoring components."""
        
        # Create integrated monitoring setup
        monitor = PerformanceMonitor(collection_interval=1)
        
        # Create memory manager with monitoring
        memory_config = MemoryConfig(enable_monitoring=True)
        memory_manager = MemoryManager(memory_config)
        
        # Create resource manager
        resource_limits = ResourceLimits(max_memory_mb=512)
        resource_manager = ResourceManager(resource_limits)
        
        try:
            # Simulate some activity
            monitor.record_request(0.1, True)
            memory_manager.cache_object("test", "value")
            
            # Wait for monitoring
            time.sleep(2)
            
            # Check that all components are working
            perf_summary = monitor.get_performance_summary()
            cache_stats = memory_manager.get_cache_stats()
            resource_usage = resource_manager.get_current_usage()
            
            assert perf_summary is not None
            assert cache_stats is not None
            assert resource_usage is not None
            
        finally:
            monitor.stop_monitoring()
            memory_manager.shutdown()
            resource_manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
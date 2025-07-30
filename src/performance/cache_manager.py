"""Advanced caching system for performance optimization."""

import time
import threading
import hashlib
import pickle
import json
from typing import Any, Dict, Optional, Callable, Union, List, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
from abc import ABC, abstractmethod
import logging
import weakref


@dataclass
class CacheConfig:
    """Configuration for cache management."""
    max_size: int = 1000  # Maximum number of cached items
    max_memory_mb: int = 512  # Maximum memory usage in MB
    default_ttl: int = 3600  # Default time-to-live in seconds
    cleanup_interval: int = 300  # Cleanup interval in seconds
    enable_stats: bool = True  # Enable cache statistics
    enable_compression: bool = False  # Enable value compression
    persistence_file: Optional[str] = None  # File for cache persistence


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired_items: int = 0
    memory_usage_mb: float = 0.0
    item_count: int = 0
    
    @property
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


@dataclass
class CacheItem:
    """Cache item with metadata."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    ttl: Optional[int] = None
    size_bytes: int = 0
    access_count: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if item is expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    @property
    def age_seconds(self) -> float:
        """Get item age in seconds."""
        return time.time() - self.created_at


class CacheEvictionPolicy(ABC):
    """Abstract base class for cache eviction policies."""
    
    @abstractmethod
    def select_eviction_candidates(self, items: Dict[str, CacheItem], count: int) -> List[str]:
        """Select items for eviction.
        
        Args:
            items: Dictionary of cache items
            count: Number of items to evict
            
        Returns:
            List of keys to evict
        """
        pass


class LRUEvictionPolicy(CacheEvictionPolicy):
    """Least Recently Used eviction policy."""
    
    def select_eviction_candidates(self, items: Dict[str, CacheItem], count: int) -> List[str]:
        """Select LRU items for eviction."""
        # Sort by access time (oldest first)
        sorted_items = sorted(items.items(), key=lambda x: x[1].accessed_at)
        return [key for key, _ in sorted_items[:count]]


class LFUEvictionPolicy(CacheEvictionPolicy):
    """Least Frequently Used eviction policy."""
    
    def select_eviction_candidates(self, items: Dict[str, CacheItem], count: int) -> List[str]:
        """Select LFU items for eviction."""
        # Sort by access count (lowest first)
        sorted_items = sorted(items.items(), key=lambda x: x[1].access_count)
        return [key for key, _ in sorted_items[:count]]


class TTLEvictionPolicy(CacheEvictionPolicy):
    """Time-to-Live based eviction policy."""
    
    def select_eviction_candidates(self, items: Dict[str, CacheItem], count: int) -> List[str]:
        """Select expired items for eviction."""
        expired_keys = [key for key, item in items.items() if item.is_expired]
        
        # If not enough expired items, fall back to LRU
        if len(expired_keys) < count:
            lru_policy = LRUEvictionPolicy()
            remaining_items = {k: v for k, v in items.items() if k not in expired_keys}
            additional_keys = lru_policy.select_eviction_candidates(
                remaining_items, count - len(expired_keys)
            )
            expired_keys.extend(additional_keys)
        
        return expired_keys[:count]


class CacheManager:
    """Advanced cache manager with multiple eviction policies and monitoring."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize cache manager.
        
        Args:
            config: Cache configuration
        """
        self.config = config or CacheConfig()
        self.logger = logging.getLogger(__name__)
        
        # Cache storage
        self._cache: Dict[str, CacheItem] = {}
        self._cache_lock = threading.RLock()
        
        # Statistics
        self.stats = CacheStats()
        
        # Eviction policy
        self.eviction_policy: CacheEvictionPolicy = LRUEvictionPolicy()
        
        # Background cleanup
        self._cleanup_thread = None
        self._shutdown_event = threading.Event()
        
        # Weak references for automatic cleanup
        self._weak_refs: Dict[str, weakref.ref] = {}
        
        # Start background tasks
        self._start_cleanup_thread()
        
        # Load persisted cache if configured
        if self.config.persistence_file:
            self._load_cache()
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread."""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="cache_cleanup"
        )
        self._cleanup_thread.start()
    
    def _cleanup_loop(self):
        """Background cleanup loop."""
        while not self._shutdown_event.is_set():
            try:
                self._perform_cleanup()
                self._shutdown_event.wait(self.config.cleanup_interval)
            except Exception as e:
                self.logger.error(f"Cache cleanup error: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _perform_cleanup(self):
        """Perform cache cleanup operations."""
        with self._cache_lock:
            # Remove expired items
            expired_keys = [key for key, item in self._cache.items() if item.is_expired]
            
            for key in expired_keys:
                del self._cache[key]
                self.stats.expired_items += 1
            
            if expired_keys:
                self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache items")
            
            # Check memory usage and evict if necessary
            self._check_memory_usage()
            
            # Update statistics
            self._update_stats()
    
    def _check_memory_usage(self):
        """Check memory usage and evict items if necessary."""
        current_memory = self._calculate_memory_usage()
        
        if current_memory > self.config.max_memory_mb:
            # Calculate how many items to evict (rough estimate)
            avg_item_size = current_memory / len(self._cache) if self._cache else 1
            items_to_evict = int((current_memory - self.config.max_memory_mb * 0.8) / avg_item_size)
            items_to_evict = max(1, min(items_to_evict, len(self._cache) // 4))  # Evict at most 25%
            
            self._evict_items(items_to_evict)
    
    def _calculate_memory_usage(self) -> float:
        """Calculate current memory usage in MB."""
        total_size = sum(item.size_bytes for item in self._cache.values())
        return total_size / 1024 / 1024
    
    def _evict_items(self, count: int):
        """Evict specified number of items."""
        if count <= 0 or not self._cache:
            return
        
        # Select items for eviction
        keys_to_evict = self.eviction_policy.select_eviction_candidates(self._cache, count)
        
        # Remove selected items
        for key in keys_to_evict:
            if key in self._cache:
                del self._cache[key]
                self.stats.evictions += 1
        
        if keys_to_evict:
            self.logger.debug(f"Evicted {len(keys_to_evict)} cache items")
    
    def _update_stats(self):
        """Update cache statistics."""
        self.stats.item_count = len(self._cache)
        self.stats.memory_usage_mb = self._calculate_memory_usage()
    
    def _calculate_item_size(self, value: Any) -> int:
        """Calculate size of cache item in bytes."""
        try:
            if self.config.enable_compression:
                # Estimate compressed size
                serialized = pickle.dumps(value)
                return len(serialized) // 2  # Rough compression estimate
            else:
                return len(pickle.dumps(value))
        except Exception:
            # Fallback size estimation
            return len(str(value).encode('utf-8'))
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage."""
        try:
            serialized = pickle.dumps(value)
            
            if self.config.enable_compression:
                import gzip
                return gzip.compress(serialized)
            
            return serialized
            
        except Exception as e:
            self.logger.error(f"Value serialization failed: {e}")
            raise
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        try:
            if self.config.enable_compression:
                import gzip
                data = gzip.decompress(data)
            
            return pickle.loads(data)
            
        except Exception as e:
            self.logger.error(f"Value deserialization failed: {e}")
            raise
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store item in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (optional)
        """
        with self._cache_lock:
            # Check if we need to make room
            if len(self._cache) >= self.config.max_size:
                self._evict_items(1)
            
            # Calculate item size
            item_size = self._calculate_item_size(value)
            
            # Create cache item
            cache_item = CacheItem(
                key=key,
                value=value,
                ttl=ttl or self.config.default_ttl,
                size_bytes=item_size
            )
            
            # Store item
            self._cache[key] = cache_item
            
            self.logger.debug(f"Cached item: {key} ({item_size} bytes)")
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._cache_lock:
            if key not in self._cache:
                self.stats.misses += 1
                return None
            
            item = self._cache[key]
            
            # Check if expired
            if item.is_expired:
                del self._cache[key]
                self.stats.misses += 1
                self.stats.expired_items += 1
                return None
            
            # Update access information
            item.accessed_at = time.time()
            item.access_count += 1
            
            self.stats.hits += 1
            return item.value
    
    def get_or_compute(self, key: str, compute_func: Callable[[], Any], 
                      ttl: Optional[int] = None) -> Any:
        """Get item from cache or compute and cache it.
        
        Args:
            key: Cache key
            compute_func: Function to compute value if not cached
            ttl: Time-to-live in seconds (optional)
            
        Returns:
            Cached or computed value
        """
        # Try to get from cache first
        value = self.get(key)
        
        if value is not None:
            return value
        
        # Compute value
        try:
            computed_value = compute_func()
            self.put(key, computed_value, ttl)
            return computed_value
        except Exception as e:
            self.logger.error(f"Failed to compute value for key {key}: {e}")
            raise
    
    def delete(self, key: str) -> bool:
        """Delete item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if item was deleted, False if not found
        """
        with self._cache_lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """Clear all items from cache."""
        with self._cache_lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            self.logger.info(f"Cleared {cleared_count} cache items")
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache and is not expired.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is not expired
        """
        with self._cache_lock:
            if key not in self._cache:
                return False
            
            item = self._cache[key]
            if item.is_expired:
                del self._cache[key]
                self.stats.expired_items += 1
                return False
            
            return True
    
    def keys(self) -> List[str]:
        """Get list of all cache keys."""
        with self._cache_lock:
            return list(self._cache.keys())
    
    def set_eviction_policy(self, policy: CacheEvictionPolicy):
        """Set cache eviction policy.
        
        Args:
            policy: Eviction policy instance
        """
        self.eviction_policy = policy
        self.logger.info(f"Cache eviction policy set to {policy.__class__.__name__}")
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._cache_lock:
            self._update_stats()
            return self.stats
    
    def get_item_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get information about cached item.
        
        Args:
            key: Cache key
            
        Returns:
            Item information dictionary or None if not found
        """
        with self._cache_lock:
            if key not in self._cache:
                return None
            
            item = self._cache[key]
            return {
                'key': item.key,
                'created_at': item.created_at,
                'accessed_at': item.accessed_at,
                'ttl': item.ttl,
                'size_bytes': item.size_bytes,
                'access_count': item.access_count,
                'age_seconds': item.age_seconds,
                'is_expired': item.is_expired
            }
    
    def _save_cache(self):
        """Save cache to persistence file."""
        if not self.config.persistence_file:
            return
        
        try:
            cache_data = {}
            
            with self._cache_lock:
                for key, item in self._cache.items():
                    if not item.is_expired:  # Only save non-expired items
                        cache_data[key] = {
                            'value': self._serialize_value(item.value),
                            'created_at': item.created_at,
                            'ttl': item.ttl,
                            'access_count': item.access_count
                        }
            
            with open(self.config.persistence_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            self.logger.info(f"Cache saved to {self.config.persistence_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save cache: {e}")
    
    def _load_cache(self):
        """Load cache from persistence file."""
        if not self.config.persistence_file:
            return
        
        try:
            with open(self.config.persistence_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            loaded_count = 0
            
            with self._cache_lock:
                for key, data in cache_data.items():
                    try:
                        value = self._deserialize_value(data['value'])
                        
                        item = CacheItem(
                            key=key,
                            value=value,
                            created_at=data['created_at'],
                            ttl=data['ttl'],
                            access_count=data['access_count'],
                            size_bytes=self._calculate_item_size(value)
                        )
                        
                        # Only load non-expired items
                        if not item.is_expired:
                            self._cache[key] = item
                            loaded_count += 1
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to load cache item {key}: {e}")
            
            self.logger.info(f"Loaded {loaded_count} cache items from {self.config.persistence_file}")
            
        except FileNotFoundError:
            self.logger.info("No cache persistence file found")
        except Exception as e:
            self.logger.error(f"Failed to load cache: {e}")
    
    def shutdown(self):
        """Shutdown cache manager."""
        self._shutdown_event.set()
        
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
        
        # Save cache if persistence is enabled
        if self.config.persistence_file:
            self._save_cache()
        
        self.logger.info("Cache manager shutdown complete")


class MultiLevelCache:
    """Multi-level cache with L1 (memory) and L2 (disk) tiers."""
    
    def __init__(self, l1_config: Optional[CacheConfig] = None, 
                 l2_config: Optional[CacheConfig] = None):
        """Initialize multi-level cache.
        
        Args:
            l1_config: L1 (memory) cache configuration
            l2_config: L2 (disk) cache configuration
        """
        self.logger = logging.getLogger(__name__)
        
        # L1 cache (fast, small)
        l1_config = l1_config or CacheConfig(max_size=100, max_memory_mb=64, default_ttl=1800)
        self.l1_cache = CacheManager(l1_config)
        
        # L2 cache (slower, larger)
        l2_config = l2_config or CacheConfig(
            max_size=1000, 
            max_memory_mb=256, 
            default_ttl=7200,
            persistence_file="cache_l2.pkl"
        )
        self.l2_cache = CacheManager(l2_config)
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from multi-level cache."""
        # Try L1 first
        value = self.l1_cache.get(key)
        if value is not None:
            return value
        
        # Try L2
        value = self.l2_cache.get(key)
        if value is not None:
            # Promote to L1
            self.l1_cache.put(key, value)
            return value
        
        return None
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None):
        """Put item in multi-level cache."""
        # Store in both levels
        self.l1_cache.put(key, value, ttl)
        self.l2_cache.put(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """Delete item from multi-level cache."""
        l1_deleted = self.l1_cache.delete(key)
        l2_deleted = self.l2_cache.delete(key)
        return l1_deleted or l2_deleted
    
    def clear(self):
        """Clear all cache levels."""
        self.l1_cache.clear()
        self.l2_cache.clear()
    
    def get_stats(self) -> Dict[str, CacheStats]:
        """Get statistics for all cache levels."""
        return {
            'l1': self.l1_cache.get_stats(),
            'l2': self.l2_cache.get_stats()
        }
    
    def shutdown(self):
        """Shutdown multi-level cache."""
        self.l1_cache.shutdown()
        self.l2_cache.shutdown()


# Specialized caches for document translation
class DocumentCache(CacheManager):
    """Specialized cache for document objects."""
    
    def __init__(self):
        """Initialize document cache."""
        config = CacheConfig(
            max_size=50,  # Fewer documents but larger objects
            max_memory_mb=1024,  # More memory for documents
            default_ttl=7200,  # 2 hours
            enable_compression=True  # Compress large documents
        )
        super().__init__(config)
    
    def cache_document(self, file_path: str, document: Any, ttl: Optional[int] = None):
        """Cache parsed document.
        
        Args:
            file_path: Path to original file
            document: Parsed document object
            ttl: Time-to-live in seconds
        """
        # Use file path hash as key
        key = hashlib.md5(file_path.encode()).hexdigest()
        self.put(key, document, ttl)
    
    def get_document(self, file_path: str) -> Optional[Any]:
        """Get cached document.
        
        Args:
            file_path: Path to original file
            
        Returns:
            Cached document or None
        """
        key = hashlib.md5(file_path.encode()).hexdigest()
        return self.get(key)


class TranslationCache(CacheManager):
    """Specialized cache for translation results."""
    
    def __init__(self):
        """Initialize translation cache."""
        config = CacheConfig(
            max_size=1000,
            max_memory_mb=256,
            default_ttl=86400,  # 24 hours
            enable_compression=False  # Text doesn't compress well
        )
        super().__init__(config)
    
    def cache_translation(self, text: str, source_lang: str, target_lang: str, 
                         translation: str, ttl: Optional[int] = None):
        """Cache translation result.
        
        Args:
            text: Original text
            source_lang: Source language
            target_lang: Target language
            translation: Translated text
            ttl: Time-to-live in seconds
        """
        # Create cache key from text and languages
        key_data = f"{text}|{source_lang}|{target_lang}"
        key = hashlib.md5(key_data.encode()).hexdigest()
        
        self.put(key, translation, ttl)
    
    def get_translation(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Get cached translation.
        
        Args:
            text: Original text
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Cached translation or None
        """
        key_data = f"{text}|{source_lang}|{target_lang}"
        key = hashlib.md5(key_data.encode()).hexdigest()
        
        return self.get(key)
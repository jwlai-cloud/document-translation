"""Concurrent processing optimizations for document translation."""

import asyncio
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
import time
import logging
from queue import Queue, Empty
import psutil

from src.models.document import DocumentStructure, PageStructure, TextRegion
from src.models.layout import AdjustedRegion


@dataclass
class ProcessingConfig:
    """Configuration for concurrent processing."""
    max_workers: int = None  # Auto-detect based on CPU cores
    chunk_size: int = 10  # Number of text regions per chunk
    memory_limit_mb: int = 1024  # Memory limit per worker
    timeout_seconds: int = 300  # Timeout per processing task
    use_process_pool: bool = False  # Use processes instead of threads
    enable_batching: bool = True  # Enable batch processing
    batch_size: int = 50  # Batch size for translation requests


@dataclass
class ProcessingMetrics:
    """Metrics for concurrent processing performance."""
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    processing_time: float = 0.0
    throughput: float = 0.0  # items per second
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    worker_utilization: Dict[str, float] = field(default_factory=dict)


class ConcurrentDocumentProcessor:
    """Optimized concurrent processor for document translation tasks."""
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        """Initialize concurrent processor.
        
        Args:
            config: Processing configuration
        """
        self.config = config or ProcessingConfig()
        self.logger = logging.getLogger(__name__)
        
        # Auto-detect optimal worker count if not specified
        if self.config.max_workers is None:
            cpu_count = multiprocessing.cpu_count()
            # Use CPU count for I/O bound tasks, CPU count - 1 for CPU bound
            self.config.max_workers = min(cpu_count, 8)  # Cap at 8 workers
        
        # Initialize executors
        self.thread_executor = None
        self.process_executor = None
        self._initialize_executors()
        
        # Performance tracking
        self.metrics = ProcessingMetrics()
        self._start_time = None
        
    def _initialize_executors(self):
        """Initialize thread and process executors."""
        self.thread_executor = ThreadPoolExecutor(
            max_workers=self.config.max_workers,
            thread_name_prefix="doc_processor"
        )
        
        if self.config.use_process_pool:
            self.process_executor = ProcessPoolExecutor(
                max_workers=min(self.config.max_workers, multiprocessing.cpu_count())
            )
    
    async def process_document_sections(
        self, 
        document: DocumentStructure,
        processor_func: Callable,
        **kwargs
    ) -> List[Any]:
        """Process document sections concurrently.
        
        Args:
            document: Document to process
            processor_func: Function to process each section
            **kwargs: Additional arguments for processor function
            
        Returns:
            List of processed results
        """
        self._start_time = time.time()
        self.metrics = ProcessingMetrics()
        
        # Split document into processable chunks
        chunks = self._create_processing_chunks(document)
        self.metrics.total_items = len(chunks)
        
        self.logger.info(f"Processing {len(chunks)} chunks with {self.config.max_workers} workers")
        
        try:
            if self.config.use_process_pool and self.process_executor:
                results = await self._process_with_processes(chunks, processor_func, **kwargs)
            else:
                results = await self._process_with_threads(chunks, processor_func, **kwargs)
            
            self._calculate_final_metrics()
            return results
            
        except Exception as e:
            self.logger.error(f"Concurrent processing failed: {e}")
            raise
    
    def _create_processing_chunks(self, document: DocumentStructure) -> List[Dict[str, Any]]:
        """Create processing chunks from document."""
        chunks = []
        
        for page in document.pages:
            # Group text regions into chunks
            text_regions = page.text_regions
            
            for i in range(0, len(text_regions), self.config.chunk_size):
                chunk_regions = text_regions[i:i + self.config.chunk_size]
                
                chunk = {
                    'page_number': page.page_number,
                    'regions': chunk_regions,
                    'chunk_id': f"page_{page.page_number}_chunk_{i // self.config.chunk_size}",
                    'visual_elements': page.visual_elements if i == 0 else []  # Include visual elements only in first chunk
                }
                chunks.append(chunk)
        
        return chunks
    
    async def _process_with_threads(
        self, 
        chunks: List[Dict[str, Any]], 
        processor_func: Callable,
        **kwargs
    ) -> List[Any]:
        """Process chunks using thread pool."""
        
        loop = asyncio.get_event_loop()
        futures = []
        
        # Submit all tasks
        for chunk in chunks:
            future = loop.run_in_executor(
                self.thread_executor,
                self._safe_process_chunk,
                chunk,
                processor_func,
                kwargs
            )
            futures.append(future)
        
        # Process results as they complete
        results = []
        completed_count = 0
        
        for future in asyncio.as_completed(futures):
            try:
                result = await future
                results.append(result)
                completed_count += 1
                self.metrics.processed_items = completed_count
                
                # Update progress
                if completed_count % 10 == 0:
                    progress = (completed_count / len(chunks)) * 100
                    self.logger.info(f"Processing progress: {progress:.1f}% ({completed_count}/{len(chunks)})")
                    
            except Exception as e:
                self.logger.error(f"Chunk processing failed: {e}")
                self.metrics.failed_items += 1
                results.append(None)  # Placeholder for failed chunk
        
        return results
    
    async def _process_with_processes(
        self, 
        chunks: List[Dict[str, Any]], 
        processor_func: Callable,
        **kwargs
    ) -> List[Any]:
        """Process chunks using process pool."""
        
        loop = asyncio.get_event_loop()
        
        # Submit tasks to process pool
        futures = []
        for chunk in chunks:
            future = loop.run_in_executor(
                self.process_executor,
                _process_chunk_worker,  # Static function for pickling
                chunk,
                processor_func,
                kwargs
            )
            futures.append(future)
        
        # Collect results
        results = []
        for future in asyncio.as_completed(futures):
            try:
                result = await future
                results.append(result)
                self.metrics.processed_items += 1
            except Exception as e:
                self.logger.error(f"Process chunk failed: {e}")
                self.metrics.failed_items += 1
                results.append(None)
        
        return results
    
    def _safe_process_chunk(
        self, 
        chunk: Dict[str, Any], 
        processor_func: Callable,
        kwargs: Dict[str, Any]
    ) -> Any:
        """Safely process a chunk with error handling."""
        
        try:
            # Monitor memory usage
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Process the chunk
            result = processor_func(chunk, **kwargs)
            
            # Check memory usage
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = final_memory - initial_memory
            
            if memory_used > self.config.memory_limit_mb:
                self.logger.warning(f"Chunk processing exceeded memory limit: {memory_used:.1f}MB")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Chunk processing error: {e}")
            raise
    
    def _calculate_final_metrics(self):
        """Calculate final processing metrics."""
        if self._start_time:
            self.metrics.processing_time = time.time() - self._start_time
            
            if self.metrics.processing_time > 0:
                self.metrics.throughput = self.metrics.processed_items / self.metrics.processing_time
        
        # Get current system metrics
        try:
            process = psutil.Process()
            self.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            self.metrics.cpu_usage_percent = process.cpu_percent()
        except Exception as e:
            self.logger.warning(f"Failed to get system metrics: {e}")
    
    def get_performance_metrics(self) -> ProcessingMetrics:
        """Get current performance metrics."""
        return self.metrics
    
    def shutdown(self):
        """Shutdown executors and cleanup resources."""
        if self.thread_executor:
            self.thread_executor.shutdown(wait=True)
        
        if self.process_executor:
            self.process_executor.shutdown(wait=True)


class BatchProcessor:
    """Optimized batch processor for translation requests."""
    
    def __init__(self, batch_size: int = 50, max_wait_time: float = 1.0):
        """Initialize batch processor.
        
        Args:
            batch_size: Maximum batch size
            max_wait_time: Maximum time to wait for batch to fill
        """
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.logger = logging.getLogger(__name__)
        
        # Batch management
        self._batch_queue = Queue()
        self._current_batch = []
        self._batch_lock = threading.Lock()
        self._last_batch_time = time.time()
        
        # Processing thread
        self._processing_thread = None
        self._shutdown_event = threading.Event()
        self._start_processing_thread()
    
    def _start_processing_thread(self):
        """Start background batch processing thread."""
        self._processing_thread = threading.Thread(
            target=self._process_batches,
            daemon=True,
            name="batch_processor"
        )
        self._processing_thread.start()
    
    def add_to_batch(self, item: Any, callback: Optional[Callable] = None) -> None:
        """Add item to current batch.
        
        Args:
            item: Item to process
            callback: Optional callback for result
        """
        with self._batch_lock:
            self._current_batch.append({
                'item': item,
                'callback': callback,
                'timestamp': time.time()
            })
            
            # Check if batch is ready
            if (len(self._current_batch) >= self.batch_size or 
                time.time() - self._last_batch_time > self.max_wait_time):
                
                self._flush_current_batch()
    
    def _flush_current_batch(self):
        """Flush current batch to processing queue."""
        if self._current_batch:
            batch = self._current_batch.copy()
            self._current_batch.clear()
            self._last_batch_time = time.time()
            
            self._batch_queue.put(batch)
            self.logger.debug(f"Flushed batch with {len(batch)} items")
    
    def _process_batches(self):
        """Background thread to process batches."""
        while not self._shutdown_event.is_set():
            try:
                # Get batch with timeout
                batch = self._batch_queue.get(timeout=0.5)
                
                if batch:
                    self._process_single_batch(batch)
                    
            except Empty:
                # Check if we need to flush current batch due to timeout
                with self._batch_lock:
                    if (self._current_batch and 
                        time.time() - self._last_batch_time > self.max_wait_time):
                        self._flush_current_batch()
            
            except Exception as e:
                self.logger.error(f"Batch processing error: {e}")
    
    def _process_single_batch(self, batch: List[Dict[str, Any]]):
        """Process a single batch of items."""
        try:
            # Extract items for batch processing
            items = [entry['item'] for entry in batch]
            
            # Process batch (this would be implemented by subclasses)
            results = self._batch_process_items(items)
            
            # Call callbacks with results
            for entry, result in zip(batch, results):
                if entry['callback']:
                    try:
                        entry['callback'](result)
                    except Exception as e:
                        self.logger.error(f"Callback error: {e}")
                        
        except Exception as e:
            self.logger.error(f"Batch processing failed: {e}")
            
            # Call callbacks with error
            for entry in batch:
                if entry['callback']:
                    try:
                        entry['callback'](None, error=e)
                    except Exception:
                        pass
    
    def _batch_process_items(self, items: List[Any]) -> List[Any]:
        """Process batch of items. Override in subclasses."""
        # Default implementation processes items individually
        return [self._process_single_item(item) for item in items]
    
    def _process_single_item(self, item: Any) -> Any:
        """Process single item. Override in subclasses."""
        return item
    
    def shutdown(self):
        """Shutdown batch processor."""
        self._shutdown_event.set()
        
        # Flush remaining batch
        with self._batch_lock:
            self._flush_current_batch()
        
        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)


# Static function for process pool (must be picklable)
def _process_chunk_worker(chunk: Dict[str, Any], processor_func: Callable, kwargs: Dict[str, Any]) -> Any:
    """Worker function for process pool execution."""
    return processor_func(chunk, **kwargs)


class TranslationBatchProcessor(BatchProcessor):
    """Specialized batch processor for translation requests."""
    
    def __init__(self, translation_service, batch_size: int = 50, max_wait_time: float = 2.0):
        """Initialize translation batch processor.
        
        Args:
            translation_service: Translation service instance
            batch_size: Maximum batch size
            max_wait_time: Maximum wait time for batch
        """
        self.translation_service = translation_service
        super().__init__(batch_size, max_wait_time)
    
    def _batch_process_items(self, items: List[TextRegion]) -> List[AdjustedRegion]:
        """Process batch of text regions for translation."""
        try:
            # Use translation service batch processing
            return self.translation_service.translate_regions_batch(items)
        except Exception as e:
            self.logger.error(f"Translation batch processing failed: {e}")
            # Return individual processing as fallback
            return [self.translation_service.translate_region(item) for item in items]


# Example usage and integration
class OptimizedTranslationPipeline:
    """Optimized translation pipeline using concurrent processing."""
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        """Initialize optimized pipeline."""
        self.config = config or ProcessingConfig()
        self.concurrent_processor = ConcurrentDocumentProcessor(config)
        self.logger = logging.getLogger(__name__)
    
    async def process_document_optimized(
        self, 
        document: DocumentStructure,
        translation_service,
        **kwargs
    ) -> DocumentStructure:
        """Process document with optimized concurrent processing."""
        
        def process_chunk(chunk: Dict[str, Any], **proc_kwargs) -> Dict[str, Any]:
            """Process a single chunk of text regions."""
            try:
                # Translate regions in chunk
                translated_regions = []
                for region in chunk['regions']:
                    translated_region = translation_service.translate_region(
                        region, **proc_kwargs
                    )
                    translated_regions.append(translated_region)
                
                return {
                    'chunk_id': chunk['chunk_id'],
                    'page_number': chunk['page_number'],
                    'translated_regions': translated_regions,
                    'visual_elements': chunk['visual_elements']
                }
                
            except Exception as e:
                self.logger.error(f"Chunk processing failed: {e}")
                raise
        
        # Process document sections concurrently
        results = await self.concurrent_processor.process_document_sections(
            document, process_chunk, **kwargs
        )
        
        # Reconstruct document from results
        return self._reconstruct_document(document, results)
    
    def _reconstruct_document(
        self, 
        original_document: DocumentStructure, 
        processed_results: List[Dict[str, Any]]
    ) -> DocumentStructure:
        """Reconstruct document from processed chunks."""
        
        # Group results by page
        pages_data = {}
        for result in processed_results:
            if result:  # Skip failed chunks
                page_num = result['page_number']
                if page_num not in pages_data:
                    pages_data[page_num] = {
                        'translated_regions': [],
                        'visual_elements': []
                    }
                
                pages_data[page_num]['translated_regions'].extend(
                    result['translated_regions']
                )
                pages_data[page_num]['visual_elements'].extend(
                    result['visual_elements']
                )
        
        # Reconstruct pages
        new_pages = []
        for page in original_document.pages:
            page_data = pages_data.get(page.page_number, {})
            
            new_page = PageStructure(
                page_number=page.page_number,
                width=page.width,
                height=page.height,
                text_regions=page_data.get('translated_regions', []),
                visual_elements=page_data.get('visual_elements', page.visual_elements)
            )
            new_pages.append(new_page)
        
        # Create new document
        return DocumentStructure(
            format_type=original_document.format_type,
            pages=new_pages,
            metadata=original_document.metadata
        )
    
    def get_performance_metrics(self) -> ProcessingMetrics:
        """Get performance metrics."""
        return self.concurrent_processor.get_performance_metrics()
    
    def shutdown(self):
        """Shutdown pipeline."""
        self.concurrent_processor.shutdown()
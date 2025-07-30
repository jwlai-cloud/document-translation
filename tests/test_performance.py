"""Performance and load tests for document translation system."""

import pytest
import asyncio
import time
import tempfile
import os
import threading
import psutil
from typing import List, Dict, Any
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.services.orchestrator_service import TranslationOrchestrator, OrchestrationConfig
from src.services.upload_service import FileUploadService, UploadConfig
from src.web.gradio_interface import TranslationWebInterface


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = OrchestrationConfig(
            max_concurrent_jobs=5,
            job_timeout_minutes=10
        )
        self.orchestrator = TranslationOrchestrator(self.config)
        self.test_files = self._create_performance_test_files()
        
        # Performance tracking
        self.performance_metrics = {
            'processing_times': [],
            'memory_usage': [],
            'cpu_usage': [],
            'throughput': []
        }
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.orchestrator.shutdown()
        # Clean up test files
        for file_path in self.test_files:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def _create_performance_test_files(self) -> List[str]:
        """Create test files of various sizes for performance testing."""
        test_files = []
        
        # Small files (< 1MB)
        for i in range(3):
            content = f'%PDF-1.4\nSmall test document {i}\n' + 'x' * 1000
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(content.encode())
                test_files.append(f.name)
        
        # Medium files (1-5MB)
        for i in range(2):
            content = f'%PDF-1.4\nMedium test document {i}\n' + 'x' * 1000000
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(content.encode())
                test_files.append(f.name)
        
        # Large file (5-10MB)
        content = '%PDF-1.4\nLarge test document\n' + 'x' * 5000000
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(content.encode())
            test_files.append(f.name)
        
        return test_files
    
    @pytest.mark.asyncio
    async def test_single_document_processing_speed(self):
        """Test processing speed for single document."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup fast mocks
            self._setup_performance_mocks(mock_factory, mock_translation, mock_layout, mock_quality)
            
            # Test processing speed for different file sizes
            for i, file_path in enumerate(self.test_files[:3]):  # Test first 3 files
                start_time = time.time()
                
                job_id = self.orchestrator.submit_translation_job(
                    file_path=file_path,
                    source_language='en',
                    target_language='fr',
                    format_type='pdf'
                )
                
                # Wait for completion
                await self._wait_for_completion(job_id)
                
                processing_time = time.time() - start_time
                self.performance_metrics['processing_times'].append(processing_time)
                
                # Verify completion
                status = self.orchestrator.get_job_status(job_id)
                assert status['status'] == 'completed'
                
                # Performance assertion - should complete within reasonable time
                file_size = os.path.getsize(file_path) / 1024 / 1024  # MB
                expected_time = max(5, file_size * 2)  # 2 seconds per MB minimum 5 seconds
                assert processing_time < expected_time, \
                    f"Processing took {processing_time:.2f}s for {file_size:.2f}MB file"
        
        # Verify average processing time
        avg_time = sum(self.performance_metrics['processing_times']) / len(self.performance_metrics['processing_times'])
        assert avg_time < 15, f"Average processing time too high: {avg_time:.2f}s"
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_performance(self):
        """Test performance with concurrent document processing."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            self._setup_performance_mocks(mock_factory, mock_translation, mock_layout, mock_quality)
            
            # Submit multiple jobs concurrently
            start_time = time.time()
            job_ids = []
            
            for file_path in self.test_files[:4]:  # Process 4 files concurrently
                job_id = self.orchestrator.submit_translation_job(
                    file_path=file_path,
                    source_language='en',
                    target_language='fr',
                    format_type='pdf'
                )
                job_ids.append(job_id)
            
            # Wait for all jobs to complete
            for job_id in job_ids:
                await self._wait_for_completion(job_id)
            
            total_time = time.time() - start_time
            
            # Verify all jobs completed
            completed_jobs = 0
            for job_id in job_ids:
                status = self.orchestrator.get_job_status(job_id)
                if status['status'] == 'completed':
                    completed_jobs += 1
            
            assert completed_jobs == len(job_ids)
            
            # Calculate throughput
            throughput = len(job_ids) / total_time  # jobs per second
            self.performance_metrics['throughput'].append(throughput)
            
            # Performance assertion - concurrent processing should be efficient
            assert total_time < 30, f"Concurrent processing took too long: {total_time:.2f}s"
            assert throughput > 0.1, f"Throughput too low: {throughput:.3f} jobs/sec"
    
    @pytest.mark.asyncio
    async def test_memory_usage_performance(self):
        """Test memory usage during processing."""
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            self._setup_performance_mocks(mock_factory, mock_translation, mock_layout, mock_quality)
            
            # Process multiple documents and monitor memory
            job_ids = []
            memory_samples = []
            
            for file_path in self.test_files:
                job_id = self.orchestrator.submit_translation_job(
                    file_path=file_path,
                    source_language='en',
                    target_language='fr',
                    format_type='pdf'
                )
                job_ids.append(job_id)
                
                # Sample memory usage
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_samples.append(current_memory)
            
            # Wait for all jobs to complete
            for job_id in job_ids:
                await self._wait_for_completion(job_id)
            
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            max_memory = max(memory_samples)
            memory_increase = max_memory - initial_memory
            
            self.performance_metrics['memory_usage'].extend(memory_samples)
            
            # Memory usage assertions
            assert memory_increase < 200, f"Memory usage increased by {memory_increase:.2f}MB"
            assert final_memory < initial_memory + 100, f"Memory not properly cleaned up"
    
    @pytest.mark.asyncio
    async def test_cpu_usage_performance(self):
        """Test CPU usage during processing."""
        
        cpu_samples = []
        
        def monitor_cpu():
            """Monitor CPU usage in background."""
            for _ in range(20):  # Monitor for 20 seconds
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_samples.append(cpu_percent)
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            self._setup_performance_mocks(mock_factory, mock_translation, mock_layout, mock_quality)
            
            # Start CPU monitoring
            cpu_thread = threading.Thread(target=monitor_cpu, daemon=True)
            cpu_thread.start()
            
            # Process documents
            job_ids = []
            for file_path in self.test_files[:3]:
                job_id = self.orchestrator.submit_translation_job(
                    file_path=file_path,
                    source_language='en',
                    target_language='fr',
                    format_type='pdf'
                )
                job_ids.append(job_id)
            
            # Wait for completion
            for job_id in job_ids:
                await self._wait_for_completion(job_id)
            
            # Wait for CPU monitoring to finish
            cpu_thread.join(timeout=5)
            
            if cpu_samples:
                avg_cpu = sum(cpu_samples) / len(cpu_samples)
                max_cpu = max(cpu_samples)
                
                self.performance_metrics['cpu_usage'].extend(cpu_samples)
                
                # CPU usage should be reasonable
                assert avg_cpu < 80, f"Average CPU usage too high: {avg_cpu:.2f}%"
                assert max_cpu < 95, f"Peak CPU usage too high: {max_cpu:.2f}%"
    
    def test_orchestrator_statistics_performance(self):
        """Test performance of statistics collection."""
        
        # Generate some job history
        for i in range(10):
            job = Mock()
            job.status = 'completed'
            job.duration = Mock(total_seconds=lambda: 30.0)
            self.orchestrator.job_history.append(job)
        
        # Measure statistics collection time
        start_time = time.time()
        
        for _ in range(100):  # Call stats 100 times
            stats = self.orchestrator.get_orchestrator_stats()
        
        stats_time = time.time() - start_time
        
        # Statistics collection should be fast
        assert stats_time < 1.0, f"Statistics collection too slow: {stats_time:.3f}s"
        
        # Verify stats are complete
        assert 'active_jobs' in stats
        assert 'completed_jobs' in stats
        assert 'error_handling' in stats
    
    def _setup_performance_mocks(self, mock_factory, mock_translation, mock_layout, mock_quality):
        """Setup mocks optimized for performance testing."""
        
        # Fast parser mock
        mock_parser = Mock()
        mock_parser.parse.return_value = Mock()
        mock_parser.reconstruct.return_value = b'Mock content'
        mock_factory.return_value.create_parser.return_value = mock_parser
        
        # Fast translation mock
        mock_translation.return_value.translate_regions.return_value = []
        
        # Fast layout analysis mock
        mock_layout.return_value.analyze_layout.return_value = Mock()
        
        # Fast quality assessment mock
        mock_quality.return_value.assess_translation.return_value = Mock(
            overall_score=Mock(value=0.85)
        )
    
    async def _wait_for_completion(self, job_id: str, timeout: int = 20):
        """Wait for job completion with timeout."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.orchestrator.get_job_status(job_id)
            if status and status['status'] in ['completed', 'failed']:
                return
            await asyncio.sleep(0.1)
        
        # Timeout - job should have completed
        final_status = self.orchestrator.get_job_status(job_id)
        assert final_status is not None, f"Job {job_id} not found"
        assert final_status['status'] in ['completed', 'failed'], \
            f"Job {job_id} did not complete within {timeout}s"


class TestLoadTesting:
    """Load testing for high-volume scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = OrchestrationConfig(
            max_concurrent_jobs=10,
            job_timeout_minutes=15
        )
        self.orchestrator = TranslationOrchestrator(self.config)
        self.web_interface = TranslationWebInterface()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.orchestrator.shutdown()
        self.web_interface.shutdown()
    
    @pytest.mark.asyncio
    async def test_high_volume_job_submission(self):
        """Test handling high volume of job submissions."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup fast mocks
            mock_parser = Mock()
            mock_parser.parse.return_value = Mock()
            mock_parser.reconstruct.return_value = b'Mock content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = []
            mock_layout.return_value.analyze_layout.return_value = Mock()
            mock_quality.return_value.assess_translation.return_value = Mock(overall_score=Mock(value=0.85))
            
            # Create test file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(b'%PDF-1.4\nTest content')
                test_file = f.name
            
            try:
                # Submit many jobs quickly
                job_ids = []
                start_time = time.time()
                
                for i in range(20):  # Submit 20 jobs
                    job_id = self.orchestrator.submit_translation_job(
                        file_path=test_file,
                        source_language='en',
                        target_language='fr',
                        format_type='pdf'
                    )
                    job_ids.append(job_id)
                
                submission_time = time.time() - start_time
                
                # Job submission should be fast
                assert submission_time < 5.0, f"Job submission too slow: {submission_time:.2f}s"
                
                # Wait for jobs to complete (with reasonable timeout)
                completed_jobs = 0
                max_wait = 60  # 1 minute total
                check_start = time.time()
                
                while time.time() - check_start < max_wait and completed_jobs < len(job_ids):
                    completed_jobs = 0
                    for job_id in job_ids:
                        status = self.orchestrator.get_job_status(job_id)
                        if status and status['status'] == 'completed':
                            completed_jobs += 1
                    
                    if completed_jobs < len(job_ids):
                        await asyncio.sleep(1)
                
                # Verify most jobs completed
                completion_rate = completed_jobs / len(job_ids)
                assert completion_rate > 0.8, f"Low completion rate: {completion_rate:.2%}"
                
            finally:
                os.unlink(test_file)
    
    @pytest.mark.asyncio
    async def test_concurrent_user_simulation(self):
        """Simulate multiple concurrent users."""
        
        with patch('src.services.upload_service.FileUploadService') as mock_upload, \
             patch('src.parsers.factory.DocumentParserFactory') as mock_factory, \
             patch('src.translation.translation_service.TranslationService') as mock_translation, \
             patch('src.layout.analysis_engine.DefaultLayoutAnalysisEngine') as mock_layout, \
             patch('src.quality.assessment_service.QualityAssessmentService') as mock_quality:
            
            # Setup mocks
            mock_upload.return_value.upload_file.return_value = (True, Mock(file_id='test_123'), [])
            mock_upload.return_value.get_file_path.return_value.__enter__.return_value = '/tmp/test.pdf'
            
            mock_parser = Mock()
            mock_parser.parse.return_value = Mock()
            mock_parser.reconstruct.return_value = b'Mock content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            mock_translation.return_value.translate_regions.return_value = []
            mock_layout.return_value.analyze_layout.return_value = Mock()
            mock_quality.return_value.assess_translation.return_value = Mock(overall_score=Mock(value=0.85))
            
            # Simulate concurrent users
            def simulate_user(user_id: int) -> Dict[str, Any]:
                """Simulate a single user workflow."""
                try:
                    # Upload and submit job
                    result = self.web_interface._handle_translation_submit(
                        file_data=f'Mock file data for user {user_id}'.encode(),
                        format_type='pdf',
                        source_lang='en',
                        target_lang='fr',
                        preserve_layout=True,
                        quality_assessment=True,
                        quality_threshold=0.8
                    )
                    
                    return {
                        'user_id': user_id,
                        'success': 'successfully' in result[0].lower(),
                        'response': result[0]
                    }
                except Exception as e:
                    return {
                        'user_id': user_id,
                        'success': False,
                        'error': str(e)
                    }
            
            # Run concurrent user simulations
            num_users = 10
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=num_users) as executor:
                futures = [executor.submit(simulate_user, i) for i in range(num_users)]
                results = [future.result() for future in as_completed(futures)]
            
            total_time = time.time() - start_time
            
            # Analyze results
            successful_users = [r for r in results if r['success']]
            success_rate = len(successful_users) / len(results)
            
            # Performance assertions
            assert total_time < 30, f"Concurrent user simulation took too long: {total_time:.2f}s"
            assert success_rate > 0.8, f"Low success rate: {success_rate:.2%}"
    
    def test_memory_leak_detection(self):
        """Test for memory leaks during extended operation."""
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_samples = [initial_memory]
        
        # Simulate extended operation
        for cycle in range(5):  # 5 cycles of operations
            
            # Create and destroy multiple orchestrators
            for i in range(3):
                temp_orchestrator = TranslationOrchestrator()
                
                # Add some job history
                for j in range(10):
                    job = Mock()
                    job.status = 'completed'
                    temp_orchestrator.job_history.append(job)
                
                # Get statistics multiple times
                for k in range(10):
                    stats = temp_orchestrator.get_orchestrator_stats()
                
                temp_orchestrator.shutdown()
            
            # Sample memory after each cycle
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_samples.append(current_memory)
        
        final_memory = memory_samples[-1]
        memory_growth = final_memory - initial_memory
        
        # Check for memory leaks
        assert memory_growth < 50, f"Potential memory leak detected: {memory_growth:.2f}MB growth"
        
        # Memory should not continuously grow
        if len(memory_samples) >= 3:
            recent_growth = memory_samples[-1] - memory_samples[-3]
            assert recent_growth < 20, f"Continuous memory growth: {recent_growth:.2f}MB"


class TestScalabilityLimits:
    """Test system behavior at scalability limits."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = OrchestrationConfig(
            max_concurrent_jobs=2,  # Low limit for testing
            job_timeout_minutes=5
        )
        self.orchestrator = TranslationOrchestrator(self.config)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.orchestrator.shutdown()
    
    @pytest.mark.asyncio
    async def test_job_queue_limits(self):
        """Test behavior when job queue reaches limits."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory:
            # Setup slow mock to create backlog
            mock_parser = Mock()
            mock_parser.parse.side_effect = lambda *args: time.sleep(2) or Mock()
            mock_parser.reconstruct.return_value = b'Mock content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            # Create test file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(b'%PDF-1.4\nTest content')
                test_file = f.name
            
            try:
                # Submit more jobs than concurrent limit
                job_ids = []
                for i in range(5):  # Submit 5 jobs with limit of 2 concurrent
                    job_id = self.orchestrator.submit_translation_job(
                        file_path=test_file,
                        source_language='en',
                        target_language='fr',
                        format_type='pdf'
                    )
                    job_ids.append(job_id)
                
                # Check that jobs are queued properly
                stats = self.orchestrator.get_orchestrator_stats()
                assert stats['active_jobs'] <= self.config.max_concurrent_jobs
                
                # Wait for some jobs to complete
                await asyncio.sleep(5)
                
                # Verify system is still responsive
                new_job_id = self.orchestrator.submit_translation_job(
                    file_path=test_file,
                    source_language='en',
                    target_language='fr',
                    format_type='pdf'
                )
                
                assert new_job_id is not None
                
            finally:
                os.unlink(test_file)
    
    def test_error_handling_under_load(self):
        """Test error handling when system is under load."""
        
        with patch('src.parsers.factory.DocumentParserFactory') as mock_factory:
            # Setup mock that fails intermittently
            call_count = 0
            
            def parse_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count % 3 == 0:  # Fail every 3rd call
                    raise Exception(f"Simulated failure {call_count}")
                return Mock()
            
            mock_parser = Mock()
            mock_parser.parse.side_effect = parse_side_effect
            mock_parser.reconstruct.return_value = b'Mock content'
            mock_factory.return_value.create_parser.return_value = mock_parser
            
            # Create test file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(b'%PDF-1.4\nTest content')
                test_file = f.name
            
            try:
                # Submit multiple jobs
                job_ids = []
                for i in range(6):
                    job_id = self.orchestrator.submit_translation_job(
                        file_path=test_file,
                        source_language='en',
                        target_language='fr',
                        format_type='pdf'
                    )
                    job_ids.append(job_id)
                
                # Wait for processing
                time.sleep(3)
                
                # Check that system handled errors gracefully
                failed_jobs = 0
                completed_jobs = 0
                
                for job_id in job_ids:
                    status = self.orchestrator.get_job_status(job_id)
                    if status:
                        if status['status'] == 'failed':
                            failed_jobs += 1
                        elif status['status'] == 'completed':
                            completed_jobs += 1
                
                # Should have some failures but system should continue working
                assert failed_jobs > 0, "Expected some failures for testing"
                assert completed_jobs > 0, "System should handle some jobs successfully"
                
                # Error handling statistics should be available
                stats = self.orchestrator.get_orchestrator_stats()
                assert 'error_handling' in stats
                
            finally:
                os.unlink(test_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
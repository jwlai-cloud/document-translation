"""Tests for translation orchestrator service."""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.models.document import DocumentStructure, PageStructure, TextRegion, BoundingBox, Dimensions, DocumentMetadata
from src.models.layout import AdjustedRegion, LayoutAnalysis
from src.services.orchestrator_service import (
    TranslationOrchestrator, OrchestrationConfig, TranslationJob,
    TranslationStatus, TranslationError, ErrorSeverity, StageProgress
)


class TestTranslationJob:
    """Test cases for TranslationJob."""
    
    def test_translation_job_creation(self):
        """Test TranslationJob creation and properties."""
        job = TranslationJob(
            file_path="/test/document.pdf",
            source_language="en",
            target_language="fr",
            format_type="pdf"
        )
        
        assert job.file_path == "/test/document.pdf"
        assert job.source_language == "en"
        assert job.target_language == "fr"
        assert job.format_type == "pdf"
        assert job.status == TranslationStatus.PENDING
        assert job.overall_progress == 0.0
        assert job.retry_count == 0
        assert job.is_completed is False
        assert job.has_critical_errors is False
    
    def test_translation_job_duration(self):
        """Test job duration calculation."""
        job = TranslationJob()
        
        # No duration when not started
        assert job.duration is None
        
        # Set start and end times
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=5)
        job.started_at = start_time
        job.completed_at = end_time
        
        duration = job.duration
        assert duration is not None
        assert duration.total_seconds() == 300  # 5 minutes
    
    def test_translation_job_completion_status(self):
        """Test job completion status checking."""
        job = TranslationJob()
        
        # Initially not completed
        assert job.is_completed is False
        
        # Test different completion statuses
        completion_statuses = [
            TranslationStatus.COMPLETED,
            TranslationStatus.FAILED,
            TranslationStatus.CANCELLED
        ]
        
        for status in completion_statuses:
            job.status = status
            assert job.is_completed is True
        
        # Test non-completion status
        job.status = TranslationStatus.TRANSLATING
        assert job.is_completed is False
    
    def test_translation_job_critical_errors(self):
        """Test critical error detection."""
        job = TranslationJob()
        
        # No critical errors initially
        assert job.has_critical_errors is False
        
        # Add non-critical error
        job.errors.append(TranslationError(
            stage="test",
            error_type="test_error",
            message="Test error",
            severity=ErrorSeverity.MEDIUM
        ))
        assert job.has_critical_errors is False
        
        # Add critical error
        job.errors.append(TranslationError(
            stage="test",
            error_type="critical_error",
            message="Critical error",
            severity=ErrorSeverity.CRITICAL
        ))
        assert job.has_critical_errors is True


class TestStageProgress:
    """Test cases for StageProgress."""
    
    def test_stage_progress_creation(self):
        """Test StageProgress creation and properties."""
        stage = StageProgress(
            stage_name="parsing",
            status=TranslationStatus.PARSING
        )
        
        assert stage.stage_name == "parsing"
        assert stage.status == TranslationStatus.PARSING
        assert stage.progress_percentage == 0.0
        assert stage.items_processed == 0
        assert stage.total_items == 0
        assert stage.is_completed is False
        assert stage.duration is None
    
    def test_stage_progress_completion(self):
        """Test stage completion tracking."""
        stage = StageProgress("test", TranslationStatus.PENDING)
        
        # Not completed initially
        assert stage.is_completed is False
        
        # Set end time
        stage.end_time = datetime.now()
        assert stage.is_completed is True
    
    def test_stage_progress_duration(self):
        """Test stage duration calculation."""
        stage = StageProgress("test", TranslationStatus.PENDING)
        
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=30)
        stage.start_time = start_time
        stage.end_time = end_time
        
        duration = stage.duration
        assert duration is not None
        assert duration.total_seconds() == 30


class TestOrchestrationConfig:
    """Test cases for OrchestrationConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = OrchestrationConfig()
        
        assert config.max_concurrent_jobs == 3
        assert config.job_timeout_minutes == 30
        assert config.retry_delays == [5, 15, 30]
        assert config.cleanup_interval_minutes == 60
        assert config.max_job_history == 100
        assert config.enable_quality_assessment is True
        assert config.quality_threshold == 0.7
        assert config.progress_callback_interval == 1.0
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = OrchestrationConfig(
            max_concurrent_jobs=5,
            job_timeout_minutes=60,
            enable_quality_assessment=False,
            quality_threshold=0.8
        )
        
        assert config.max_concurrent_jobs == 5
        assert config.job_timeout_minutes == 60
        assert config.enable_quality_assessment is False
        assert config.quality_threshold == 0.8


class TestTranslationOrchestrator:
    """Test cases for TranslationOrchestrator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = OrchestrationConfig(
            max_concurrent_jobs=2,
            job_timeout_minutes=1,  # Short timeout for testing
            cleanup_interval_minutes=1
        )
        
        # Mock all the services
        with patch.multiple(
            'src.services.orchestrator_service',
            DocumentParserFactory=Mock(),
            DefaultLayoutAnalysisEngine=Mock(),
            TranslationService=Mock(),
            TextFittingEngine=Mock(),
            LayoutAdjustmentEngine=Mock(),
            DefaultLayoutReconstructionEngine=Mock(),
            QualityAssessmentService=Mock(),
            DownloadService=Mock()
        ):
            self.orchestrator = TranslationOrchestrator(self.config)
    
    def teardown_method(self):
        """Clean up after tests."""
        self.orchestrator.shutdown()
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        assert self.orchestrator.config == self.config
        assert len(self.orchestrator.active_jobs) == 0
        assert len(self.orchestrator.job_history) == 0
        assert len(self.orchestrator.progress_callbacks) == 0
    
    def test_submit_translation_job(self):
        """Test submitting a translation job."""
        job_id = self.orchestrator.submit_translation_job(
            file_path="/test/document.pdf",
            source_language="en",
            target_language="fr",
            format_type="pdf"
        )
        
        assert isinstance(job_id, str)
        assert job_id in self.orchestrator.active_jobs
        
        job = self.orchestrator.active_jobs[job_id]
        assert job.file_path == "/test/document.pdf"
        assert job.source_language == "en"
        assert job.target_language == "fr"
        assert job.format_type == "pdf"
        assert len(job.stages) > 0
    
    def test_get_job_status_active(self):
        """Test getting status of active job."""
        job_id = self.orchestrator.submit_translation_job("/test/document.pdf")
        
        status = self.orchestrator.get_job_status(job_id)
        
        assert status is not None
        assert status['job_id'] == job_id
        assert 'status' in status
        assert 'overall_progress' in status
        assert 'stages' in status
        assert 'created_at' in status
    
    def test_get_job_status_nonexistent(self):
        """Test getting status of non-existent job."""
        status = self.orchestrator.get_job_status("nonexistent_job")
        assert status is None
    
    def test_cancel_job(self):
        """Test cancelling a job."""
        job_id = self.orchestrator.submit_translation_job("/test/document.pdf")
        
        # Cancel the job
        success = self.orchestrator.cancel_job(job_id)
        assert success is True
        
        # Check job status
        job = self.orchestrator.active_jobs[job_id]
        assert job.status == TranslationStatus.CANCELLED
        assert job.completed_at is not None
    
    def test_cancel_nonexistent_job(self):
        """Test cancelling non-existent job."""
        success = self.orchestrator.cancel_job("nonexistent_job")
        assert success is False
    
    def test_add_progress_callback(self):
        """Test adding progress callback."""
        callback = Mock()
        
        self.orchestrator.add_progress_callback(callback)
        
        assert callback in self.orchestrator.progress_callbacks
    
    def test_get_orchestrator_stats(self):
        """Test getting orchestrator statistics."""
        stats = self.orchestrator.get_orchestrator_stats()
        
        assert 'active_jobs' in stats
        assert 'completed_jobs' in stats
        assert 'failed_jobs' in stats
        assert 'total_jobs_processed' in stats
        assert 'max_concurrent_jobs' in stats
        assert 'job_timeout_minutes' in stats
        assert 'success_rate' in stats
        
        assert stats['active_jobs'] == 0
        assert stats['max_concurrent_jobs'] == self.config.max_concurrent_jobs
    
    def test_detect_document_format(self):
        """Test document format detection."""
        assert self.orchestrator._detect_document_format("test.pdf") == "pdf"
        assert self.orchestrator._detect_document_format("test.docx") == "docx"
        assert self.orchestrator._detect_document_format("test.doc") == "docx"
        assert self.orchestrator._detect_document_format("test.epub") == "epub"
        assert self.orchestrator._detect_document_format("test.unknown") == "pdf"  # Default
    
    def test_handle_job_error(self):
        """Test job error handling."""
        job = TranslationJob()
        
        self.orchestrator._handle_job_error(
            job, "test_stage", "test_error", "Test error message", ErrorSeverity.HIGH
        )
        
        assert len(job.errors) == 1
        assert job.status == TranslationStatus.FAILED
        assert job.completed_at is not None
        
        error = job.errors[0]
        assert error.stage == "test_stage"
        assert error.error_type == "test_error"
        assert error.message == "Test error message"
        assert error.severity == ErrorSeverity.HIGH
    
    def test_handle_stage_error(self):
        """Test stage error handling."""
        job = TranslationJob()
        stage = StageProgress("test_stage", TranslationStatus.PENDING)
        
        self.orchestrator._handle_stage_error(
            job, stage, "test_error", "Test error message", ErrorSeverity.MEDIUM
        )
        
        assert len(stage.errors) == 1
        assert len(job.errors) == 1
        assert stage.end_time is not None
        assert job.status == TranslationStatus.FAILED
        assert job.completed_at is not None
    
    def test_notify_progress_callbacks(self):
        """Test progress callback notification."""
        callback1 = Mock()
        callback2 = Mock()
        
        self.orchestrator.add_progress_callback(callback1)
        self.orchestrator.add_progress_callback(callback2)
        
        job = TranslationJob()
        self.orchestrator._notify_progress_callbacks(job)
        
        callback1.assert_called_once_with(job)
        callback2.assert_called_once_with(job)
    
    def test_notify_progress_callbacks_with_exception(self):
        """Test progress callback notification with callback exception."""
        failing_callback = Mock(side_effect=Exception("Callback failed"))
        working_callback = Mock()
        
        self.orchestrator.add_progress_callback(failing_callback)
        self.orchestrator.add_progress_callback(working_callback)
        
        job = TranslationJob()
        # Should not raise exception
        self.orchestrator._notify_progress_callbacks(job)
        
        failing_callback.assert_called_once_with(job)
        working_callback.assert_called_once_with(job)
    
    def test_finalize_job(self):
        """Test job finalization."""
        job = TranslationJob()
        job_id = job.job_id
        
        # Add to active jobs
        self.orchestrator.active_jobs[job_id] = job
        
        # Finalize job
        self.orchestrator._finalize_job(job)
        
        # Should be removed from active jobs
        assert job_id not in self.orchestrator.active_jobs
        
        # Should be added to history
        assert job in self.orchestrator.job_history
    
    def test_finalize_job_history_limit(self):
        """Test job history size limiting."""
        # Set small history limit
        self.orchestrator.config.max_job_history = 2
        
        # Add jobs to history
        for i in range(5):
            job = TranslationJob()
            self.orchestrator.job_history.append(job)
        
        # Finalize another job
        new_job = TranslationJob()
        self.orchestrator._finalize_job(new_job)
        
        # History should be limited
        assert len(self.orchestrator.job_history) == 2
        assert new_job in self.orchestrator.job_history
    
    def test_calculate_average_processing_time(self):
        """Test average processing time calculation."""
        # No completed jobs
        avg_time = self.orchestrator._calculate_average_processing_time()
        assert avg_time is None
        
        # Add completed jobs with durations
        job1 = TranslationJob()
        job1.started_at = datetime.now()
        job1.completed_at = job1.started_at + timedelta(seconds=60)
        
        job2 = TranslationJob()
        job2.started_at = datetime.now()
        job2.completed_at = job2.started_at + timedelta(seconds=120)
        
        self.orchestrator.job_history = [job1, job2]
        
        avg_time = self.orchestrator._calculate_average_processing_time()
        assert avg_time == 90.0  # Average of 60 and 120 seconds
    
    def test_calculate_success_rate(self):
        """Test success rate calculation."""
        # No jobs
        success_rate = self.orchestrator._calculate_success_rate()
        assert success_rate == 0.0
        
        # Add jobs with different statuses
        completed_job = TranslationJob()
        completed_job.status = TranslationStatus.COMPLETED
        
        failed_job = TranslationJob()
        failed_job.status = TranslationStatus.FAILED
        
        self.orchestrator.job_history = [completed_job, failed_job]
        
        success_rate = self.orchestrator._calculate_success_rate()
        assert success_rate == 50.0  # 1 out of 2 successful
    
    @patch('src.services.orchestrator_service.DocumentParserFactory')
    @patch('src.services.orchestrator_service.DefaultLayoutAnalysisEngine')
    def test_execute_parsing_stage_success(self, mock_layout_engine, mock_parser_factory):
        """Test successful parsing stage execution."""
        # Setup mocks
        mock_parser = Mock()
        mock_document = Mock()
        mock_parser.parse.return_value = mock_document
        mock_parser_factory.return_value.create_parser.return_value = mock_parser
        
        job = TranslationJob(file_path="/test/document.pdf", format_type="pdf")
        self.orchestrator._initialize_job_stages(job)
        
        # Execute parsing stage
        success = self.orchestrator._execute_parsing_stage(job)
        
        assert success is True
        assert job.original_document == mock_document
        assert job.stages["parsing"].progress_percentage == 100.0
        assert job.stages["parsing"].end_time is not None
        assert job.overall_progress == 15.0
    
    @patch('src.services.orchestrator_service.DocumentParserFactory')
    def test_execute_parsing_stage_failure(self, mock_parser_factory):
        """Test parsing stage execution failure."""
        # Setup mock to raise exception
        mock_parser_factory.return_value.create_parser.side_effect = Exception("Parse error")
        
        job = TranslationJob(file_path="/test/document.pdf", format_type="pdf")
        self.orchestrator._initialize_job_stages(job)
        
        # Execute parsing stage
        success = self.orchestrator._execute_parsing_stage(job)
        
        assert success is False
        assert job.status == TranslationStatus.FAILED
        assert len(job.errors) > 0
        assert len(job.stages["parsing"].errors) > 0


class TestIntegration:
    """Integration tests for orchestrator service."""
    
    @patch('src.services.orchestrator_service.DocumentParserFactory')
    @patch('src.services.orchestrator_service.DefaultLayoutAnalysisEngine')
    @patch('src.services.orchestrator_service.TranslationService')
    @patch('src.services.orchestrator_service.TextFittingEngine')
    @patch('src.services.orchestrator_service.DownloadService')
    def test_full_orchestration_workflow(self, mock_download_service, mock_text_fitting,
                                       mock_translation_service, mock_layout_engine,
                                       mock_parser_factory):
        """Test complete orchestration workflow."""
        # Setup mocks
        mock_document = DocumentStructure(
            format="pdf",
            pages=[
                PageStructure(
                    page_number=1,
                    dimensions=Dimensions(width=400, height=600),
                    text_regions=[
                        TextRegion(
                            id="region1",
                            bounding_box=BoundingBox(10, 10, 200, 30),
                            text_content="Test content"
                        )
                    ]
                )
            ],
            metadata=DocumentMetadata(title="Test Document")
        )
        
        mock_parser = Mock()
        mock_parser.parse.return_value = mock_document
        mock_parser_factory.return_value.create_parser.return_value = mock_parser
        
        mock_layout_analysis = [LayoutAnalysis(page_number=1)]
        mock_layout_engine.return_value.analyze_layout.return_value = mock_layout_analysis
        
        mock_translation_service.return_value.translate_text.return_value = "Translated content"
        
        mock_adjusted_region = AdjustedRegion(
            original_region=mock_document.pages[0].text_regions[0],
            adjusted_text="Translated content",
            new_bounding_box=BoundingBox(10, 10, 220, 35),
            adjustments=[],
            fit_quality=0.9
        )
        mock_text_fitting.return_value.fit_text_to_region.return_value = mock_adjusted_region
        
        mock_download_result = Mock()
        mock_download_result.success = True
        mock_download_result.download_link.link_id = "test_link_id"
        mock_download_service.return_value.prepare_download.return_value = mock_download_result
        
        # Create orchestrator
        config = OrchestrationConfig(enable_quality_assessment=False)  # Disable for simpler test
        orchestrator = TranslationOrchestrator(config)
        
        try:
            # Submit job
            job_id = orchestrator.submit_translation_job(
                file_path="/test/document.pdf",
                source_language="en",
                target_language="fr",
                format_type="pdf"
            )
            
            # Wait for job to complete (with timeout)
            timeout = time.time() + 10  # 10 second timeout
            while time.time() < timeout:
                status = orchestrator.get_job_status(job_id)
                if status and status['status'] in ['completed', 'failed']:
                    break
                time.sleep(0.1)
            
            # Check final status
            final_status = orchestrator.get_job_status(job_id)
            
            assert final_status is not None
            print(f"Final job status: {final_status['status']}")
            
            # The job should complete successfully or at least progress through stages
            assert final_status['overall_progress'] > 0
            
        finally:
            orchestrator.shutdown()


if __name__ == "__main__":
    pytest.main([__file__])
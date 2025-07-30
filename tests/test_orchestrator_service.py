"""Tests for translation orchestrator service."""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, BoundingBox,
    Dimensions, DocumentMetadata
)
from src.models.layout import AdjustedRegion, LayoutAnalysis
from src.models.quality import QualityScore, QualityReport
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
        assert job.max_retries == 3
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
            message="Non-critical error",
            severity=ErrorSeverity.LOW
        ))
        assert job.has_critical_errors is False
        
        # Add critical error
        job.errors.append(TranslationError(
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
        assert stage.start_time is None
        assert stage.end_time is None
        assert stage.is_completed is False
        assert stage.duration is None
    
    def test_stage_progress_completion(self):
        """Test stage completion tracking."""
        stage = StageProgress("test_stage", TranslationStatus.PENDING)
        
        # Not completed initially
        assert stage.is_completed is False
        assert stage.duration is None
        
        # Set start and end times
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=30)
        stage.start_time = start_time
        stage.end_time = end_time
        
        assert stage.is_completed is True
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
            retry_delays=[10, 30, 60],
            enable_quality_assessment=False,
            quality_threshold=0.8
        )
        
        assert config.max_concurrent_jobs == 5
        assert config.job_timeout_minutes == 60
        assert config.retry_delays == [10, 30, 60]
        assert config.enable_quality_assessment is False
        assert config.quality_threshold == 0.8


class TestTranslationOrchestrator:
    """Test cases for TranslationOrchestrator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use fast cleanup for testing
        self.config = OrchestrationConfig(
            max_concurrent_jobs=2,
            job_timeout_minutes=1,
            cleanup_interval_minutes=1
        )
        
        # Mock all the services to avoid dependencies
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
        """Test job submission."""
        job_id = self.orchestrator.submit_translation_job(
            file_path="/test/document.pdf",
            source_language="en",
            target_language="fr",
            format_type="pdf"
        )
        
        assert isinstance(job_id, str)
        assert len(job_id) > 0
        assert job_id in self.orchestrator.active_jobs
        
        job = self.orchestrator.active_jobs[job_id]
        assert job.file_path == "/test/document.pdf"
        assert job.source_language == "en"
        assert job.target_language == "fr"
        assert job.format_type == "pdf"
        assert len(job.stages) > 0
    
    def test_get_job_status_active(self):
        """Test getting status of active job."""
        job_id = self.orchestrator.submit_translation_job("/test/doc.pdf")
        
        status = self.orchestrator.get_job_status(job_id)
        
        assert status is not None
        assert status['job_id'] == job_id
        assert status['status'] == TranslationStatus.PENDING.value
        assert status['overall_progress'] == 0.0
        assert 'stages' in status
        assert 'created_at' in status
    
    def test_get_job_status_nonexistent(self):
        """Test getting status of non-existent job."""
        status = self.orchestrator.get_job_status("nonexistent_job")
        assert status is None
    
    def test_get_job_status_historical(self):
        """Test getting status of historical job."""
        # Create a completed job in history
        completed_job = TranslationJob(
            job_id="historical_job",
            file_path="/test/doc.pdf"
        )
        completed_job.status = TranslationStatus.COMPLETED
        self.orchestrator.job_history.append(completed_job)
        
        status = self.orchestrator.get_job_status("historical_job")
        
        assert status is not None
        assert status['job_id'] == "historical_job"
        assert status['status'] == TranslationStatus.COMPLETED.value
    
    def test_cancel_job(self):
        """Test job cancellation."""
        job_id = self.orchestrator.submit_translation_job("/test/doc.pdf")
        
        # Cancel the job
        success = self.orchestrator.cancel_job(job_id)
        
        assert success is True
        
        job = self.orchestrator.active_jobs[job_id]
        assert job.status == TranslationStatus.CANCELLED
        assert job.completed_at is not None
    
    def test_cancel_nonexistent_job(self):
        """Test cancelling non-existent job."""
        success = self.orchestrator.cancel_job("nonexistent_job")
        assert success is False
    
    def test_cancel_completed_job(self):
        """Test cancelling already completed job."""
        job_id = self.orchestrator.submit_translation_job("/test/doc.pdf")
        
        # Mark job as completed
        job = self.orchestrator.active_jobs[job_id]
        job.status = TranslationStatus.COMPLETED
        
        success = self.orchestrator.cancel_job(job_id)
        assert success is False
    
    def test_retry_job(self):
        """Test job retry functionality."""
        job_id = self.orchestrator.submit_translation_job("/test/doc.pdf")
        
        # Mark job as failed
        job = self.orchestrator.active_jobs[job_id]
        job.status = TranslationStatus.FAILED
        job.errors.append(TranslationError(message="Test error"))
        
        # Retry the job
        success = self.orchestrator.retry_job(job_id)
        
        assert success is True
        assert job.status == TranslationStatus.PENDING
        assert job.retry_count == 1
        assert len(job.errors) == 0  # Errors should be cleared
    
    def test_retry_job_max_retries_exceeded(self):
        """Test retry when max retries exceeded."""
        job_id = self.orchestrator.submit_translation_job("/test/doc.pdf")
        
        # Set job to failed with max retries
        job = self.orchestrator.active_jobs[job_id]
        job.status = TranslationStatus.FAILED
        job.retry_count = job.max_retries
        
        success = self.orchestrator.retry_job(job_id)
        assert success is False
    
    def test_retry_non_failed_job(self):
        """Test retry of non-failed job."""
        job_id = self.orchestrator.submit_translation_job("/test/doc.pdf")
        
        # Job is still pending
        success = self.orchestrator.retry_job(job_id)
        assert success is False
    
    def test_add_progress_callback(self):
        """Test adding progress callback."""
        callback = Mock()
        
        self.orchestrator.add_progress_callback(callback)
        
        assert callback in self.orchestrator.progress_callbacks
    
    def test_get_orchestrator_stats(self):
        """Test getting orchestrator statistics."""
        # Add some jobs to history
        completed_job = TranslationJob()
        completed_job.status = TranslationStatus.COMPLETED
        failed_job = TranslationJob()
        failed_job.status = TranslationStatus.FAILED
        
        self.orchestrator.job_history = [completed_job, failed_job]
        
        stats = self.orchestrator.get_orchestrator_stats()
        
        assert 'active_jobs' in stats
        assert 'completed_jobs' in stats
        assert 'failed_jobs' in stats
        assert 'total_jobs_processed' in stats
        assert 'max_concurrent_jobs' in stats
        assert 'success_rate' in stats
        
        assert stats['completed_jobs'] == 1
        assert stats['failed_jobs'] == 1
        assert stats['total_jobs_processed'] == 2
        assert stats['success_rate'] == 50.0
    
    def test_initialize_job_stages(self):
        """Test job stage initialization."""
        job = TranslationJob()
        
        self.orchestrator._initialize_job_stages(job)
        
        expected_stages = [
            "parsing", "analyzing_layout", "translating",
            "fitting_text", "reconstructing", "assessing_quality",
            "preparing_download"
        ]
        
        assert len(job.stages) == len(expected_stages)
        for stage_name in expected_stages:
            assert stage_name in job.stages
            stage = job.stages[stage_name]
            assert stage.stage_name == stage_name
            assert stage.status == TranslationStatus.PENDING
    
    def test_detect_document_format(self):
        """Test document format detection."""
        test_cases = [
            ("/path/to/document.pdf", "pdf"),
            ("/path/to/document.docx", "docx"),
            ("/path/to/document.doc", "docx"),
            ("/path/to/document.epub", "epub"),
            ("/path/to/document.unknown", "pdf")  # Default
        ]
        
        for file_path, expected_format in test_cases:
            detected_format = self.orchestrator._detect_document_format(file_path)
            assert detected_format == expected_format
    
    def test_handle_job_error(self):
        """Test job error handling."""
        job = TranslationJob()
        
        self.orchestrator._handle_job_error(
            job, "parsing", "parse_error", "Test error", ErrorSeverity.HIGH
        )
        
        assert len(job.errors) == 1
        error = job.errors[0]
        assert error.stage == "parsing"
        assert error.error_type == "parse_error"
        assert error.message == "Test error"
        assert error.severity == ErrorSeverity.HIGH
        assert job.status == TranslationStatus.FAILED
        assert job.completed_at is not None
    
    def test_handle_stage_error(self):
        """Test stage error handling."""
        job = TranslationJob()
        stage = StageProgress("test_stage", TranslationStatus.PENDING)
        
        self.orchestrator._handle_stage_error(
            job, stage, "stage_error", "Test stage error", ErrorSeverity.MEDIUM
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
        failing_callback = Mock(side_effect=Exception("Callback error"))
        working_callback = Mock()
        
        self.orchestrator.add_progress_callback(failing_callback)
        self.orchestrator.add_progress_callback(working_callback)
        
        job = TranslationJob()
        
        # Should not raise exception despite failing callback
        self.orchestrator._notify_progress_callbacks(job)
        
        failing_callback.assert_called_once_with(job)
        working_callback.assert_called_once_with(job)
    
    def test_finalize_job(self):
        """Test job finalization."""
        job_id = self.orchestrator.submit_translation_job("/test/doc.pdf")
        job = self.orchestrator.active_jobs[job_id]
        
        # Add progress callback to verify notification
        callback = Mock()
        self.orchestrator.add_progress_callback(callback)
        
        self.orchestrator._finalize_job(job)
        
        # Job should be moved from active to history
        assert job_id not in self.orchestrator.active_jobs
        assert job in self.orchestrator.job_history
        
        # Callback should be notified
        callback.assert_called_with(job)
    
    def test_finalize_job_history_limit(self):
        """Test job history size limiting."""
        # Set small history limit
        self.orchestrator.config.max_job_history = 2
        
        # Add jobs to history
        for i in range(5):
            job = TranslationJob(job_id=f"job_{i}")
            self.orchestrator._finalize_job(job)
        
        # Should only keep the last 2 jobs
        assert len(self.orchestrator.job_history) == 2
        assert self.orchestrator.job_history[0].job_id == "job_3"
        assert self.orchestrator.job_history[1].job_id == "job_4"
    
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
        
        # Add mixed jobs
        completed_job = TranslationJob()
        completed_job.status = TranslationStatus.COMPLETED
        
        failed_job = TranslationJob()
        failed_job.status = TranslationStatus.FAILED
        
        cancelled_job = TranslationJob()
        cancelled_job.status = TranslationStatus.CANCELLED
        
        self.orchestrator.job_history = [completed_job, failed_job, cancelled_job]
        
        success_rate = self.orchestrator._calculate_success_rate()
        assert success_rate == pytest.approx(33.33, rel=1e-2)  # 1 out of 3 successful


class TestTranslationOrchestrationIntegration:
    """Integration tests for translation orchestration."""
    
    @patch('src.services.orchestrator_service.DocumentParserFactory')
    @patch('src.services.orchestrator_service.DefaultLayoutAnalysisEngine')
    @patch('src.services.orchestrator_service.TranslationService')
    @patch('src.services.orchestrator_service.TextFittingEngine')
    @patch('src.services.orchestrator_service.LayoutAdjustmentEngine')
    @patch('src.services.orchestrator_service.DefaultLayoutReconstructionEngine')
    @patch('src.services.orchestrator_service.QualityAssessmentService')
    @patch('src.services.orchestrator_service.DownloadService')
    def test_successful_job_processing(self, mock_download_service, mock_quality_service,
                                     mock_reconstruction_engine, mock_layout_adjustment,
                                     mock_text_fitting, mock_translation_service,
                                     mock_layout_engine, mock_parser_factory):
        """Test successful end-to-end job processing."""
        
        # Setup mocks
        mock_parser = Mock()
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
        
        mock_parser.parse.return_value = mock_document
        mock_parser_factory.return_value.create_parser.return_value = mock_parser
        
        mock_layout_analysis = [LayoutAnalysis(page_number=1)]
        mock_layout_engine.return_value.analyze_layout.return_value = mock_layout_analysis
        
        mock_translation_service.return_value.translate_text.return_value = "Contenu de test"
        
        mock_adjusted_region = AdjustedRegion(
            original_region=mock_document.pages[0].text_regions[0],
            adjusted_text="Contenu de test",
            new_bounding_box=BoundingBox(10, 10, 220, 35),
            adjustments=[],
            fit_quality=0.9
        )
        mock_text_fitting.return_value.fit_text_to_region.return_value = mock_adjusted_region
        
        mock_layout_adjustment.return_value.detect_layout_conflicts.return_value = []
        
        mock_quality_score = QualityScore(
            overall_score=0.85,
            metrics=Mock(),
            issues=[]
        )
        mock_quality_service.return_value.assess_layout_preservation.return_value = mock_quality_score
        mock_quality_service.return_value.generate_quality_report.return_value = QualityReport(
            document_id="test",
            overall_score=mock_quality_score
        )
        
        mock_download_result = Mock()
        mock_download_result.success = True
        mock_download_result.download_link.link_id = "test_link_id"
        mock_download_service.return_value.prepare_download.return_value = mock_download_result
        
        # Create orchestrator and submit job
        config = OrchestrationConfig(max_concurrent_jobs=1)
        orchestrator = TranslationOrchestrator(config)
        
        try:
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
            
            # Verify job completed successfully
            final_status = orchestrator.get_job_status(job_id)
            assert final_status is not None
            assert final_status['status'] == 'completed'
            assert final_status['overall_progress'] == 100.0
            assert final_status['download_link_id'] == "test_link_id"
            
            # Verify all stages were executed
            stages = final_status['stages']
            expected_stages = [
                "parsing", "analyzing_layout", "translating",
                "fitting_text", "reconstructing", "assessing_quality",
                "preparing_download"
            ]
            
            for stage_name in expected_stages:
                assert stage_name in stages
                assert stages[stage_name]['progress'] == 100.0
            
        finally:
            orchestrator.shutdown()


if __name__ == "__main__":
    pytest.main([__file__])
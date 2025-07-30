"""Tests for web interface functionality."""

import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock

from src.web.gradio_interface import TranslationWebInterface


class TestTranslationWebInterface:
    """Test cases for TranslationWebInterface."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock all services to avoid dependencies
        with patch.multiple(
            'src.web.gradio_interface',
            FileUploadService=Mock(),
            TranslationOrchestrator=Mock(),
            PreviewService=Mock(),
            DownloadService=Mock()
        ):
            self.interface = TranslationWebInterface()
    
    def test_interface_initialization(self):
        """Test interface initialization."""
        assert self.interface.upload_service is not None
        assert self.interface.orchestrator is not None
        assert self.interface.preview_service is not None
        assert self.interface.download_service is not None
        
        # Check language and format configurations
        assert "en" in self.interface.languages
        assert "fr" in self.interface.languages
        assert "pdf" in self.interface.formats
        assert "docx" in self.interface.formats
        assert "epub" in self.interface.formats
    
    def test_create_interface(self):
        """Test Gradio interface creation."""
        interface = self.interface.create_interface()
        
        # Interface should be created without errors
        assert interface is not None
    
    def test_handle_translation_submit_no_file(self):
        """Test translation submission with no file."""
        result = self.interface._handle_translation_submit(
            file_data=None,
            format_type="pdf",
            source_lang="en",
            target_lang="fr",
            preserve_layout=True,
            quality_assessment=True
        )
        
        status, job_info, error_display, success_display = result
        
        assert "Please select a file" in status
        assert error_display.value is not None
        assert "No file selected" in error_display.value
    
    def test_handle_translation_submit_upload_failure(self):
        """Test translation submission with upload failure."""
        # Mock upload service to return failure
        self.interface.upload_service.upload_file.return_value = (
            False, None, ["Upload failed", "Invalid format"]
        )
        
        result = self.interface._handle_translation_submit(
            file_data=b"fake file data",
            format_type="pdf",
            source_lang="en",
            target_lang="fr",
            preserve_layout=True,
            quality_assessment=True
        )
        
        status, job_info, error_display, success_display = result
        
        assert "upload failed" in status.lower()
        assert "Upload failed" in error_display.value
        assert "Invalid format" in error_display.value
    
    def test_handle_translation_submit_success(self):
        """Test successful translation submission."""
        # Mock successful upload
        mock_uploaded_file = Mock()
        mock_uploaded_file.file_id = "test_file_id"
        
        self.interface.upload_service.upload_file.return_value = (
            True, mock_uploaded_file, []
        )
        
        # Mock file path context manager
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value="/tmp/test_file.pdf")
        mock_context.__exit__ = Mock(return_value=None)
        self.interface.upload_service.get_file_path.return_value = mock_context
        
        # Mock orchestrator job submission
        test_job_id = "test_job_12345"
        self.interface.orchestrator.submit_translation_job.return_value = test_job_id
        
        # Mock job status
        mock_job_status = {
            'job_id': test_job_id,
            'status': 'pending',
            'overall_progress': 0.0
        }
        self.interface.orchestrator.get_job_status.return_value = mock_job_status
        
        result = self.interface._handle_translation_submit(
            file_data=b"fake pdf data",
            format_type="pdf",
            source_lang="en",
            target_lang="fr",
            preserve_layout=True,
            quality_assessment=True
        )
        
        status, job_info, error_display, success_display = result
        
        assert "successfully" in status.lower()
        assert test_job_id[:8] in status
        assert job_info.value == mock_job_status
        assert test_job_id in self.interface.active_jobs
    
    def test_update_job_progress(self):
        """Test job progress update callback."""
        # Create mock job
        mock_job = Mock()
        mock_job.job_id = "test_job_123"
        mock_job.status.value = "translating"
        mock_job.overall_progress = 45.0
        mock_job.current_stage = "translating"
        mock_job.errors = []
        
        # Add job to active jobs
        self.interface.active_jobs[mock_job.job_id] = {}
        
        # Call progress update
        self.interface._update_job_progress(mock_job)
        
        # Check that progress was updated
        assert 'last_update' in self.interface.active_jobs[mock_job.job_id]
        update = self.interface.active_jobs[mock_job.job_id]['last_update']
        assert update['status'] == "translating"
        assert update['progress'] == 45.0
        assert update['stage'] == "translating"
        assert update['errors'] == 0
    
    def test_refresh_jobs_table(self):
        """Test jobs table refresh."""
        # Mock orchestrator stats
        self.interface.orchestrator.get_orchestrator_stats.return_value = {
            'active_jobs': 2
        }
        
        # Add test jobs
        test_jobs = {
            "job1": {},
            "job2": {}
        }
        self.interface.active_jobs = test_jobs
        
        # Mock job statuses
        def mock_get_job_status(job_id):
            return {
                'job_id': job_id,
                'status': 'pending',
                'overall_progress': 25.0,
                'source_language': 'en',
                'target_language': 'fr',
                'format_type': 'pdf',
                'created_at': '2024-01-01T12:00:00'
            }
        
        self.interface.orchestrator.get_job_status.side_effect = mock_get_job_status
        
        jobs_data, job_choices = self.interface._refresh_jobs_table()
        
        assert len(jobs_data) == 2
        assert len(job_choices.choices) == 2
        
        # Check data format
        job_row = jobs_data[0]
        assert len(job_row) == 7  # All expected columns
        assert "job1"[:8] in job_row[0]  # Truncated job ID
        assert job_row[1] == 'pending'  # Status
        assert "25.0%" in job_row[2]  # Progress
    
    def test_get_job_details_no_job(self):
        """Test getting job details with no job selected."""
        job_details, stage_progress = self.interface._get_job_details(None)
        
        assert job_details.value == {}
        assert "Select a job" in stage_progress
    
    def test_get_job_details_job_not_found(self):
        """Test getting job details for non-existent job."""
        self.interface.orchestrator.get_job_status.return_value = None
        
        job_details, stage_progress = self.interface._get_job_details("nonexistent_job")
        
        assert job_details.value == {}
        assert "Job not found" in stage_progress
    
    def test_get_job_details_success(self):
        """Test successful job details retrieval."""
        mock_status = {
            'job_id': 'test_job',
            'status': 'completed',
            'overall_progress': 100.0,
            'stages': {
                'parsing': {
                    'status': 'completed',
                    'progress': 100.0,
                    'error_count': 0
                },
                'translating': {
                    'status': 'completed',
                    'progress': 100.0,
                    'error_count': 1
                }
            }
        }
        
        self.interface.orchestrator.get_job_status.return_value = mock_status
        
        job_details, stage_progress = self.interface._get_job_details("test_job")
        
        assert job_details.value == mock_status
        assert "Parsing" in stage_progress
        assert "Translating" in stage_progress
        assert "1 errors" in stage_progress  # Error count shown
    
    def test_cancel_job_no_selection(self):
        """Test job cancellation with no job selected."""
        # Mock refresh_jobs_table return
        self.interface.orchestrator.get_orchestrator_stats.return_value = {'active_jobs': 0}
        
        result = self.interface._cancel_job(None)
        
        # Should return refresh results plus error message
        assert len(result) == 4
        assert "No job selected" in result[3]
    
    def test_cancel_job_success(self):
        """Test successful job cancellation."""
        self.interface.orchestrator.cancel_job.return_value = True
        self.interface.orchestrator.get_orchestrator_stats.return_value = {'active_jobs': 0}
        
        result = self.interface._cancel_job("test_job")
        
        assert "cancelled successfully" in result[3]
    
    def test_cancel_job_failure(self):
        """Test job cancellation failure."""
        self.interface.orchestrator.cancel_job.return_value = False
        self.interface.orchestrator.get_orchestrator_stats.return_value = {'active_jobs': 0}
        
        result = self.interface._cancel_job("test_job")
        
        assert "Failed to cancel" in result[3]
    
    def test_retry_job_success(self):
        """Test successful job retry."""
        self.interface.orchestrator.retry_job.return_value = True
        self.interface.orchestrator.get_orchestrator_stats.return_value = {'active_jobs': 0}
        
        result = self.interface._retry_job("test_job")
        
        assert "queued for retry" in result[3]
    
    def test_retry_job_failure(self):
        """Test job retry failure."""
        self.interface.orchestrator.retry_job.return_value = False
        self.interface.orchestrator.get_orchestrator_stats.return_value = {'active_jobs': 0}
        
        result = self.interface._retry_job("test_job")
        
        assert "Failed to retry" in result[3]
    
    def test_generate_preview_no_job(self):
        """Test preview generation with no job selected."""
        result = self.interface._generate_preview(
            None, True, True, True, 1.0, "original"
        )
        
        assert "Please select a completed job" in result
    
    def test_generate_preview_success(self):
        """Test successful preview generation."""
        result = self.interface._generate_preview(
            "test_job", True, True, True, 1.5, "translated"
        )
        
        assert "Document Preview" in result
        assert "test_job" in result
        assert "1.5x" in result
        assert "translated" in result
    
    def test_get_download_info_no_job(self):
        """Test download info with no job selected."""
        result = self.interface._get_download_info(None)
        
        assert result.visible is False
    
    def test_get_download_info_job_not_completed(self):
        """Test download info for incomplete job."""
        mock_status = {
            'status': 'pending'
        }
        self.interface.orchestrator.get_job_status.return_value = mock_status
        
        result = self.interface._get_download_info("test_job")
        
        assert "not completed" in result.value["error"]
    
    def test_get_download_info_success(self):
        """Test successful download info retrieval."""
        mock_status = {
            'status': 'completed',
            'download_link_id': 'test_link_123'
        }
        self.interface.orchestrator.get_job_status.return_value = mock_status
        
        mock_download_info = {
            'filename': 'translated_document.pdf',
            'file_size': 1024,
            'format': 'pdf'
        }
        self.interface.download_service.get_download_info.return_value = mock_download_info
        
        result = self.interface._get_download_info("test_job")
        
        assert result.value == mock_download_info
        assert result.visible is True
    
    def test_handle_download_no_job(self):
        """Test download handling with no job selected."""
        status, file_update = self.interface._handle_download(None)
        
        assert "Please select a job" in status
        assert file_update.visible is False
    
    def test_handle_download_success(self):
        """Test successful download handling."""
        # Mock job status
        mock_status = {
            'status': 'completed',
            'download_link_id': 'test_link_123'
        }
        self.interface.orchestrator.get_job_status.return_value = mock_status
        
        # Mock download service
        mock_file_bytes = b"fake pdf content"
        mock_filename = "translated_document.pdf"
        mock_metadata = {
            'format': 'pdf',
            'file_size': len(mock_file_bytes)
        }
        
        self.interface.download_service.download_file.return_value = (
            True, mock_file_bytes, mock_filename, mock_metadata
        )
        
        status, file_update = self.interface._handle_download("test_job")
        
        assert "Download ready" in status
        assert mock_filename in status
        assert file_update.visible is True
        assert file_update.value is not None
    
    def test_handle_download_failure(self):
        """Test download handling failure."""
        mock_status = {
            'status': 'completed',
            'download_link_id': 'test_link_123'
        }
        self.interface.orchestrator.get_job_status.return_value = mock_status
        
        # Mock download failure
        self.interface.download_service.download_file.return_value = (
            False, None, "", {"error": "Download link expired"}
        )
        
        status, file_update = self.interface._handle_download("test_job")
        
        assert "Download failed" in status
        assert "expired" in status
        assert file_update.visible is False
    
    def test_get_system_statistics(self):
        """Test system statistics retrieval."""
        # Mock service statistics
        mock_orchestrator_stats = {'active_jobs': 2, 'completed_jobs': 10}
        mock_upload_stats = {'active_files': 1, 'total_size_bytes': 1024}
        mock_download_stats = {'active_download_links': 3}
        
        self.interface.orchestrator.get_orchestrator_stats.return_value = mock_orchestrator_stats
        self.interface.upload_service.get_upload_stats.return_value = mock_upload_stats
        self.interface.download_service.get_download_stats.return_value = mock_download_stats
        
        orch_stats, upload_stats, download_stats = self.interface._get_system_statistics()
        
        assert orch_stats == mock_orchestrator_stats
        assert upload_stats == mock_upload_stats
        assert download_stats == mock_download_stats
    
    def test_get_system_statistics_error(self):
        """Test system statistics retrieval with error."""
        # Mock service error
        self.interface.orchestrator.get_orchestrator_stats.side_effect = Exception("Service error")
        
        orch_stats, upload_stats, download_stats = self.interface._get_system_statistics()
        
        assert "error" in orch_stats
        assert "Service error" in orch_stats["error"]
    
    def test_get_custom_css(self):
        """Test custom CSS generation."""
        css = self.interface._get_custom_css()
        
        assert isinstance(css, str)
        assert ".gradio-container" in css
        assert ".progress-bar" in css
        assert ".error-message" in css
        assert ".success-message" in css
    
    def test_shutdown(self):
        """Test service shutdown."""
        self.interface.shutdown()
        
        # Verify all services are shut down
        self.interface.upload_service.shutdown.assert_called_once()
        self.interface.orchestrator.shutdown.assert_called_once()
        self.interface.download_service.shutdown.assert_called_once()


class TestWebInterfaceIntegration:
    """Integration tests for web interface."""
    
    @patch('src.web.gradio_interface.FileUploadService')
    @patch('src.web.gradio_interface.TranslationOrchestrator')
    @patch('src.web.gradio_interface.PreviewService')
    @patch('src.web.gradio_interface.DownloadService')
    def test_full_translation_workflow(self, mock_download_service, mock_preview_service,
                                     mock_orchestrator, mock_upload_service):
        """Test complete translation workflow through the interface."""
        
        # Setup mocks
        mock_upload_instance = Mock()
        mock_orchestrator_instance = Mock()
        mock_download_instance = Mock()
        
        mock_upload_service.return_value = mock_upload_instance
        mock_orchestrator.return_value = mock_orchestrator_instance
        mock_download_service.return_value = mock_download_instance
        
        # Create interface
        interface = TranslationWebInterface()
        
        # Test file upload and job submission
        mock_uploaded_file = Mock()
        mock_uploaded_file.file_id = "uploaded_file_123"
        mock_upload_instance.upload_file.return_value = (True, mock_uploaded_file, [])
        
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value="/tmp/uploaded_file.pdf")
        mock_context.__exit__ = Mock(return_value=None)
        mock_upload_instance.get_file_path.return_value = mock_context
        
        test_job_id = "translation_job_456"
        mock_orchestrator_instance.submit_translation_job.return_value = test_job_id
        
        mock_job_status = {
            'job_id': test_job_id,
            'status': 'pending',
            'overall_progress': 0.0,
            'source_language': 'en',
            'target_language': 'fr',
            'format_type': 'pdf',
            'created_at': '2024-01-01T12:00:00',
            'stages': {}
        }
        mock_orchestrator_instance.get_job_status.return_value = mock_job_status
        
        # Submit translation
        result = interface._handle_translation_submit(
            file_data=b"fake pdf data",
            format_type="pdf",
            source_lang="en",
            target_lang="fr",
            preserve_layout=True,
            quality_assessment=True
        )
        
        status, job_info, error_display, success_display = result
        
        # Verify successful submission
        assert "successfully" in status.lower()
        assert test_job_id[:8] in status
        assert job_info.value == mock_job_status
        
        # Test job monitoring
        jobs_data, job_choices = interface._refresh_jobs_table()
        assert len(jobs_data) == 1
        assert test_job_id[:8] in jobs_data[0][0]
        
        # Test job completion and download
        completed_status = mock_job_status.copy()
        completed_status.update({
            'status': 'completed',
            'overall_progress': 100.0,
            'download_link_id': 'download_link_789'
        })
        mock_orchestrator_instance.get_job_status.return_value = completed_status
        
        # Test download info
        mock_download_info = {
            'filename': 'translated_document.pdf',
            'file_size': 2048,
            'format': 'pdf'
        }
        mock_download_instance.get_download_info.return_value = mock_download_info
        
        download_info = interface._get_download_info(test_job_id)
        assert download_info.value == mock_download_info
        
        # Test actual download
        mock_file_bytes = b"translated pdf content"
        mock_download_instance.download_file.return_value = (
            True, mock_file_bytes, "translated_document.pdf", mock_download_info
        )
        
        download_status, download_file = interface._handle_download(test_job_id)
        
        assert "Download ready" in download_status
        assert download_file.visible is True
        
        print("✓ Full translation workflow test completed successfully")


if __name__ == "__main__":
    pytest.main([__file__])
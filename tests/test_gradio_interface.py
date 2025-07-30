"""Tests for the enhanced Gradio web interface."""

import pytest
import tempfile
from unittest.mock import Mock, patch

from src.web.gradio_interface import TranslationWebInterface


class TestTranslationWebInterface:
    """Test cases for the enhanced web interface."""

    def setup_method(self):
        """Set up test fixtures."""
        self.interface = TranslationWebInterface()

    def test_interface_initialization(self):
        """Test that the interface initializes correctly."""
        assert self.interface is not None
        assert hasattr(self.interface, 'upload_service')
        assert hasattr(self.interface, 'orchestrator')
        assert hasattr(self.interface, 'preview_service')
        assert hasattr(self.interface, 'download_service')

    def test_supported_languages(self):
        """Test that supported languages are properly configured."""
        assert 'en' in self.interface.languages
        assert 'fr' in self.interface.languages
        assert 'auto' in self.interface.languages
        assert len(self.interface.languages) >= 10

    def test_supported_formats(self):
        """Test that supported formats are properly configured."""
        expected_formats = ['pdf', 'docx', 'epub']
        assert all(fmt in self.interface.formats for fmt in expected_formats)

    def test_create_interface(self):
        """Test that the Gradio interface is created successfully."""
        interface = self.interface.create_interface()
        assert interface is not None

    def test_custom_css(self):
        """Test that custom CSS is properly formatted."""
        css = self.interface._get_custom_css()
        assert '.gradio-container' in css
        assert '.progress-bar' in css
        assert '.error-message' in css
        assert '.success-message' in css

    @patch('src.web.gradio_interface.FileUploadService')
    @patch('src.web.gradio_interface.TranslationOrchestrator')
    def test_translation_submit_no_file(self, mock_orchestrator, mock_upload):
        """Test translation submission with no file."""
        result = self.interface._handle_translation_submit(
            None, 'pdf', 'en', 'fr', True, True, 0.8
        )
        
        # Should return error message
        assert "Please select a file" in result[0]

    @patch('src.web.gradio_interface.FileUploadService')
    @patch('src.web.gradio_interface.TranslationOrchestrator')
    def test_translation_submit_same_languages(self, mock_orchestrator, mock_upload):
        """Test translation submission with same source and target language."""
        result = self.interface._handle_translation_submit(
            b"fake_file_data", 'pdf', 'en', 'en', True, True, 0.8
        )
        
        # Should return error message
        assert "cannot be the same" in result[0]

    def test_quality_class_mapping(self):
        """Test quality score to CSS class mapping."""
        assert self.interface._get_quality_class(0.95) == "excellent"
        assert self.interface._get_quality_class(0.85) == "good"
        assert self.interface._get_quality_class(0.75) == "fair"
        assert self.interface._get_quality_class(0.55) == "poor"
        assert self.interface._get_quality_class(0.35) == "failed"

    def test_job_details_no_job(self):
        """Test getting job details with no job selected."""
        result = self.interface._get_job_details(None)
        assert "Select a job" in result[1]

    def test_download_info_no_job(self):
        """Test getting download info with no job selected."""
        result = self.interface._get_download_info(None)
        assert "Select a completed job" in result[2]

    def test_generate_quality_report(self):
        """Test quality report generation."""
        report = self.interface._generate_quality_report("test_job_123")
        assert "Quality Report" in report
        assert "test_job_123" in report
        assert "<html>" in report

    def test_generate_metadata_file(self):
        """Test metadata file generation."""
        status = {'status': 'completed', 'progress': 100}
        metadata = self.interface._generate_metadata_file("test_job_123", status)
        
        import json
        parsed = json.loads(metadata)
        assert parsed['job_id'] == "test_job_123"
        assert parsed['status'] == status

    def test_batch_download_no_jobs(self):
        """Test batch download with no jobs selected."""
        result = self.interface._handle_batch_download([], 'pdf')
        assert "Please select jobs" in result[0]

    def test_export_statistics(self):
        """Test statistics export functionality."""
        with patch.object(self.interface.orchestrator, 'get_orchestrator_stats') as mock_stats:
            mock_stats.return_value = {'total_jobs': 5}
            
            result = self.interface._export_statistics()
            assert result.endswith('.json')

    def test_navigate_preview_page(self):
        """Test preview page navigation."""
        result = self.interface._navigate_preview_page("test_job", 1, 1)
        assert "page 2" in result[0]

    def test_pause_job_functionality(self):
        """Test job pause functionality."""
        result = self.interface._pause_job("test_job_123")
        assert "pause functionality not yet implemented" in result[2].value

    def test_interface_shutdown(self):
        """Test that interface shuts down cleanly."""
        # This should not raise any exceptions
        self.interface.shutdown()


if __name__ == "__main__":
    pytest.main([__file__])
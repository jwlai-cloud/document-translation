"""Tests for download service."""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timedelta

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, BoundingBox,
    Dimensions, DocumentMetadata
)
from src.models.layout import AdjustedRegion
from src.services.download_service import (
    DownloadService, DownloadConfig, DownloadLink, DownloadRequest,
    DownloadResult, FileNamingService, DownloadLinkManager
)


class TestDownloadConfig:
    """Test cases for DownloadConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = DownloadConfig()
        
        assert config.temp_storage_duration == 1800  # 30 minutes
        assert config.temp_storage_path is not None
        assert config.max_concurrent_downloads == 5
        assert config.secure_links is True
        assert config.link_expiration_time == 3600  # 1 hour
        assert config.cleanup_interval == 300  # 5 minutes
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = DownloadConfig(
            temp_storage_duration=3600,  # 1 hour
            max_concurrent_downloads=10,
            secure_links=False,
            link_expiration_time=1800  # 30 minutes
        )
        
        assert config.temp_storage_duration == 3600
        assert config.max_concurrent_downloads == 10
        assert config.secure_links is False
        assert config.link_expiration_time == 1800


class TestDownloadLink:
    """Test cases for DownloadLink."""
    
    def test_download_link_creation(self):
        """Test DownloadLink creation and properties."""
        now = datetime.now()
        expires_at = now + timedelta(hours=1)
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name
        
        try:
            download_link = DownloadLink(
                link_id="test_link",
                file_path=temp_file_path,
                original_filename="test.pdf",
                file_format="pdf",
                file_size=12,
                file_hash="abc123",
                created_at=now,
                expires_at=expires_at,
                max_downloads=3
            )
            
            assert download_link.link_id == "test_link"
            assert download_link.original_filename == "test.pdf"
            assert download_link.file_format == "pdf"
            assert download_link.download_count == 0
            assert download_link.max_downloads == 3
            assert download_link.is_expired is False
            assert download_link.is_exhausted is False
            assert download_link.is_valid is True
        finally:
            os.unlink(temp_file_path)
    
    def test_download_link_expiration(self):
        """Test download link expiration logic."""
        past_time = datetime.now() - timedelta(hours=1)
        
        download_link = DownloadLink(
            link_id="expired_link",
            file_path="/nonexistent/path",
            original_filename="test.pdf",
            file_format="pdf",
            file_size=0,
            file_hash="",
            created_at=past_time,
            expires_at=past_time
        )
        
        assert download_link.is_expired is True
        assert download_link.is_valid is False
    
    def test_download_link_exhaustion(self):
        """Test download link exhaustion logic."""
        now = datetime.now()
        
        download_link = DownloadLink(
            link_id="exhausted_link",
            file_path="/nonexistent/path",
            original_filename="test.pdf",
            file_format="pdf",
            file_size=0,
            file_hash="",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            download_count=2,
            max_downloads=2
        )
        
        assert download_link.is_exhausted is True
        assert download_link.is_valid is False


class TestFileNamingService:
    """Test cases for FileNamingService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_document = DocumentStructure(
            format="pdf",
            pages=[],
            metadata=DocumentMetadata(title="Test Document")
        )
    
    def test_generate_filename_basic(self):
        """Test basic filename generation."""
        filename = FileNamingService.generate_filename(
            self.test_document,
            "pdf",
            include_timestamp=False,
            include_language_info=False
        )
        
        assert filename == "Test_Document.pdf"
    
    def test_generate_filename_with_prefix(self):
        """Test filename generation with prefix."""
        filename = FileNamingService.generate_filename(
            self.test_document,
            "pdf",
            prefix="translated",
            include_timestamp=False,
            include_language_info=False
        )
        
        assert filename == "translated_Test_Document.pdf"
    
    def test_generate_filename_with_language_info(self):
        """Test filename generation with language information."""
        filename = FileNamingService.generate_filename(
            self.test_document,
            "pdf",
            include_timestamp=False,
            include_language_info=True
        )
        
        assert filename == "Test_Document_translated.pdf"
    
    def test_generate_filename_with_timestamp(self):
        """Test filename generation with timestamp."""
        filename = FileNamingService.generate_filename(
            self.test_document,
            "pdf",
            include_timestamp=True,
            include_language_info=False
        )
        
        # Should contain timestamp pattern
        assert "Test_Document_" in filename
        assert filename.endswith(".pdf")
        assert len(filename) > len("Test_Document.pdf")
    
    def test_generate_filename_no_title(self):
        """Test filename generation with no document title."""
        document_no_title = DocumentStructure(
            format="pdf",
            pages=[],
            metadata=DocumentMetadata()
        )
        
        filename = FileNamingService.generate_filename(
            document_no_title,
            "pdf",
            include_timestamp=False,
            include_language_info=False
        )
        
        assert filename == "translated_document.pdf"
    
    def test_clean_filename(self):
        """Test filename cleaning."""
        dirty_filename = "Test<>Document:/\\|?*"
        clean_filename = FileNamingService._clean_filename(dirty_filename)
        
        assert clean_filename == "Test_Document"
        assert "<" not in clean_filename
        assert ">" not in clean_filename
        assert ":" not in clean_filename
    
    def test_clean_filename_empty(self):
        """Test filename cleaning with empty input."""
        clean_filename = FileNamingService._clean_filename("")
        assert clean_filename == "document"
    
    def test_clean_filename_long(self):
        """Test filename cleaning with very long input."""
        long_filename = "a" * 150
        clean_filename = FileNamingService._clean_filename(long_filename)
        
        assert len(clean_filename) <= 100
    
    def test_get_extension_for_format(self):
        """Test file extension mapping."""
        assert FileNamingService._get_extension_for_format("pdf") == "pdf"
        assert FileNamingService._get_extension_for_format("docx") == "docx"
        assert FileNamingService._get_extension_for_format("epub") == "epub"
        assert FileNamingService._get_extension_for_format("unknown") == "unknown"


class TestDownloadLinkManager:
    """Test cases for DownloadLinkManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = DownloadConfig(cleanup_interval=1)  # Fast cleanup for testing
        self.manager = DownloadLinkManager(self.config)
    
    def teardown_method(self):
        """Clean up after tests."""
        self.manager.shutdown()
    
    def test_create_download_link(self):
        """Test download link creation."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name
        
        try:
            download_link = self.manager.create_download_link(
                temp_file_path,
                "test.pdf",
                "pdf"
            )
            
            assert download_link.link_id is not None
            assert download_link.file_path == temp_file_path
            assert download_link.original_filename == "test.pdf"
            assert download_link.file_format == "pdf"
            assert download_link.file_size > 0
            assert download_link.file_hash != ""
            assert download_link.is_valid is True
            
            # Verify link is stored
            retrieved_link = self.manager.get_download_link(download_link.link_id)
            assert retrieved_link is not None
            assert retrieved_link.link_id == download_link.link_id
        finally:
            os.unlink(temp_file_path)
    
    def test_get_download_link_nonexistent(self):
        """Test getting non-existent download link."""
        retrieved_link = self.manager.get_download_link("nonexistent")
        assert retrieved_link is None
    
    def test_record_download(self):
        """Test recording download attempts."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name
        
        try:
            download_link = self.manager.create_download_link(
                temp_file_path,
                "test.pdf",
                "pdf",
                max_downloads=2
            )
            
            # Record first download
            success = self.manager.record_download(download_link.link_id)
            assert success is True
            
            retrieved_link = self.manager.get_download_link(download_link.link_id)
            assert retrieved_link.download_count == 1
            assert retrieved_link.is_valid is True
            
            # Record second download (should exhaust the link)
            success = self.manager.record_download(download_link.link_id)
            assert success is True
            
            # Link should be cleaned up after exhaustion
            retrieved_link = self.manager.get_download_link(download_link.link_id)
            assert retrieved_link is None
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def test_cleanup_link(self):
        """Test manual link cleanup."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name
        
        download_link = self.manager.create_download_link(
            temp_file_path,
            "test.pdf",
            "pdf"
        )
        
        # Verify file exists
        assert os.path.exists(temp_file_path)
        
        # Clean up link
        success = self.manager.cleanup_link(download_link.link_id)
        assert success is True
        
        # Verify file is removed
        assert not os.path.exists(temp_file_path)
        
        # Verify link is removed
        retrieved_link = self.manager.get_download_link(download_link.link_id)
        assert retrieved_link is None
    
    def test_cleanup_expired_links(self):
        """Test cleanup of expired links."""
        # Create expired link
        past_time = datetime.now() - timedelta(hours=1)
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name
        
        expired_link = DownloadLink(
            link_id="expired_test",
            file_path=temp_file_path,
            original_filename="test.pdf",
            file_format="pdf",
            file_size=12,
            file_hash="abc123",
            created_at=past_time,
            expires_at=past_time
        )
        
        self.manager.download_links["expired_test"] = expired_link
        
        # Run cleanup
        cleaned_count = self.manager.cleanup_expired_links()
        
        assert cleaned_count == 1
        assert "expired_test" not in self.manager.download_links
        assert not os.path.exists(temp_file_path)
    
    def test_generate_secure_link_id(self):
        """Test secure link ID generation."""
        # Test secure mode
        self.manager.config.secure_links = True
        secure_id = self.manager._generate_secure_link_id()
        
        assert isinstance(secure_id, str)
        assert len(secure_id) == 64  # SHA-256 hex digest length
        
        # Test non-secure mode
        self.manager.config.secure_links = False
        non_secure_id = self.manager._generate_secure_link_id()
        
        assert isinstance(non_secure_id, str)
        assert len(non_secure_id) == 36  # UUID length with hyphens
    
    def test_calculate_file_hash(self):
        """Test file hash calculation."""
        test_content = b"Hello, World!"
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name
        
        try:
            file_hash = self.manager._calculate_file_hash(temp_file_path)
            
            assert isinstance(file_hash, str)
            assert len(file_hash) == 64  # SHA-256 hex digest length
            # Verify it's the correct hash for "Hello, World!"
            expected_hash = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
            assert file_hash == expected_hash
        finally:
            os.unlink(temp_file_path)
    
    def test_calculate_file_hash_nonexistent(self):
        """Test file hash calculation for non-existent file."""
        file_hash = self.manager._calculate_file_hash("/nonexistent/file")
        assert file_hash == ""


class TestDownloadService:
    """Test cases for DownloadService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = DownloadConfig()
        self.service = DownloadService(self.config)
        
        # Create test document
        self.test_document = DocumentStructure(
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
        
        # Create test translated regions
        self.translated_regions = {
            "1": [
                AdjustedRegion(
                    original_region=self.test_document.pages[0].text_regions[0],
                    adjusted_text="Contenu de test",
                    new_bounding_box=BoundingBox(10, 10, 220, 35),
                    adjustments=[],
                    fit_quality=0.9
                )
            ]
        }
    
    def teardown_method(self):
        """Clean up after tests."""
        self.service.shutdown()
    
    @patch('src.services.download_service.DefaultLayoutReconstructionEngine')
    def test_prepare_download_success(self, mock_reconstruction_engine):
        """Test successful download preparation."""
        # Mock reconstruction engine
        mock_engine = Mock()
        mock_engine.reconstruct_document.return_value = b"reconstructed document content"
        mock_reconstruction_engine.return_value = mock_engine
        
        # Create download request
        download_request = DownloadRequest(
            request_id="test_request",
            document=self.test_document,
            translated_regions=self.translated_regions,
            target_format="pdf",
            filename_prefix="translated"
        )
        
        # Prepare download
        result = self.service.prepare_download(download_request)
        
        assert result.success is True
        assert result.download_link is not None
        assert result.error_message == ""
        assert result.processing_time > 0
        
        # Verify download link properties
        download_link = result.download_link
        assert download_link.file_format == "pdf"
        assert "translated" in download_link.original_filename
        assert "Test_Document" in download_link.original_filename
        assert download_link.file_size > 0
        assert os.path.exists(download_link.file_path)
    
    def test_prepare_download_concurrent_limit(self):
        """Test download preparation with concurrent limit."""
        # Set low concurrent limit for testing
        self.service.config.max_concurrent_downloads = 1
        self.service.download_semaphore = threading.Semaphore(1)
        
        # Acquire the semaphore to simulate concurrent download
        self.service.download_semaphore.acquire()
        
        try:
            download_request = DownloadRequest(
                request_id="test_request",
                document=self.test_document,
                translated_regions=self.translated_regions,
                target_format="pdf"
            )
            
            result = self.service.prepare_download(download_request)
            
            assert result.success is False
            assert "too many concurrent" in result.error_message.lower()
        finally:
            self.service.download_semaphore.release()
    
    def test_get_download_info(self):
        """Test getting download information."""
        # Create a download link first
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name
        
        try:
            download_link = self.service.link_manager.create_download_link(
                temp_file_path,
                "test.pdf",
                "pdf"
            )
            
            # Get download info
            info = self.service.get_download_info(download_link.link_id)
            
            assert info is not None
            assert info['link_id'] == download_link.link_id
            assert info['filename'] == "test.pdf"
            assert info['format'] == "pdf"
            assert info['file_size'] > 0
            assert info['download_count'] == 0
            assert info['is_valid'] is True
            assert info['time_remaining'] > 0
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def test_get_download_info_nonexistent(self):
        """Test getting download information for non-existent link."""
        info = self.service.get_download_info("nonexistent")
        assert info is None
    
    def test_download_file_success(self):
        """Test successful file download."""
        test_content = b"test document content"
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name
        
        try:
            download_link = self.service.link_manager.create_download_link(
                temp_file_path,
                "test.pdf",
                "pdf"
            )
            
            # Download file
            success, file_bytes, filename, metadata = self.service.download_file(download_link.link_id)
            
            assert success is True
            assert file_bytes == test_content
            assert filename == "test.pdf"
            assert metadata['format'] == "pdf"
            assert metadata['file_size'] == len(test_content)
            assert metadata['download_count'] == 1
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def test_download_file_nonexistent_link(self):
        """Test downloading with non-existent link."""
        success, file_bytes, filename, metadata = self.service.download_file("nonexistent")
        
        assert success is False
        assert file_bytes is None
        assert filename == ""
        assert "not found" in metadata['error'].lower()
    
    def test_cancel_download(self):
        """Test download cancellation."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name
        
        download_link = self.service.link_manager.create_download_link(
            temp_file_path,
            "test.pdf",
            "pdf"
        )
        
        # Cancel download
        success = self.service.cancel_download(download_link.link_id)
        
        assert success is True
        assert not os.path.exists(temp_file_path)
        assert self.service.get_download_info(download_link.link_id) is None
    
    def test_get_download_stats(self):
        """Test getting download service statistics."""
        stats = self.service.get_download_stats()
        
        assert 'active_download_links' in stats
        assert 'total_storage_size_bytes' in stats
        assert 'temp_storage_path' in stats
        assert 'link_expiration_time_seconds' in stats
        assert 'max_concurrent_downloads' in stats
        assert 'cleanup_interval_seconds' in stats
        
        assert stats['active_download_links'] == 0  # No downloads yet
        assert stats['max_concurrent_downloads'] == self.config.max_concurrent_downloads
    
    def test_cleanup_expired_downloads(self):
        """Test manual cleanup of expired downloads."""
        # Initially no downloads to clean up
        cleaned_count = self.service.cleanup_expired_downloads()
        assert cleaned_count == 0
        
        # Create expired download link
        past_time = datetime.now() - timedelta(hours=1)
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name
        
        expired_link = DownloadLink(
            link_id="expired_test",
            file_path=temp_file_path,
            original_filename="test.pdf",
            file_format="pdf",
            file_size=12,
            file_hash="abc123",
            created_at=past_time,
            expires_at=past_time
        )
        
        self.service.link_manager.download_links["expired_test"] = expired_link
        
        # Run cleanup
        cleaned_count = self.service.cleanup_expired_downloads()
        
        assert cleaned_count == 1
        assert not os.path.exists(temp_file_path)


class TestIntegration:
    """Integration tests for download service."""
    
    def test_full_download_workflow(self):
        """Test complete download workflow."""
        service = DownloadService()
        
        try:
            # Create comprehensive test document
            text_regions = [
                TextRegion(
                    id="title",
                    bounding_box=BoundingBox(50, 50, 300, 40),
                    text_content="Document Title"
                ),
                TextRegion(
                    id="paragraph",
                    bounding_box=BoundingBox(50, 120, 300, 60),
                    text_content="This is a test paragraph."
                )
            ]
            
            document = DocumentStructure(
                format="pdf",
                pages=[
                    PageStructure(
                        page_number=1,
                        dimensions=Dimensions(width=400, height=600),
                        text_regions=text_regions
                    )
                ],
                metadata=DocumentMetadata(title="Integration Test Document")
            )
            
            # Create translated regions
            translated_regions = {
                "1": [
                    AdjustedRegion(
                        original_region=text_regions[0],
                        adjusted_text="Titre du Document",
                        new_bounding_box=BoundingBox(50, 50, 320, 45),
                        adjustments=[],
                        fit_quality=0.9
                    ),
                    AdjustedRegion(
                        original_region=text_regions[1],
                        adjusted_text="Ceci est un paragraphe de test.",
                        new_bounding_box=BoundingBox(50, 120, 330, 65),
                        adjustments=[],
                        fit_quality=0.85
                    )
                ]
            }
            
            # Create download request
            download_request = DownloadRequest(
                request_id="integration_test",
                document=document,
                translated_regions=translated_regions,
                target_format="pdf",
                filename_prefix="translated"
            )
            
            # Mock reconstruction engine for integration test
            with patch('src.services.download_service.DefaultLayoutReconstructionEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.reconstruct_document.return_value = b"Mock reconstructed PDF content"
                mock_engine_class.return_value = mock_engine
                
                # Prepare download
                result = service.prepare_download(download_request)
                
                assert result.success is True
                assert result.download_link is not None
                
                download_link = result.download_link
                
                # Get download info
                info = service.get_download_info(download_link.link_id)
                assert info is not None
                assert info['is_valid'] is True
                
                # Download file
                success, file_bytes, filename, metadata = service.download_file(download_link.link_id)
                
                assert success is True
                assert file_bytes == b"Mock reconstructed PDF content"
                assert "translated" in filename
                assert "Integration_Test_Document" in filename
                assert filename.endswith(".pdf")
                
                # Verify download was recorded
                info_after = service.get_download_info(download_link.link_id)
                # Link should be cleaned up after single download
                assert info_after is None
                
                print("✓ Full download workflow completed successfully")
        
        finally:
            service.shutdown()


if __name__ == "__main__":
    pytest.main([__file__])
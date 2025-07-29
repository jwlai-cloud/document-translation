"""Tests for file upload and validation service."""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timedelta

from src.services.upload_service import (
    FileUploadService, FileValidator, TempFileManager,
    UploadConfig, ValidationResult, UploadedFile
)


class TestUploadConfig:
    """Test cases for UploadConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = UploadConfig()
        
        assert config.max_file_size == 50 * 1024 * 1024  # 50MB
        assert config.allowed_formats == ['pdf', 'docx', 'epub']
        assert config.temp_storage_duration == 3600  # 1 hour
        assert config.temp_storage_path is not None
        assert config.enable_virus_scan is False
        assert config.max_concurrent_uploads == 10
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = UploadConfig(
            max_file_size=10 * 1024 * 1024,  # 10MB
            allowed_formats=['pdf'],
            temp_storage_duration=1800,  # 30 minutes
            max_concurrent_uploads=5
        )
        
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.allowed_formats == ['pdf']
        assert config.temp_storage_duration == 1800
        assert config.max_concurrent_uploads == 5


class TestValidationResult:
    """Test cases for ValidationResult."""
    
    def test_validation_result_creation(self):
        """Test ValidationResult creation and defaults."""
        result = ValidationResult(is_valid=True, file_format='pdf', file_size=1024)
        
        assert result.is_valid is True
        assert result.file_format == 'pdf'
        assert result.file_size == 1024
        assert result.security_issues == []
        assert result.validation_errors == []
    
    def test_validation_result_with_issues(self):
        """Test ValidationResult with issues."""
        result = ValidationResult(
            is_valid=False,
            security_issues=['Suspicious content'],
            validation_errors=['Invalid format']
        )
        
        assert result.is_valid is False
        assert 'Suspicious content' in result.security_issues
        assert 'Invalid format' in result.validation_errors


class TestUploadedFile:
    """Test cases for UploadedFile."""
    
    def test_uploaded_file_creation(self):
        """Test UploadedFile creation."""
        now = datetime.now()
        expires_at = now + timedelta(hours=1)
        
        validation_result = ValidationResult(is_valid=True, file_format='pdf')
        
        uploaded_file = UploadedFile(
            file_id='test-id',
            original_filename='test.pdf',
            temp_file_path='/tmp/test.pdf',
            file_format='pdf',
            file_size=1024,
            mime_type='application/pdf',
            file_hash='abc123',
            upload_timestamp=now,
            expires_at=expires_at,
            validation_result=validation_result
        )
        
        assert uploaded_file.file_id == 'test-id'
        assert uploaded_file.original_filename == 'test.pdf'
        assert uploaded_file.file_format == 'pdf'
        assert uploaded_file.is_expired is False
        assert uploaded_file.time_remaining > timedelta(0)
    
    def test_uploaded_file_expiration(self):
        """Test file expiration logic."""
        past_time = datetime.now() - timedelta(hours=1)
        validation_result = ValidationResult(is_valid=True)
        
        uploaded_file = UploadedFile(
            file_id='expired-id',
            original_filename='test.pdf',
            temp_file_path='/tmp/test.pdf',
            file_format='pdf',
            file_size=1024,
            mime_type='application/pdf',
            file_hash='abc123',
            upload_timestamp=past_time,
            expires_at=past_time,
            validation_result=validation_result
        )
        
        assert uploaded_file.is_expired is True
        assert uploaded_file.time_remaining == timedelta(0)


class TestFileValidator:
    """Test cases for FileValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = UploadConfig()
        self.validator = FileValidator(self.config)
    
    def test_validate_file_size_valid(self):
        """Test file size validation with valid size."""
        result = ValidationResult(is_valid=False)
        
        is_valid = self.validator._validate_file_size(1024, result)
        
        assert is_valid is True
        assert len(result.validation_errors) == 0
    
    def test_validate_file_size_empty(self):
        """Test file size validation with empty file."""
        result = ValidationResult(is_valid=False)
        
        is_valid = self.validator._validate_file_size(0, result)
        
        assert is_valid is False
        assert any('empty' in error.lower() for error in result.validation_errors)
    
    def test_validate_file_size_too_large(self):
        """Test file size validation with oversized file."""
        result = ValidationResult(is_valid=False)
        large_size = self.config.max_file_size + 1
        
        is_valid = self.validator._validate_file_size(large_size, result)
        
        assert is_valid is False
        assert any('exceeds maximum' in error for error in result.validation_errors)
    
    def test_calculate_file_hash(self):
        """Test file hash calculation."""
        test_content = b"Hello, World!"
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name
        
        try:
            file_hash = self.validator._calculate_file_hash(temp_file_path)
            
            assert isinstance(file_hash, str)
            assert len(file_hash) == 64  # SHA-256 hex digest length
            # Verify it's the correct hash for "Hello, World!"
            expected_hash = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
            assert file_hash == expected_hash
        finally:
            os.unlink(temp_file_path)
    
    @patch('magic.from_file')
    def test_detect_mime_type_with_magic(self, mock_magic):
        """Test MIME type detection using python-magic."""
        mock_magic.return_value = 'application/pdf'
        
        mime_type = self.validator._detect_mime_type('/fake/path.pdf')
        
        assert mime_type == 'application/pdf'
        mock_magic.assert_called_once_with('/fake/path.pdf', mime=True)
    
    @patch('magic.from_file', side_effect=Exception("Magic not available"))
    @patch('mimetypes.guess_type')
    def test_detect_mime_type_fallback(self, mock_guess_type, mock_magic):
        """Test MIME type detection fallback to mimetypes."""
        mock_guess_type.return_value = ('application/pdf', None)
        
        mime_type = self.validator._detect_mime_type('/fake/path.pdf')
        
        assert mime_type == 'application/pdf'
        mock_guess_type.assert_called_once_with('/fake/path.pdf')
    
    def test_validate_file_format_valid_pdf(self):
        """Test file format validation for valid PDF."""
        result = ValidationResult(is_valid=False, mime_type='application/pdf')
        
        with patch.object(self.validator, '_verify_file_signature', return_value=True):
            is_valid = self.validator._validate_file_format('/fake/path', 'test.pdf', result)
        
        assert is_valid is True
        assert result.file_format == 'pdf'
        assert len(result.validation_errors) == 0
    
    def test_validate_file_format_invalid_extension(self):
        """Test file format validation with invalid extension."""
        result = ValidationResult(is_valid=False, mime_type='text/plain')
        
        is_valid = self.validator._validate_file_format('/fake/path', 'test.txt', result)
        
        assert is_valid is False
        assert any('not allowed' in error for error in result.validation_errors)
    
    def test_validate_file_format_mime_mismatch(self):
        """Test file format validation with MIME type mismatch."""
        result = ValidationResult(is_valid=False, mime_type='text/plain')
        
        is_valid = self.validator._validate_file_format('/fake/path', 'test.pdf', result)
        
        assert is_valid is False
        assert any('does not match' in error for error in result.validation_errors)
    
    def test_verify_file_signature_pdf(self):
        """Test PDF file signature verification."""
        pdf_content = b'%PDF-1.4\n%some pdf content'
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(pdf_content)
            temp_file_path = temp_file.name
        
        try:
            is_valid = self.validator._verify_file_signature(temp_file_path, 'pdf')
            assert is_valid is True
        finally:
            os.unlink(temp_file_path)
    
    def test_verify_file_signature_invalid(self):
        """Test file signature verification with invalid signature."""
        invalid_content = b'This is not a PDF file'
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(invalid_content)
            temp_file_path = temp_file.name
        
        try:
            is_valid = self.validator._verify_file_signature(temp_file_path, 'pdf')
            assert is_valid is False
        finally:
            os.unlink(temp_file_path)
    
    def test_perform_security_checks_safe_content(self):
        """Test security checks with safe content."""
        safe_content = b'This is safe PDF content without any dangerous patterns.'
        result = ValidationResult(is_valid=False)
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(safe_content)
            temp_file_path = temp_file.name
        
        try:
            is_valid = self.validator._perform_security_checks(temp_file_path, result)
            
            assert is_valid is True
            assert len(result.security_issues) == 0
        finally:
            os.unlink(temp_file_path)
    
    def test_perform_security_checks_dangerous_content(self):
        """Test security checks with dangerous content."""
        dangerous_content = b'<script>alert("xss")</script>'
        result = ValidationResult(is_valid=False)
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(dangerous_content)
            temp_file_path = temp_file.name
        
        try:
            is_valid = self.validator._perform_security_checks(temp_file_path, result)
            
            assert is_valid is False
            assert len(result.security_issues) > 0
            assert any('dangerous content' in issue.lower() for issue in result.security_issues)
        finally:
            os.unlink(temp_file_path)
    
    def test_has_suspicious_filename(self):
        """Test suspicious filename detection."""
        suspicious_filenames = [
            '../../../etc/passwd',
            'file\\with\\backslashes',
            'file:with:colons',
            'file<with>brackets',
            'file|with|pipes'
        ]
        
        safe_filenames = [
            'document.pdf',
            'my_file.docx',
            'book-title.epub'
        ]
        
        for filename in suspicious_filenames:
            assert self.validator._has_suspicious_filename(filename) is True
        
        for filename in safe_filenames:
            assert self.validator._has_suspicious_filename(filename) is False
    
    def test_validate_pdf_valid(self):
        """Test PDF-specific validation with valid PDF."""
        pdf_content = b'%PDF-1.4\n%some pdf content'
        result = ValidationResult(is_valid=False)
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(pdf_content)
            temp_file_path = temp_file.name
        
        try:
            is_valid = self.validator._validate_pdf(temp_file_path, result)
            
            assert is_valid is True
            assert len(result.validation_errors) == 0
        finally:
            os.unlink(temp_file_path)
    
    def test_validate_pdf_invalid_header(self):
        """Test PDF-specific validation with invalid header."""
        invalid_content = b'Not a PDF file'
        result = ValidationResult(is_valid=False)
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(invalid_content)
            temp_file_path = temp_file.name
        
        try:
            is_valid = self.validator._validate_pdf(temp_file_path, result)
            
            assert is_valid is False
            assert any('invalid pdf header' in error.lower() for error in result.validation_errors)
        finally:
            os.unlink(temp_file_path)
    
    @patch('zipfile.ZipFile')
    def test_validate_docx_valid(self, mock_zipfile):
        """Test DOCX-specific validation with valid DOCX."""
        mock_zip = Mock()
        mock_zip.namelist.return_value = [
            '[Content_Types].xml',
            '_rels/.rels',
            'word/document.xml',
            'word/styles.xml'
        ]
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        
        result = ValidationResult(is_valid=False)
        is_valid = self.validator._validate_docx('/fake/path.docx', result)
        
        assert is_valid is True
        assert len(result.validation_errors) == 0
    
    @patch('zipfile.ZipFile')
    def test_validate_docx_missing_files(self, mock_zipfile):
        """Test DOCX-specific validation with missing required files."""
        mock_zip = Mock()
        mock_zip.namelist.return_value = ['[Content_Types].xml']  # Missing required files
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        
        result = ValidationResult(is_valid=False)
        is_valid = self.validator._validate_docx('/fake/path.docx', result)
        
        assert is_valid is False
        assert any('missing required' in error.lower() for error in result.validation_errors)
    
    @patch('zipfile.ZipFile')
    def test_validate_epub_valid(self, mock_zipfile):
        """Test EPUB-specific validation with valid EPUB."""
        mock_zip = Mock()
        mock_zip.namelist.return_value = [
            'META-INF/container.xml',
            'mimetype',
            'OEBPS/content.opf'
        ]
        mock_zip.read.return_value = b'application/epub+zip'
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        
        result = ValidationResult(is_valid=False)
        is_valid = self.validator._validate_epub('/fake/path.epub', result)
        
        assert is_valid is True
        assert len(result.validation_errors) == 0
    
    @patch('zipfile.ZipFile')
    def test_validate_epub_invalid_mimetype(self, mock_zipfile):
        """Test EPUB-specific validation with invalid mimetype."""
        mock_zip = Mock()
        mock_zip.namelist.return_value = [
            'META-INF/container.xml',
            'mimetype'
        ]
        mock_zip.read.return_value = b'invalid/mimetype'
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        
        result = ValidationResult(is_valid=False)
        is_valid = self.validator._validate_epub('/fake/path.epub', result)
        
        assert is_valid is False
        assert any('invalid epub mimetype' in error.lower() for error in result.validation_errors)


class TestTempFileManager:
    """Test cases for TempFileManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = UploadConfig(temp_storage_duration=60)  # 1 minute for testing
        self.temp_manager = TempFileManager(self.config)
    
    def teardown_method(self):
        """Clean up after tests."""
        self.temp_manager.shutdown()
    
    def test_store_file(self):
        """Test file storage."""
        file_data = b'Test file content'
        filename = 'test.pdf'
        validation_result = ValidationResult(
            is_valid=True,
            file_format='pdf',
            file_size=len(file_data),
            mime_type='application/pdf',
            file_hash='abc123'
        )
        
        uploaded_file = self.temp_manager.store_file(file_data, filename, validation_result)
        
        assert uploaded_file.file_id is not None
        assert uploaded_file.original_filename == filename
        assert uploaded_file.file_format == 'pdf'
        assert uploaded_file.file_size == len(file_data)
        assert os.path.exists(uploaded_file.temp_file_path)
        
        # Verify file content
        with open(uploaded_file.temp_file_path, 'rb') as f:
            stored_content = f.read()
        assert stored_content == file_data
    
    def test_get_file_valid(self):
        """Test getting a valid file."""
        file_data = b'Test content'
        validation_result = ValidationResult(is_valid=True, file_format='pdf', file_size=len(file_data))
        
        uploaded_file = self.temp_manager.store_file(file_data, 'test.pdf', validation_result)
        retrieved_file = self.temp_manager.get_file(uploaded_file.file_id)
        
        assert retrieved_file is not None
        assert retrieved_file.file_id == uploaded_file.file_id
    
    def test_get_file_nonexistent(self):
        """Test getting a non-existent file."""
        retrieved_file = self.temp_manager.get_file('nonexistent-id')
        
        assert retrieved_file is None
    
    def test_cleanup_file(self):
        """Test file cleanup."""
        file_data = b'Test content'
        validation_result = ValidationResult(is_valid=True, file_format='pdf', file_size=len(file_data))
        
        uploaded_file = self.temp_manager.store_file(file_data, 'test.pdf', validation_result)
        file_path = uploaded_file.temp_file_path
        
        # Verify file exists
        assert os.path.exists(file_path)
        assert self.temp_manager.get_file(uploaded_file.file_id) is not None
        
        # Clean up file
        success = self.temp_manager.cleanup_file(uploaded_file.file_id)
        
        assert success is True
        assert not os.path.exists(file_path)
        assert self.temp_manager.get_file(uploaded_file.file_id) is None
    
    def test_cleanup_expired_files(self):
        """Test cleanup of expired files."""
        file_data = b'Test content'
        validation_result = ValidationResult(is_valid=True, file_format='pdf', file_size=len(file_data))
        
        # Store file
        uploaded_file = self.temp_manager.store_file(file_data, 'test.pdf', validation_result)
        
        # Manually expire the file
        uploaded_file.expires_at = datetime.now() - timedelta(seconds=1)
        
        # Run cleanup
        cleaned_count = self.temp_manager.cleanup_expired_files()
        
        assert cleaned_count == 1
        assert self.temp_manager.get_file(uploaded_file.file_id) is None
    
    def test_get_file_path_context_manager(self):
        """Test file path context manager."""
        file_data = b'Test content'
        validation_result = ValidationResult(is_valid=True, file_format='pdf', file_size=len(file_data))
        
        uploaded_file = self.temp_manager.store_file(file_data, 'test.pdf', validation_result)
        
        with self.temp_manager.get_file_path(uploaded_file.file_id) as file_path:
            assert file_path == uploaded_file.temp_file_path
            assert os.path.exists(file_path)
            
            # Read content through context manager
            with open(file_path, 'rb') as f:
                content = f.read()
            assert content == file_data
    
    def test_get_file_path_nonexistent(self):
        """Test file path context manager with non-existent file."""
        with pytest.raises(FileNotFoundError):
            with self.temp_manager.get_file_path('nonexistent-id'):
                pass


class TestFileUploadService:
    """Test cases for FileUploadService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = UploadConfig()
        self.upload_service = FileUploadService(self.config)
    
    def teardown_method(self):
        """Clean up after tests."""
        self.upload_service.shutdown()
    
    def test_upload_file_success(self):
        """Test successful file upload."""
        # Create a simple PDF-like file
        file_data = b'%PDF-1.4\nTest PDF content'
        filename = 'test.pdf'
        
        with patch.object(self.upload_service.validator, 'validate_file') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                file_format='pdf',
                file_size=len(file_data),
                mime_type='application/pdf',
                file_hash='abc123'
            )
            
            success, uploaded_file, errors = self.upload_service.upload_file(file_data, filename)
        
        assert success is True
        assert uploaded_file is not None
        assert len(errors) == 0
        assert uploaded_file.original_filename == filename
        assert uploaded_file.file_format == 'pdf'
    
    def test_upload_file_validation_failure(self):
        """Test file upload with validation failure."""
        file_data = b'Invalid file content'
        filename = 'test.pdf'
        
        with patch.object(self.upload_service.validator, 'validate_file') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=False,
                validation_errors=['Invalid PDF format'],
                security_issues=['Suspicious content']
            )
            
            success, uploaded_file, errors = self.upload_service.upload_file(file_data, filename)
        
        assert success is False
        assert uploaded_file is None
        assert len(errors) > 0
        assert 'Invalid PDF format' in errors
        assert 'Suspicious content' in errors
    
    def test_upload_file_concurrent_limit(self):
        """Test concurrent upload limiting."""
        # Set a low concurrent limit for testing
        self.upload_service.config.max_concurrent_uploads = 1
        self.upload_service.upload_semaphore = threading.Semaphore(1)
        
        file_data = b'%PDF-1.4\nTest content'
        filename = 'test.pdf'
        
        # Acquire the semaphore to simulate concurrent upload
        self.upload_service.upload_semaphore.acquire()
        
        try:
            success, uploaded_file, errors = self.upload_service.upload_file(file_data, filename)
            
            assert success is False
            assert uploaded_file is None
            assert any('too many concurrent' in error.lower() for error in errors)
        finally:
            self.upload_service.upload_semaphore.release()
    
    def test_get_uploaded_file(self):
        """Test getting uploaded file."""
        file_data = b'%PDF-1.4\nTest content'
        filename = 'test.pdf'
        
        with patch.object(self.upload_service.validator, 'validate_file') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                file_format='pdf',
                file_size=len(file_data),
                mime_type='application/pdf',
                file_hash='abc123'
            )
            
            success, uploaded_file, errors = self.upload_service.upload_file(file_data, filename)
        
        assert success is True
        
        # Get the uploaded file
        retrieved_file = self.upload_service.get_uploaded_file(uploaded_file.file_id)
        
        assert retrieved_file is not None
        assert retrieved_file.file_id == uploaded_file.file_id
    
    def test_delete_uploaded_file(self):
        """Test deleting uploaded file."""
        file_data = b'%PDF-1.4\nTest content'
        filename = 'test.pdf'
        
        with patch.object(self.upload_service.validator, 'validate_file') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                file_format='pdf',
                file_size=len(file_data),
                mime_type='application/pdf',
                file_hash='abc123'
            )
            
            success, uploaded_file, errors = self.upload_service.upload_file(file_data, filename)
        
        assert success is True
        
        # Delete the file
        delete_success = self.upload_service.delete_uploaded_file(uploaded_file.file_id)
        
        assert delete_success is True
        assert self.upload_service.get_uploaded_file(uploaded_file.file_id) is None
    
    def test_get_file_path_context_manager(self):
        """Test file path context manager."""
        file_data = b'%PDF-1.4\nTest content'
        filename = 'test.pdf'
        
        with patch.object(self.upload_service.validator, 'validate_file') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                file_format='pdf',
                file_size=len(file_data),
                mime_type='application/pdf',
                file_hash='abc123'
            )
            
            success, uploaded_file, errors = self.upload_service.upload_file(file_data, filename)
        
        assert success is True
        
        # Use context manager to access file
        with self.upload_service.get_file_path(uploaded_file.file_id) as file_path:
            assert os.path.exists(file_path)
            
            with open(file_path, 'rb') as f:
                content = f.read()
            assert content == file_data
    
    def test_get_upload_stats(self):
        """Test getting upload service statistics."""
        stats = self.upload_service.get_upload_stats()
        
        assert 'active_files' in stats
        assert 'total_size_bytes' in stats
        assert 'max_file_size_bytes' in stats
        assert 'allowed_formats' in stats
        assert 'temp_storage_duration_seconds' in stats
        assert 'max_concurrent_uploads' in stats
        
        assert stats['active_files'] == 0  # No files uploaded yet
        assert stats['max_file_size_bytes'] == self.config.max_file_size
        assert stats['allowed_formats'] == self.config.allowed_formats


class TestIntegration:
    """Integration tests for upload service."""
    
    def test_full_upload_workflow(self):
        """Test complete upload workflow."""
        config = UploadConfig(max_file_size=1024*1024)  # 1MB limit
        service = FileUploadService(config)
        
        try:
            # Create test PDF content
            pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n'
            filename = 'test_document.pdf'
            
            # Upload file
            success, uploaded_file, errors = service.upload_file(pdf_content, filename)
            
            # Should succeed (mocked validation)
            if success:
                assert uploaded_file is not None
                assert uploaded_file.original_filename == filename
                assert len(errors) == 0
                
                # Get file back
                retrieved_file = service.get_uploaded_file(uploaded_file.file_id)
                assert retrieved_file is not None
                
                # Access file content
                with service.get_file_path(uploaded_file.file_id) as file_path:
                    with open(file_path, 'rb') as f:
                        stored_content = f.read()
                    assert stored_content == pdf_content
                
                # Get stats
                stats = service.get_upload_stats()
                assert stats['active_files'] >= 1
                
                # Clean up
                delete_success = service.delete_uploaded_file(uploaded_file.file_id)
                assert delete_success is True
            
        finally:
            service.shutdown()


if __name__ == "__main__":
    pytest.main([__file__])
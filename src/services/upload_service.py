"""File upload and validation service."""

import os
import tempfile
import hashlib
import mimetypes
import magic
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import time
import uuid
from contextlib import contextmanager

from src.models.document import DocumentStructure


@dataclass
class UploadConfig:
    """Configuration for file upload service."""
    max_file_size: int = 50 * 1024 * 1024  # 50MB default
    allowed_formats: List[str] = None
    temp_storage_duration: int = 3600  # 1 hour in seconds
    temp_storage_path: str = None
    enable_virus_scan: bool = False
    max_concurrent_uploads: int = 10
    
    def __post_init__(self):
        """Set default values after initialization."""
        if self.allowed_formats is None:
            self.allowed_formats = ['pdf', 'docx', 'epub']
        
        if self.temp_storage_path is None:
            self.temp_storage_path = tempfile.gettempdir()


@dataclass
class ValidationResult:
    """Result of file validation."""
    is_valid: bool
    file_format: Optional[str] = None
    file_size: int = 0
    mime_type: Optional[str] = None
    security_issues: List[str] = None
    validation_errors: List[str] = None
    file_hash: Optional[str] = None
    
    def __post_init__(self):
        """Initialize lists if None."""
        if self.security_issues is None:
            self.security_issues = []
        if self.validation_errors is None:
            self.validation_errors = []


@dataclass
class UploadedFile:
    """Represents an uploaded file."""
    file_id: str
    original_filename: str
    temp_file_path: str
    file_format: str
    file_size: int
    mime_type: str
    file_hash: str
    upload_timestamp: datetime
    expires_at: datetime
    validation_result: ValidationResult
    
    @property
    def is_expired(self) -> bool:
        """Check if the uploaded file has expired."""
        return datetime.now() > self.expires_at
    
    @property
    def time_remaining(self) -> timedelta:
        """Get remaining time before expiration."""
        return max(timedelta(0), self.expires_at - datetime.now())


class FileValidator:
    """Validates uploaded files for security and format compliance."""
    
    def __init__(self, config: UploadConfig):
        """Initialize file validator.
        
        Args:
            config: Upload configuration
        """
        self.config = config
        
        # MIME type mappings for supported formats
        self.format_mime_types = {
            'pdf': ['application/pdf'],
            'docx': [
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/msword'
            ],
            'epub': ['application/epub+zip']
        }
        
        # File signature (magic bytes) for format verification
        self.file_signatures = {
            'pdf': [b'%PDF-'],
            'docx': [b'PK\x03\x04'],  # ZIP signature (DOCX is ZIP-based)
            'epub': [b'PK\x03\x04']   # ZIP signature (EPUB is ZIP-based)
        }
        
        # Dangerous file patterns to check for
        self.dangerous_patterns = [
            b'<script',
            b'javascript:',
            b'vbscript:',
            b'onload=',
            b'onerror=',
            b'eval(',
            b'document.write',
            b'<?php',
            b'<%',
            b'#!/bin/',
            b'#!/usr/bin/'
        ]
    
    def validate_file(self, file_path: str, original_filename: str) -> ValidationResult:
        """Validate an uploaded file.
        
        Args:
            file_path: Path to the uploaded file
            original_filename: Original filename from upload
            
        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=False)
        
        try:
            # Check if file exists and is readable
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                result.validation_errors.append("File does not exist or is not a regular file")
                return result
            
            # Get file size
            result.file_size = os.path.getsize(file_path)
            
            # Validate file size
            if not self._validate_file_size(result.file_size, result):
                return result
            
            # Calculate file hash
            result.file_hash = self._calculate_file_hash(file_path)
            
            # Detect MIME type
            result.mime_type = self._detect_mime_type(file_path)
            
            # Validate file format
            if not self._validate_file_format(file_path, original_filename, result):
                return result
            
            # Perform security checks
            if not self._perform_security_checks(file_path, result):
                return result
            
            # Additional format-specific validation
            if not self._validate_format_specific(file_path, result.file_format, result):
                return result
            
            result.is_valid = True
            return result
            
        except Exception as e:
            result.validation_errors.append(f"Validation error: {str(e)}")
            return result
    
    def _validate_file_size(self, file_size: int, result: ValidationResult) -> bool:
        """Validate file size against limits."""
        if file_size == 0:
            result.validation_errors.append("File is empty")
            return False
        
        if file_size > self.config.max_file_size:
            result.validation_errors.append(
                f"File size ({file_size} bytes) exceeds maximum allowed size ({self.config.max_file_size} bytes)"
            )
            return False
        
        return True
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of the file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _detect_mime_type(self, file_path: str) -> str:
        """Detect MIME type of the file."""
        try:
            # Try using python-magic for more accurate detection
            mime_type = magic.from_file(file_path, mime=True)
            return mime_type
        except:
            # Fallback to mimetypes module
            mime_type, _ = mimetypes.guess_type(file_path)
            return mime_type or 'application/octet-stream'
    
    def _validate_file_format(self, file_path: str, original_filename: str, 
                            result: ValidationResult) -> bool:
        """Validate file format using multiple methods."""
        # Extract extension from filename
        file_extension = Path(original_filename).suffix.lower().lstrip('.')
        
        # Check if extension is allowed
        if file_extension not in self.config.allowed_formats:
            result.validation_errors.append(
                f"File format '{file_extension}' is not allowed. Allowed formats: {', '.join(self.config.allowed_formats)}"
            )
            return False
        
        # Verify MIME type matches extension
        expected_mime_types = self.format_mime_types.get(file_extension, [])
        if expected_mime_types and result.mime_type not in expected_mime_types:
            result.validation_errors.append(
                f"MIME type '{result.mime_type}' does not match file extension '{file_extension}'"
            )
            return False
        
        # Verify file signature (magic bytes)
        if not self._verify_file_signature(file_path, file_extension):
            result.validation_errors.append(
                f"File signature does not match expected format for '{file_extension}'"
            )
            return False
        
        result.file_format = file_extension
        return True
    
    def _verify_file_signature(self, file_path: str, file_format: str) -> bool:
        """Verify file signature matches the expected format."""
        expected_signatures = self.file_signatures.get(file_format, [])
        if not expected_signatures:
            return True  # No signature check for this format
        
        try:
            with open(file_path, 'rb') as f:
                file_header = f.read(1024)  # Read first 1KB
            
            for signature in expected_signatures:
                if file_header.startswith(signature):
                    return True
            
            return False
        except:
            return False
    
    def _perform_security_checks(self, file_path: str, result: ValidationResult) -> bool:
        """Perform security checks on the file."""
        try:
            # Check for dangerous patterns in file content
            with open(file_path, 'rb') as f:
                # Read file in chunks to handle large files
                chunk_size = 8192
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Check for dangerous patterns
                    chunk_lower = chunk.lower()
                    for pattern in self.dangerous_patterns:
                        if pattern in chunk_lower:
                            result.security_issues.append(
                                f"Potentially dangerous content detected: {pattern.decode('utf-8', errors='ignore')}"
                            )
            
            # Check filename for suspicious patterns
            if self._has_suspicious_filename(os.path.basename(file_path)):
                result.security_issues.append("Suspicious filename detected")
            
            # If security issues found, mark as invalid
            if result.security_issues:
                return False
            
            return True
            
        except Exception as e:
            result.security_issues.append(f"Security check failed: {str(e)}")
            return False
    
    def _has_suspicious_filename(self, filename: str) -> bool:
        """Check if filename contains suspicious patterns."""
        suspicious_patterns = [
            '..',  # Directory traversal
            '/',   # Path separator
            '\\',  # Windows path separator
            ':',   # Drive separator (Windows)
            '<',   # HTML/XML
            '>',   # HTML/XML
            '|',   # Pipe
            '*',   # Wildcard
            '?',   # Wildcard
        ]
        
        return any(pattern in filename for pattern in suspicious_patterns)
    
    def _validate_format_specific(self, file_path: str, file_format: str, 
                                result: ValidationResult) -> bool:
        """Perform format-specific validation."""
        try:
            if file_format == 'pdf':
                return self._validate_pdf(file_path, result)
            elif file_format == 'docx':
                return self._validate_docx(file_path, result)
            elif file_format == 'epub':
                return self._validate_epub(file_path, result)
            
            return True
            
        except Exception as e:
            result.validation_errors.append(f"Format-specific validation failed: {str(e)}")
            return False
    
    def _validate_pdf(self, file_path: str, result: ValidationResult) -> bool:
        """Validate PDF file structure."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read(1024)
                
                # Check for PDF header
                if not content.startswith(b'%PDF-'):
                    result.validation_errors.append("Invalid PDF header")
                    return False
                
                # Check for PDF version
                version_line = content.split(b'\n')[0]
                if b'%PDF-1.' not in version_line:
                    result.validation_errors.append("Unsupported PDF version")
                    return False
            
            return True
            
        except Exception as e:
            result.validation_errors.append(f"PDF validation failed: {str(e)}")
            return False
    
    def _validate_docx(self, file_path: str, result: ValidationResult) -> bool:
        """Validate DOCX file structure."""
        try:
            import zipfile
            
            # DOCX is a ZIP file, check if it can be opened as ZIP
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check for required DOCX files
                required_files = [
                    '[Content_Types].xml',
                    '_rels/.rels',
                    'word/document.xml'
                ]
                
                zip_contents = zip_file.namelist()
                for required_file in required_files:
                    if required_file not in zip_contents:
                        result.validation_errors.append(f"Missing required DOCX file: {required_file}")
                        return False
            
            return True
            
        except zipfile.BadZipFile:
            result.validation_errors.append("Invalid DOCX file: not a valid ZIP archive")
            return False
        except Exception as e:
            result.validation_errors.append(f"DOCX validation failed: {str(e)}")
            return False
    
    def _validate_epub(self, file_path: str, result: ValidationResult) -> bool:
        """Validate EPUB file structure."""
        try:
            import zipfile
            
            # EPUB is a ZIP file, check if it can be opened as ZIP
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check for required EPUB files
                required_files = [
                    'META-INF/container.xml',
                    'mimetype'
                ]
                
                zip_contents = zip_file.namelist()
                for required_file in required_files:
                    if required_file not in zip_contents:
                        result.validation_errors.append(f"Missing required EPUB file: {required_file}")
                        return False
                
                # Check mimetype content
                mimetype_content = zip_file.read('mimetype').decode('utf-8').strip()
                if mimetype_content != 'application/epub+zip':
                    result.validation_errors.append("Invalid EPUB mimetype")
                    return False
            
            return True
            
        except zipfile.BadZipFile:
            result.validation_errors.append("Invalid EPUB file: not a valid ZIP archive")
            return False
        except Exception as e:
            result.validation_errors.append(f"EPUB validation failed: {str(e)}")
            return False


class TempFileManager:
    """Manages temporary file storage with automatic cleanup."""
    
    def __init__(self, config: UploadConfig):
        """Initialize temporary file manager.
        
        Args:
            config: Upload configuration
        """
        self.config = config
        self.uploaded_files: Dict[str, UploadedFile] = {}
        self.cleanup_thread = None
        self.cleanup_interval = 300  # 5 minutes
        self.shutdown_event = threading.Event()
        
        # Ensure temp storage directory exists
        os.makedirs(self.config.temp_storage_path, exist_ok=True)
        
        # Start cleanup thread
        self._start_cleanup_thread()
    
    def store_file(self, file_data: bytes, original_filename: str, 
                  validation_result: ValidationResult) -> UploadedFile:
        """Store uploaded file temporarily.
        
        Args:
            file_data: File content as bytes
            original_filename: Original filename
            validation_result: Validation result
            
        Returns:
            UploadedFile object
        """
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        
        # Create temporary file
        file_extension = Path(original_filename).suffix
        temp_filename = f"{file_id}{file_extension}"
        temp_file_path = os.path.join(self.config.temp_storage_path, temp_filename)
        
        # Write file data
        with open(temp_file_path, 'wb') as f:
            f.write(file_data)
        
        # Create UploadedFile object
        now = datetime.now()
        uploaded_file = UploadedFile(
            file_id=file_id,
            original_filename=original_filename,
            temp_file_path=temp_file_path,
            file_format=validation_result.file_format,
            file_size=validation_result.file_size,
            mime_type=validation_result.mime_type,
            file_hash=validation_result.file_hash,
            upload_timestamp=now,
            expires_at=now + timedelta(seconds=self.config.temp_storage_duration),
            validation_result=validation_result
        )
        
        # Store in memory
        self.uploaded_files[file_id] = uploaded_file
        
        return uploaded_file
    
    def get_file(self, file_id: str) -> Optional[UploadedFile]:
        """Get uploaded file by ID.
        
        Args:
            file_id: File ID
            
        Returns:
            UploadedFile object or None if not found
        """
        uploaded_file = self.uploaded_files.get(file_id)
        
        if uploaded_file and uploaded_file.is_expired:
            self.cleanup_file(file_id)
            return None
        
        return uploaded_file
    
    def cleanup_file(self, file_id: str) -> bool:
        """Clean up a specific file.
        
        Args:
            file_id: File ID to clean up
            
        Returns:
            True if file was cleaned up, False otherwise
        """
        uploaded_file = self.uploaded_files.get(file_id)
        if not uploaded_file:
            return False
        
        # Remove from memory
        del self.uploaded_files[file_id]
        
        # Remove file from disk
        try:
            if os.path.exists(uploaded_file.temp_file_path):
                os.remove(uploaded_file.temp_file_path)
            return True
        except Exception:
            return False
    
    def cleanup_expired_files(self) -> int:
        """Clean up all expired files.
        
        Returns:
            Number of files cleaned up
        """
        expired_file_ids = [
            file_id for file_id, uploaded_file in self.uploaded_files.items()
            if uploaded_file.is_expired
        ]
        
        cleaned_count = 0
        for file_id in expired_file_ids:
            if self.cleanup_file(file_id):
                cleaned_count += 1
        
        return cleaned_count
    
    def _start_cleanup_thread(self):
        """Start the cleanup thread."""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
            self.cleanup_thread.start()
    
    def _cleanup_worker(self):
        """Worker thread for periodic cleanup."""
        while not self.shutdown_event.wait(self.cleanup_interval):
            try:
                self.cleanup_expired_files()
            except Exception:
                pass  # Continue cleanup on errors
    
    def shutdown(self):
        """Shutdown the temp file manager and cleanup all files."""
        self.shutdown_event.set()
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        
        # Clean up all remaining files
        file_ids = list(self.uploaded_files.keys())
        for file_id in file_ids:
            self.cleanup_file(file_id)
    
    @contextmanager
    def get_file_path(self, file_id: str):
        """Context manager to safely access file path.
        
        Args:
            file_id: File ID
            
        Yields:
            File path if file exists and is valid
        """
        uploaded_file = self.get_file(file_id)
        if not uploaded_file:
            raise FileNotFoundError(f"File {file_id} not found or expired")
        
        if not os.path.exists(uploaded_file.temp_file_path):
            raise FileNotFoundError(f"Temporary file {uploaded_file.temp_file_path} not found")
        
        try:
            yield uploaded_file.temp_file_path
        finally:
            pass  # File cleanup is handled by the cleanup thread


class FileUploadService:
    """Main file upload and validation service."""
    
    def __init__(self, config: Optional[UploadConfig] = None):
        """Initialize file upload service.
        
        Args:
            config: Upload configuration (uses defaults if None)
        """
        self.config = config or UploadConfig()
        self.validator = FileValidator(self.config)
        self.temp_manager = TempFileManager(self.config)
        self.upload_semaphore = threading.Semaphore(self.config.max_concurrent_uploads)
    
    def upload_file(self, file_data: bytes, filename: str) -> Tuple[bool, UploadedFile, List[str]]:
        """Upload and validate a file.
        
        Args:
            file_data: File content as bytes
            filename: Original filename
            
        Returns:
            Tuple of (success, uploaded_file_or_none, error_messages)
        """
        errors = []
        
        try:
            # Acquire semaphore for concurrent upload limiting
            if not self.upload_semaphore.acquire(blocking=False):
                errors.append("Too many concurrent uploads. Please try again later.")
                return False, None, errors
            
            try:
                # Create temporary file for validation
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(file_data)
                    temp_file_path = temp_file.name
                
                try:
                    # Validate the file
                    validation_result = self.validator.validate_file(temp_file_path, filename)
                    
                    if not validation_result.is_valid:
                        errors.extend(validation_result.validation_errors)
                        errors.extend(validation_result.security_issues)
                        return False, None, errors
                    
                    # Store the file
                    uploaded_file = self.temp_manager.store_file(file_data, filename, validation_result)
                    
                    return True, uploaded_file, []
                    
                finally:
                    # Clean up temporary validation file
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass
                        
            finally:
                self.upload_semaphore.release()
                
        except Exception as e:
            errors.append(f"Upload failed: {str(e)}")
            return False, None, errors
    
    def get_uploaded_file(self, file_id: str) -> Optional[UploadedFile]:
        """Get uploaded file by ID.
        
        Args:
            file_id: File ID
            
        Returns:
            UploadedFile object or None if not found
        """
        return self.temp_manager.get_file(file_id)
    
    def delete_uploaded_file(self, file_id: str) -> bool:
        """Delete uploaded file.
        
        Args:
            file_id: File ID
            
        Returns:
            True if file was deleted, False otherwise
        """
        return self.temp_manager.cleanup_file(file_id)
    
    def get_file_path(self, file_id: str):
        """Get context manager for safe file path access.
        
        Args:
            file_id: File ID
            
        Returns:
            Context manager yielding file path
        """
        return self.temp_manager.get_file_path(file_id)
    
    def get_upload_stats(self) -> Dict[str, Any]:
        """Get upload service statistics.
        
        Returns:
            Dictionary with service statistics
        """
        active_files = len(self.temp_manager.uploaded_files)
        total_size = sum(f.file_size for f in self.temp_manager.uploaded_files.values())
        
        return {
            'active_files': active_files,
            'total_size_bytes': total_size,
            'max_file_size_bytes': self.config.max_file_size,
            'allowed_formats': self.config.allowed_formats,
            'temp_storage_duration_seconds': self.config.temp_storage_duration,
            'max_concurrent_uploads': self.config.max_concurrent_uploads
        }
    
    def shutdown(self):
        """Shutdown the upload service."""
        self.temp_manager.shutdown()
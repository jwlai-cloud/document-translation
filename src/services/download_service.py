"""Download service for translated documents with format preservation."""

import os
import tempfile
import hashlib
import uuid
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import threading
import time

from src.models.document import DocumentStructure
from src.models.layout import AdjustedRegion
from src.layout.reconstruction_engine import DefaultLayoutReconstructionEngine


@dataclass
class DownloadConfig:
    """Configuration for download service."""
    temp_storage_duration: int = 1800  # 30 minutes in seconds
    temp_storage_path: str = None
    max_concurrent_downloads: int = 5
    secure_links: bool = True
    link_expiration_time: int = 3600  # 1 hour in seconds
    cleanup_interval: int = 300  # 5 minutes
    
    def __post_init__(self):
        """Set default values after initialization."""
        if self.temp_storage_path is None:
            self.temp_storage_path = tempfile.gettempdir()


@dataclass
class DownloadLink:
    """Represents a secure download link."""
    link_id: str
    file_path: str
    original_filename: str
    file_format: str
    file_size: int
    file_hash: str
    created_at: datetime
    expires_at: datetime
    download_count: int = 0
    max_downloads: int = 1
    
    @property
    def is_expired(self) -> bool:
        """Check if the download link has expired."""
        return datetime.now() > self.expires_at
    
    @property
    def is_exhausted(self) -> bool:
        """Check if the download link has been exhausted."""
        return self.download_count >= self.max_downloads
    
    @property
    def is_valid(self) -> bool:
        """Check if the download link is still valid."""
        return not self.is_expired and not self.is_exhausted and os.path.exists(self.file_path)


@dataclass
class DownloadRequest:
    """Represents a download request."""
    request_id: str
    document: DocumentStructure
    translated_regions: Dict[str, List[AdjustedRegion]]
    target_format: str
    filename_prefix: str = ""
    quality_settings: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.quality_settings is None:
            self.quality_settings = {}


@dataclass
class DownloadResult:
    """Result of a download preparation."""
    success: bool
    download_link: Optional[DownloadLink] = None
    error_message: str = ""
    processing_time: float = 0.0


class FileNamingService:
    """Service for generating appropriate file names."""
    
    @staticmethod
    def generate_filename(original_document: DocumentStructure,
                         target_format: str,
                         prefix: str = "",
                         include_timestamp: bool = True,
                         include_language_info: bool = True) -> str:
        """Generate an appropriate filename for the translated document.
        
        Args:
            original_document: Original document structure
            target_format: Target file format
            prefix: Optional prefix for the filename
            include_timestamp: Whether to include timestamp
            include_language_info: Whether to include language information
            
        Returns:
            Generated filename
        """
        # Start with original title or default
        base_name = original_document.metadata.title or "translated_document"
        
        # Clean the base name
        base_name = FileNamingService._clean_filename(base_name)
        
        # Add prefix if provided
        if prefix:
            clean_prefix = FileNamingService._clean_filename(prefix)
            base_name = f"{clean_prefix}_{base_name}"
        
        # Add language information if requested
        if include_language_info:
            # This would typically come from translation metadata
            # For now, we'll add a generic "translated" suffix
            base_name = f"{base_name}_translated"
        
        # Add timestamp if requested
        if include_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"{base_name}_{timestamp}"
        
        # Add appropriate extension
        extension = FileNamingService._get_extension_for_format(target_format)
        
        return f"{base_name}.{extension}"
    
    @staticmethod
    def _clean_filename(filename: str) -> str:
        """Clean filename by removing invalid characters."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove multiple consecutive underscores
        while '__' in filename:
            filename = filename.replace('__', '_')
        
        # Remove leading/trailing underscores and spaces
        filename = filename.strip('_ ')
        
        # Ensure filename is not empty
        if not filename:
            filename = "document"
        
        # Limit length
        if len(filename) > 100:
            filename = filename[:100]
        
        return filename
    
    @staticmethod
    def _get_extension_for_format(file_format: str) -> str:
        """Get file extension for the given format."""
        format_extensions = {
            'pdf': 'pdf',
            'docx': 'docx',
            'epub': 'epub'
        }
        return format_extensions.get(file_format.lower(), file_format.lower())


class DownloadLinkManager:
    """Manages secure download links with expiration and cleanup."""
    
    def __init__(self, config: DownloadConfig):
        """Initialize download link manager.
        
        Args:
            config: Download configuration
        """
        self.config = config
        self.download_links: Dict[str, DownloadLink] = {}
        self.cleanup_thread = None
        self.shutdown_event = threading.Event()
        
        # Start cleanup thread
        self._start_cleanup_thread()
    
    def create_download_link(self, file_path: str, original_filename: str,
                           file_format: str, max_downloads: int = 1) -> DownloadLink:
        """Create a secure download link.
        
        Args:
            file_path: Path to the file
            original_filename: Original filename
            file_format: File format
            max_downloads: Maximum number of downloads allowed
            
        Returns:
            DownloadLink object
        """
        # Generate secure link ID
        link_id = self._generate_secure_link_id()
        
        # Calculate file size and hash
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        file_hash = self._calculate_file_hash(file_path) if os.path.exists(file_path) else ""
        
        # Create download link
        now = datetime.now()
        download_link = DownloadLink(
            link_id=link_id,
            file_path=file_path,
            original_filename=original_filename,
            file_format=file_format,
            file_size=file_size,
            file_hash=file_hash,
            created_at=now,
            expires_at=now + timedelta(seconds=self.config.link_expiration_time),
            max_downloads=max_downloads
        )
        
        # Store the link
        self.download_links[link_id] = download_link
        
        return download_link
    
    def get_download_link(self, link_id: str) -> Optional[DownloadLink]:
        """Get download link by ID.
        
        Args:
            link_id: Link ID
            
        Returns:
            DownloadLink object or None if not found/invalid
        """
        download_link = self.download_links.get(link_id)
        
        if download_link and not download_link.is_valid:
            # Clean up invalid link
            self.cleanup_link(link_id)
            return None
        
        return download_link
    
    def record_download(self, link_id: str) -> bool:
        """Record a download attempt.
        
        Args:
            link_id: Link ID
            
        Returns:
            True if download was recorded successfully
        """
        download_link = self.download_links.get(link_id)
        if not download_link or not download_link.is_valid:
            return False
        
        download_link.download_count += 1
        
        # Clean up if exhausted
        if download_link.is_exhausted:
            self.cleanup_link(link_id)
        
        return True
    
    def cleanup_link(self, link_id: str) -> bool:
        """Clean up a specific download link.
        
        Args:
            link_id: Link ID to clean up
            
        Returns:
            True if link was cleaned up
        """
        download_link = self.download_links.get(link_id)
        if not download_link:
            return False
        
        # Remove from memory
        del self.download_links[link_id]
        
        # Remove file from disk
        try:
            if os.path.exists(download_link.file_path):
                os.remove(download_link.file_path)
            return True
        except Exception:
            return False
    
    def cleanup_expired_links(self) -> int:
        """Clean up all expired or invalid links.
        
        Returns:
            Number of links cleaned up
        """
        expired_link_ids = [
            link_id for link_id, download_link in self.download_links.items()
            if not download_link.is_valid
        ]
        
        cleaned_count = 0
        for link_id in expired_link_ids:
            if self.cleanup_link(link_id):
                cleaned_count += 1
        
        return cleaned_count
    
    def _generate_secure_link_id(self) -> str:
        """Generate a secure link ID."""
        if self.config.secure_links:
            # Generate cryptographically secure ID
            random_data = os.urandom(32)
            timestamp = str(time.time()).encode()
            combined = random_data + timestamp
            return hashlib.sha256(combined).hexdigest()
        else:
            # Simple UUID for non-secure links
            return str(uuid.uuid4())
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of the file."""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return ""
    
    def _start_cleanup_thread(self):
        """Start the cleanup thread."""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
            self.cleanup_thread.start()
    
    def _cleanup_worker(self):
        """Worker thread for periodic cleanup."""
        while not self.shutdown_event.wait(self.config.cleanup_interval):
            try:
                self.cleanup_expired_links()
            except Exception:
                pass  # Continue cleanup on errors
    
    def shutdown(self):
        """Shutdown the link manager and cleanup all links."""
        self.shutdown_event.set()
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        
        # Clean up all remaining links
        link_ids = list(self.download_links.keys())
        for link_id in link_ids:
            self.cleanup_link(link_id)


class DownloadService:
    """Main service for generating and managing document downloads."""
    
    def __init__(self, config: Optional[DownloadConfig] = None):
        """Initialize download service.
        
        Args:
            config: Download configuration (uses defaults if None)
        """
        self.config = config or DownloadConfig()
        self.link_manager = DownloadLinkManager(self.config)
        self.reconstruction_engine = DefaultLayoutReconstructionEngine()
        self.naming_service = FileNamingService()
        self.download_semaphore = threading.Semaphore(self.config.max_concurrent_downloads)
        
        # Ensure temp storage directory exists
        os.makedirs(self.config.temp_storage_path, exist_ok=True)
    
    def prepare_download(self, download_request: DownloadRequest) -> DownloadResult:
        """Prepare a document for download.
        
        Args:
            download_request: Download request details
            
        Returns:
            DownloadResult with download link or error
        """
        start_time = time.time()
        
        try:
            # Acquire semaphore for concurrent download limiting
            if not self.download_semaphore.acquire(blocking=False):
                return DownloadResult(
                    success=False,
                    error_message="Too many concurrent download preparations. Please try again later."
                )
            
            try:
                # Generate filename
                filename = self.naming_service.generate_filename(
                    download_request.document,
                    download_request.target_format,
                    download_request.filename_prefix
                )
                
                # Create temporary file path
                temp_filename = f"{download_request.request_id}_{filename}"
                temp_file_path = os.path.join(self.config.temp_storage_path, temp_filename)
                
                # Reconstruct document with translations
                reconstructed_bytes = self.reconstruction_engine.reconstruct_document(
                    download_request.document,
                    download_request.translated_regions
                )
                
                # Write reconstructed document to temporary file
                with open(temp_file_path, 'wb') as f:
                    f.write(reconstructed_bytes)
                
                # Create download link
                download_link = self.link_manager.create_download_link(
                    temp_file_path,
                    filename,
                    download_request.target_format
                )
                
                processing_time = time.time() - start_time
                
                return DownloadResult(
                    success=True,
                    download_link=download_link,
                    processing_time=processing_time
                )
                
            finally:
                self.download_semaphore.release()
                
        except Exception as e:
            processing_time = time.time() - start_time
            return DownloadResult(
                success=False,
                error_message=f"Download preparation failed: {str(e)}",
                processing_time=processing_time
            )
    
    def get_download_info(self, link_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a download link.
        
        Args:
            link_id: Download link ID
            
        Returns:
            Dictionary with download information or None if not found
        """
        download_link = self.link_manager.get_download_link(link_id)
        if not download_link:
            return None
        
        return {
            'link_id': download_link.link_id,
            'filename': download_link.original_filename,
            'format': download_link.file_format,
            'file_size': download_link.file_size,
            'file_hash': download_link.file_hash,
            'created_at': download_link.created_at.isoformat(),
            'expires_at': download_link.expires_at.isoformat(),
            'download_count': download_link.download_count,
            'max_downloads': download_link.max_downloads,
            'is_valid': download_link.is_valid,
            'time_remaining': max(0, (download_link.expires_at - datetime.now()).total_seconds())
        }
    
    def download_file(self, link_id: str) -> Tuple[bool, Optional[bytes], str, Dict[str, Any]]:
        """Download a file using the download link.
        
        Args:
            link_id: Download link ID
            
        Returns:
            Tuple of (success, file_bytes, filename, metadata)
        """
        download_link = self.link_manager.get_download_link(link_id)
        if not download_link:
            return False, None, "", {"error": "Download link not found or expired"}
        
        if not download_link.is_valid:
            return False, None, "", {"error": "Download link is no longer valid"}
        
        try:
            # Read file content
            with open(download_link.file_path, 'rb') as f:
                file_bytes = f.read()
            
            # Record the download
            self.link_manager.record_download(link_id)
            
            # Prepare metadata
            metadata = {
                'filename': download_link.original_filename,
                'format': download_link.file_format,
                'file_size': len(file_bytes),
                'file_hash': download_link.file_hash,
                'download_count': download_link.download_count
            }
            
            return True, file_bytes, download_link.original_filename, metadata
            
        except Exception as e:
            return False, None, "", {"error": f"Failed to read file: {str(e)}"}
    
    def cancel_download(self, link_id: str) -> bool:
        """Cancel a download and clean up associated files.
        
        Args:
            link_id: Download link ID
            
        Returns:
            True if download was cancelled successfully
        """
        return self.link_manager.cleanup_link(link_id)
    
    def get_download_stats(self) -> Dict[str, Any]:
        """Get download service statistics.
        
        Returns:
            Dictionary with service statistics
        """
        active_links = len(self.link_manager.download_links)
        total_size = sum(
            link.file_size for link in self.link_manager.download_links.values()
            if os.path.exists(link.file_path)
        )
        
        return {
            'active_download_links': active_links,
            'total_storage_size_bytes': total_size,
            'temp_storage_path': self.config.temp_storage_path,
            'link_expiration_time_seconds': self.config.link_expiration_time,
            'max_concurrent_downloads': self.config.max_concurrent_downloads,
            'cleanup_interval_seconds': self.config.cleanup_interval
        }
    
    def cleanup_expired_downloads(self) -> int:
        """Manually trigger cleanup of expired downloads.
        
        Returns:
            Number of downloads cleaned up
        """
        return self.link_manager.cleanup_expired_links()
    
    def shutdown(self):
        """Shutdown the download service."""
        self.link_manager.shutdown()
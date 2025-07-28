"""Base classes for core services."""

from abc import ABC, abstractmethod
from typing import List, Optional
from src.models.document import DocumentStructure
from src.models.quality import QualityScore, QualityReport
from src.models.layout import LayoutAnalysis


class QualityAssessmentService(ABC):
    """Abstract base class for quality assessment services."""
    
    @abstractmethod
    def assess_translation_quality(self, original: str, translated: str) -> QualityScore:
        """Assess the quality of a translation.
        
        Args:
            original: Original text
            translated: Translated text
            
        Returns:
            QualityScore with various quality metrics
        """
        pass
    
    @abstractmethod
    def assess_layout_preservation(self, original: LayoutAnalysis, 
                                 reconstructed: LayoutAnalysis) -> QualityScore:
        """Assess how well layout was preserved.
        
        Args:
            original: Original layout analysis
            reconstructed: Reconstructed layout analysis
            
        Returns:
            QualityScore for layout preservation
        """
        pass
    
    @abstractmethod
    def generate_quality_report(self, assessments: List[QualityScore]) -> QualityReport:
        """Generate a comprehensive quality report.
        
        Args:
            assessments: List of quality assessments
            
        Returns:
            QualityReport with overall metrics and recommendations
        """
        pass


class FileUploadService(ABC):
    """Abstract base class for file upload services."""
    
    @abstractmethod
    def validate_file(self, file_path: str, file_size: int) -> bool:
        """Validate uploaded file.
        
        Args:
            file_path: Path to uploaded file
            file_size: Size of the file in bytes
            
        Returns:
            True if file is valid
        """
        pass
    
    @abstractmethod
    def store_temporarily(self, file_path: str) -> str:
        """Store file temporarily for processing.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Temporary storage path
        """
        pass
    
    @abstractmethod
    def cleanup_temporary_files(self, temp_path: str) -> None:
        """Clean up temporary files.
        
        Args:
            temp_path: Path to temporary file or directory
        """
        pass


class PreviewService(ABC):
    """Abstract base class for document preview services."""
    
    @abstractmethod
    def generate_preview(self, document: DocumentStructure) -> bytes:
        """Generate preview image for a document.
        
        Args:
            document: Document structure to preview
            
        Returns:
            Preview image as bytes
        """
        pass
    
    @abstractmethod
    def generate_side_by_side_preview(self, original: DocumentStructure, 
                                    translated: DocumentStructure) -> bytes:
        """Generate side-by-side preview of original and translated documents.
        
        Args:
            original: Original document structure
            translated: Translated document structure
            
        Returns:
            Side-by-side preview image as bytes
        """
        pass


class DownloadService(ABC):
    """Abstract base class for download services."""
    
    @abstractmethod
    def generate_download_link(self, document: DocumentStructure, 
                             filename: str) -> str:
        """Generate secure download link for a document.
        
        Args:
            document: Document to download
            filename: Desired filename
            
        Returns:
            Secure download URL
        """
        pass
    
    @abstractmethod
    def prepare_download(self, document: DocumentStructure) -> bytes:
        """Prepare document for download.
        
        Args:
            document: Document structure to prepare
            
        Returns:
            Document content as bytes
        """
        pass
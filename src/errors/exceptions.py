"""Exception hierarchy for document translation system."""

from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    FILE_PROCESSING = "file_processing"
    TRANSLATION = "translation"
    LAYOUT_PROCESSING = "layout_processing"
    VALIDATION = "validation"
    SERVICE = "service"
    CONFIGURATION = "configuration"
    RESOURCE = "resource"


@dataclass
class ErrorContext:
    """Context information for errors."""
    job_id: Optional[str] = None
    file_path: Optional[str] = None
    stage: Optional[str] = None
    component: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentTranslationError(Exception):
    """Base exception for all document translation errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = False,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        suggestions: Optional[List[str]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.recoverable = recoverable
        self.context = context or ErrorContext()
        self.cause = cause
        self.suggestions = suggestions or []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            'message': self.message,
            'error_code': self.error_code,
            'category': self.category.value,
            'severity': self.severity.value,
            'recoverable': self.recoverable,
            'context': {
                'job_id': self.context.job_id,
                'file_path': self.context.file_path,
                'stage': self.context.stage,
                'component': self.context.component,
                'metadata': self.context.metadata
            },
            'cause': str(self.cause) if self.cause else None,
            'suggestions': self.suggestions
        }
    
    def __str__(self) -> str:
        """String representation of the error."""
        parts = [f"[{self.error_code}] {self.message}"]
        
        if self.context.job_id:
            parts.append(f"Job: {self.context.job_id}")
        
        if self.context.stage:
            parts.append(f"Stage: {self.context.stage}")
            
        if self.cause:
            parts.append(f"Caused by: {self.cause}")
            
        return " | ".join(parts)


class FileProcessingError(DocumentTranslationError):
    """Errors related to file processing operations."""
    
    def __init__(self, message: str, error_code: str, **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.FILE_PROCESSING,
            **kwargs
        )


class InvalidFileFormatError(FileProcessingError):
    """Error for invalid or unsupported file formats."""
    
    def __init__(self, file_format: str, supported_formats: List[str], **kwargs):
        message = (
            f"Unsupported file format: {file_format}. "
            f"Supported formats: {', '.join(supported_formats)}"
        )
        super().__init__(
            message=message,
            error_code="FILE_001",
            suggestions=[
                f"Convert your file to one of: {', '.join(supported_formats)}",
                "Check if the file extension matches the actual format",
                "Verify the file is not corrupted"
            ],
            **kwargs
        )


class FileSizeExceededError(FileProcessingError):
    """Error for files exceeding size limits."""
    
    def __init__(self, file_size: int, max_size: int, **kwargs):
        message = (
            f"File size ({file_size} bytes) exceeds maximum allowed "
            f"size ({max_size} bytes)"
        )
        super().__init__(
            message=message,
            error_code="FILE_002",
            suggestions=[
                f"Reduce file size to under {max_size} bytes",
                "Split large documents into smaller sections",
                "Compress images or remove unnecessary content"
            ],
            **kwargs
        )


class FileCorruptionError(FileProcessingError):
    """Error for corrupted or unreadable files."""
    
    def __init__(self, details: str = "", **kwargs):
        message = f"File appears to be corrupted or unreadable. {details}".strip()
        super().__init__(
            message=message,
            error_code="FILE_003",
            suggestions=[
                "Try re-saving the file in its original application",
                "Check if the file opens correctly in its native application",
                "Upload a different copy of the file"
            ],
            **kwargs
        )


class ParsingError(FileProcessingError):
    """Error during document parsing operations."""
    
    def __init__(self, parser_type: str, details: str = "", **kwargs):
        message = f"Failed to parse document using {parser_type} parser. {details}".strip()
        super().__init__(
            message=message,
            error_code="FILE_004",
            suggestions=[
                "Verify the file format matches the expected type",
                "Check if the document has any protection or encryption",
                "Try saving the document in a different format"
            ],
            **kwargs
        )


class TranslationError(DocumentTranslationError):
    """Errors related to translation operations."""
    
    def __init__(self, message: str, error_code: str, **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.TRANSLATION,
            **kwargs
        )


class UnsupportedLanguagePairError(TranslationError):
    """Error for unsupported language combinations."""
    
    def __init__(self, source_lang: str, target_lang: str, 
                 supported_pairs: List[tuple], **kwargs):
        message = (
            f"Translation from {source_lang} to {target_lang} is not supported"
        )
        super().__init__(
            message=message,
            error_code="TRANS_001",
            suggestions=[
                "Check the list of supported language pairs",
                "Try translating through an intermediate language",
                "Verify the language codes are correct"
            ],
            **kwargs
        )


class TranslationServiceError(TranslationError):
    """Error from external translation service."""
    
    def __init__(self, service_name: str, details: str = "", **kwargs):
        message = f"Translation service '{service_name}' failed. {details}".strip()
        super().__init__(
            message=message,
            error_code="TRANS_002",
            recoverable=True,
            suggestions=[
                "Check internet connection",
                "Verify translation service credentials",
                "Try again in a few moments",
                "Switch to a different translation service"
            ],
            **kwargs
        )


class ContextPreservationError(TranslationError):
    """Error in maintaining translation context."""
    
    def __init__(self, details: str = "", **kwargs):
        message = f"Failed to preserve translation context. {details}".strip()
        super().__init__(
            message=message,
            error_code="TRANS_003",
            suggestions=[
                "Try processing smaller text segments",
                "Check if the document structure is too complex",
                "Consider manual review of translated sections"
            ],
            **kwargs
        )


class QualityThresholdError(TranslationError):
    """Error when translation quality is below threshold."""
    
    def __init__(self, quality_score: float, threshold: float, **kwargs):
        message = (
            f"Translation quality ({quality_score:.2f}) is below "
            f"required threshold ({threshold:.2f})"
        )
        super().__init__(
            message=message,
            error_code="TRANS_004",
            suggestions=[
                "Lower the quality threshold",
                "Try a different translation service",
                "Review and manually improve the translation",
                "Check if the source text is clear and well-formatted"
            ],
            **kwargs
        )


class LayoutProcessingError(DocumentTranslationError):
    """Errors related to layout processing operations."""
    
    def __init__(self, message: str, error_code: str, **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.LAYOUT_PROCESSING,
            **kwargs
        )


class LayoutAnalysisError(LayoutProcessingError):
    """Error during layout analysis."""
    
    def __init__(self, details: str = "", **kwargs):
        message = f"Failed to analyze document layout. {details}".strip()
        super().__init__(
            message=message,
            error_code="LAYOUT_001",
            suggestions=[
                "Check if the document has a complex or unusual layout",
                "Try processing individual pages separately",
                "Verify the document is not password protected"
            ],
            **kwargs
        )


class TextFittingError(LayoutProcessingError):
    """Error during text fitting operations."""
    
    def __init__(self, details: str = "", **kwargs):
        message = f"Failed to fit translated text into layout. {details}".strip()
        super().__init__(
            message=message,
            error_code="LAYOUT_002",
            suggestions=[
                "Allow larger layout adjustments",
                "Consider using a more compact font",
                "Review text regions that may be too small",
                "Enable automatic font size adjustment"
            ],
            **kwargs
        )


class ReconstructionError(LayoutProcessingError):
    """Error during document reconstruction."""
    
    def __init__(self, format_type: str, details: str = "", **kwargs):
        message = f"Failed to reconstruct {format_type} document. {details}".strip()
        super().__init__(
            message=message,
            error_code="LAYOUT_003",
            suggestions=[
                "Try exporting to a different format",
                "Check if the original document structure is supported",
                "Simplify the document layout before translation"
            ],
            **kwargs
        )


class ValidationError(DocumentTranslationError):
    """Errors related to input validation."""
    
    def __init__(self, message: str, error_code: str, **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.VALIDATION,
            **kwargs
        )


class ConfigurationError(DocumentTranslationError):
    """Errors related to system configuration."""
    
    def __init__(self, message: str, error_code: str, **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class ServiceError(DocumentTranslationError):
    """Errors related to service operations."""
    
    def __init__(self, message: str, error_code: str, **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.SERVICE,
            **kwargs
        )


class ResourceError(DocumentTranslationError):
    """Errors related to resource limitations."""
    
    def __init__(self, message: str, error_code: str, **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class MemoryExceededError(ResourceError):
    """Error when memory usage exceeds limits."""
    
    def __init__(self, current_usage: int, limit: int, **kwargs):
        message = (
            f"Memory usage ({current_usage} MB) exceeds limit ({limit} MB)"
        )
        super().__init__(
            message=message,
            error_code="RESOURCE_001",
            suggestions=[
                "Process smaller documents",
                "Increase memory limits",
                "Close other applications to free memory",
                "Split large documents into sections"
            ],
            **kwargs
        )


class TimeoutError(ResourceError):
    """Error when operations exceed time limits."""
    
    def __init__(self, operation: str, timeout: int, **kwargs):
        message = f"Operation '{operation}' timed out after {timeout} seconds"
        super().__init__(
            message=message,
            error_code="RESOURCE_002",
            recoverable=True,
            suggestions=[
                "Increase timeout limits",
                "Try processing smaller sections",
                "Check system performance",
                "Retry the operation"
            ],
            **kwargs
        )
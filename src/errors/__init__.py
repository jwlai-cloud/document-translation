"""Comprehensive error handling system for document translation."""

from .exceptions import (
    DocumentTranslationError,
    FileProcessingError,
    TranslationError,
    LayoutProcessingError,
    ValidationError,
    ServiceError,
    ConfigurationError,
    ResourceError,
)

from .handlers import (
    ErrorHandler,
    ErrorResponse,
    RecoveryAction,
    ErrorLogger,
)

from .recovery import (
    RecoveryManager,
    RecoveryStrategy,
    AutoRecoveryHandler,
)

__all__ = [
    # Exceptions
    'DocumentTranslationError',
    'FileProcessingError',
    'TranslationError',
    'LayoutProcessingError',
    'ValidationError',
    'ServiceError',
    'ConfigurationError',
    'ResourceError',
    
    # Handlers
    'ErrorHandler',
    'ErrorResponse',
    'RecoveryAction',
    'ErrorLogger',
    
    # Recovery
    'RecoveryManager',
    'RecoveryStrategy',
    'AutoRecoveryHandler',
]
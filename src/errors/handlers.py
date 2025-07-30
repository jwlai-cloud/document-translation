"""Error handling and response management."""

import logging
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .exceptions import (
    DocumentTranslationError, 
    ErrorSeverity, 
    ErrorCategory,
    ErrorContext
)


class ResponseStatus(Enum):
    """Response status for error handling."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    RETRY = "retry"


@dataclass
class RecoveryAction:
    """Represents a recovery action for an error."""
    action_type: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    automatic: bool = False
    priority: int = 1  # Lower number = higher priority


@dataclass
class ErrorResponse:
    """Standardized error response structure."""
    status: ResponseStatus
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    suggestions: List[str] = field(default_factory=list)
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'status': self.status.value,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details,
            'suggestions': self.suggestions,
            'recovery_actions': [
                {
                    'action_type': action.action_type,
                    'description': action.description,
                    'parameters': action.parameters,
                    'automatic': action.automatic,
                    'priority': action.priority
                }
                for action in self.recovery_actions
            ],
            'timestamp': self.timestamp.isoformat()
        }


class ErrorLogger:
    """Centralized error logging system."""
    
    def __init__(self, logger_name: str = "document_translation"):
        self.logger = logging.getLogger(logger_name)
        self._setup_logger()
        self.error_counts: Dict[str, int] = {}
        self.error_history: List[Dict[str, Any]] = []
        
    def _setup_logger(self):
        """Setup logger configuration."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_error(self, error: DocumentTranslationError, 
                  additional_context: Optional[Dict[str, Any]] = None):
        """Log an error with full context."""
        error_dict = error.to_dict()
        
        if additional_context:
            error_dict['additional_context'] = additional_context
        
        # Update error counts
        self.error_counts[error.error_code] = (
            self.error_counts.get(error.error_code, 0) + 1
        )
        
        # Add to history
        self.error_history.append({
            'timestamp': datetime.now().isoformat(),
            'error': error_dict
        })
        
        # Keep only last 1000 errors
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-1000:]
        
        # Log based on severity
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"CRITICAL ERROR: {error}")
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(f"HIGH SEVERITY: {error}")
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"MEDIUM SEVERITY: {error}")
        else:
            self.logger.info(f"LOW SEVERITY: {error}")
        
        # Log stack trace for debugging
        if error.cause:
            self.logger.debug(f"Caused by: {error.cause}")
            self.logger.debug(traceback.format_exc())
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics."""
        return {
            'total_errors': len(self.error_history),
            'error_counts_by_code': self.error_counts.copy(),
            'recent_errors': self.error_history[-10:] if self.error_history else []
        }


class ErrorHandler:
    """Main error handling coordinator."""
    
    def __init__(self):
        self.logger = ErrorLogger()
        self.recovery_handlers: Dict[str, Callable] = {}
        self.error_patterns: Dict[str, List[RecoveryAction]] = {}
        self._setup_default_recovery_actions()
    
    def _setup_default_recovery_actions(self):
        """Setup default recovery actions for common errors."""
        
        # File processing errors
        self.error_patterns["FILE_001"] = [  # Invalid format
            RecoveryAction(
                action_type="format_conversion",
                description="Attempt automatic format detection",
                automatic=True,
                priority=1
            ),
            RecoveryAction(
                action_type="user_guidance",
                description="Provide format conversion guidance",
                priority=2
            )
        ]
        
        self.error_patterns["FILE_002"] = [  # File size exceeded
            RecoveryAction(
                action_type="compression",
                description="Attempt file compression",
                automatic=True,
                priority=1
            ),
            RecoveryAction(
                action_type="chunking",
                description="Split document into smaller sections",
                priority=2
            )
        ]
        
        # Translation errors
        self.error_patterns["TRANS_002"] = [  # Service error
            RecoveryAction(
                action_type="retry",
                description="Retry with exponential backoff",
                parameters={"max_retries": 3, "backoff_factor": 2},
                automatic=True,
                priority=1
            ),
            RecoveryAction(
                action_type="fallback_service",
                description="Switch to backup translation service",
                automatic=True,
                priority=2
            )
        ]
        
        self.error_patterns["TRANS_004"] = [  # Quality threshold
            RecoveryAction(
                action_type="quality_adjustment",
                description="Adjust quality threshold",
                parameters={"adjustment": -0.1},
                priority=1
            ),
            RecoveryAction(
                action_type="manual_review",
                description="Flag for manual review",
                priority=2
            )
        ]
        
        # Layout processing errors
        self.error_patterns["LAYOUT_002"] = [  # Text fitting
            RecoveryAction(
                action_type="font_adjustment",
                description="Reduce font size automatically",
                automatic=True,
                priority=1
            ),
            RecoveryAction(
                action_type="layout_expansion",
                description="Allow larger layout adjustments",
                parameters={"max_adjustment": 0.2},
                priority=2
            )
        ]
        
        # Resource errors
        self.error_patterns["RESOURCE_001"] = [  # Memory exceeded
            RecoveryAction(
                action_type="memory_cleanup",
                description="Clear temporary data and caches",
                automatic=True,
                priority=1
            ),
            RecoveryAction(
                action_type="processing_mode",
                description="Switch to low-memory processing mode",
                automatic=True,
                priority=2
            )
        ]
    
    def handle_error(self, error: Exception, 
                    context: Optional[ErrorContext] = None) -> ErrorResponse:
        """Handle any error and return standardized response."""
        
        # Convert to DocumentTranslationError if needed
        if not isinstance(error, DocumentTranslationError):
            doc_error = DocumentTranslationError(
                message=str(error),
                error_code="UNKNOWN_001",
                category=ErrorCategory.SERVICE,
                severity=ErrorSeverity.MEDIUM,
                context=context,
                cause=error
            )
        else:
            doc_error = error
            if context and not doc_error.context.job_id:
                doc_error.context = context
        
        # Log the error
        self.logger.log_error(doc_error)
        
        # Generate recovery actions
        recovery_actions = self._get_recovery_actions(doc_error)
        
        # Create response
        response = ErrorResponse(
            status=ResponseStatus.RETRY if doc_error.recoverable else ResponseStatus.ERROR,
            message=doc_error.message,
            error_code=doc_error.error_code,
            details=doc_error.to_dict(),
            suggestions=doc_error.suggestions,
            recovery_actions=recovery_actions
        )
        
        return response
    
    def _get_recovery_actions(self, error: DocumentTranslationError) -> List[RecoveryAction]:
        """Get recovery actions for an error."""
        actions = []
        
        # Get pattern-based actions
        if error.error_code in self.error_patterns:
            actions.extend(self.error_patterns[error.error_code])
        
        # Add category-based actions
        category_actions = self._get_category_actions(error.category)
        actions.extend(category_actions)
        
        # Sort by priority
        actions.sort(key=lambda x: x.priority)
        
        return actions
    
    def _get_category_actions(self, category: ErrorCategory) -> List[RecoveryAction]:
        """Get recovery actions based on error category."""
        category_actions = {
            ErrorCategory.FILE_PROCESSING: [
                RecoveryAction(
                    action_type="file_validation",
                    description="Re-validate file format and integrity",
                    priority=3
                )
            ],
            ErrorCategory.TRANSLATION: [
                RecoveryAction(
                    action_type="translation_retry",
                    description="Retry translation with different parameters",
                    priority=3
                )
            ],
            ErrorCategory.LAYOUT_PROCESSING: [
                RecoveryAction(
                    action_type="layout_simplification",
                    description="Simplify layout processing",
                    priority=3
                )
            ],
            ErrorCategory.RESOURCE: [
                RecoveryAction(
                    action_type="resource_optimization",
                    description="Optimize resource usage",
                    priority=3
                )
            ]
        }
        
        return category_actions.get(category, [])
    
    def register_recovery_handler(self, error_code: str, 
                                handler: Callable[[DocumentTranslationError], bool]):
        """Register a custom recovery handler for an error code."""
        self.recovery_handlers[error_code] = handler
    
    def attempt_recovery(self, error: DocumentTranslationError) -> bool:
        """Attempt automatic recovery for an error."""
        if error.error_code in self.recovery_handlers:
            try:
                return self.recovery_handlers[error.error_code](error)
            except Exception as e:
                self.logger.log_error(
                    DocumentTranslationError(
                        message=f"Recovery handler failed: {str(e)}",
                        error_code="RECOVERY_001",
                        category=ErrorCategory.SERVICE,
                        cause=e
                    )
                )
        
        return False
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        base_stats = self.logger.get_error_statistics()
        
        # Add recovery statistics
        recovery_stats = {
            'registered_handlers': len(self.recovery_handlers),
            'recovery_patterns': len(self.error_patterns)
        }
        
        return {
            **base_stats,
            'recovery': recovery_stats
        }
    
    def suggest_recovery_actions(self, error: DocumentTranslationError) -> List[str]:
        """Generate user-friendly recovery suggestions."""
        suggestions = error.suggestions.copy()
        
        # Add context-specific suggestions
        if error.context.stage:
            stage_suggestions = self._get_stage_suggestions(error.context.stage)
            suggestions.extend(stage_suggestions)
        
        # Add severity-based suggestions
        if error.severity == ErrorSeverity.CRITICAL:
            suggestions.append("Contact system administrator immediately")
        elif error.severity == ErrorSeverity.HIGH:
            suggestions.append("Consider alternative processing methods")
        
        return list(set(suggestions))  # Remove duplicates
    
    def _get_stage_suggestions(self, stage: str) -> List[str]:
        """Get suggestions based on processing stage."""
        stage_suggestions = {
            'parsing': [
                "Verify document is not password protected",
                "Check if document opens in its native application"
            ],
            'translation': [
                "Check internet connection for translation services",
                "Verify language codes are correct"
            ],
            'layout_analysis': [
                "Ensure document has clear text regions",
                "Check for complex layouts or unusual formatting"
            ],
            'reconstruction': [
                "Try exporting to a simpler format",
                "Check if all fonts are available"
            ]
        }
        
        return stage_suggestions.get(stage, [])
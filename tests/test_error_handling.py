"""Tests for the comprehensive error handling system."""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime

from src.errors.exceptions import (
    DocumentTranslationError,
    FileProcessingError,
    InvalidFileFormatError,
    FileSizeExceededError,
    TranslationError,
    UnsupportedLanguagePairError,
    TranslationServiceError,
    QualityThresholdError,
    LayoutProcessingError,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext
)

from src.errors.handlers import (
    ErrorHandler,
    ErrorResponse,
    RecoveryAction,
    ErrorLogger,
    ResponseStatus
)

from src.errors.recovery import (
    RecoveryManager,
    RetryStrategy,
    FallbackServiceStrategy,
    ResourceOptimizationStrategy,
    AutoRecoveryHandler,
    RecoveryStatus
)


class TestDocumentTranslationError:
    """Test cases for DocumentTranslationError and subclasses."""
    
    def test_base_error_creation(self):
        """Test basic error creation."""
        context = ErrorContext(job_id="test_job", stage="parsing")
        error = DocumentTranslationError(
            message="Test error",
            error_code="TEST_001",
            category=ErrorCategory.FILE_PROCESSING,
            severity=ErrorSeverity.HIGH,
            context=context
        )
        
        assert error.message == "Test error"
        assert error.error_code == "TEST_001"
        assert error.category == ErrorCategory.FILE_PROCESSING
        assert error.severity == ErrorSeverity.HIGH
        assert error.context.job_id == "test_job"
        assert not error.recoverable
    
    def test_error_to_dict(self):
        """Test error serialization to dictionary."""
        error = DocumentTranslationError(
            message="Test error",
            error_code="TEST_001",
            category=ErrorCategory.TRANSLATION,
            suggestions=["Try again", "Check settings"]
        )
        
        error_dict = error.to_dict()
        
        assert error_dict['message'] == "Test error"
        assert error_dict['error_code'] == "TEST_001"
        assert error_dict['category'] == "translation"
        assert error_dict['suggestions'] == ["Try again", "Check settings"]
    
    def test_invalid_file_format_error(self):
        """Test InvalidFileFormatError creation."""
        error = InvalidFileFormatError(
            file_format="txt",
            supported_formats=["pdf", "docx", "epub"]
        )
        
        assert "Unsupported file format: txt" in error.message
        assert "pdf, docx, epub" in error.message
        assert error.error_code == "FILE_001"
        assert len(error.suggestions) > 0
    
    def test_file_size_exceeded_error(self):
        """Test FileSizeExceededError creation."""
        error = FileSizeExceededError(
            file_size=10000000,
            max_size=5000000
        )
        
        assert "10000000 bytes" in error.message
        assert "5000000 bytes" in error.message
        assert error.error_code == "FILE_002"
    
    def test_translation_service_error(self):
        """Test TranslationServiceError creation."""
        error = TranslationServiceError(
            service_name="google_translate",
            details="API quota exceeded"
        )
        
        assert "google_translate" in error.message
        assert "API quota exceeded" in error.message
        assert error.error_code == "TRANS_002"
        assert error.recoverable
    
    def test_quality_threshold_error(self):
        """Test QualityThresholdError creation."""
        error = QualityThresholdError(
            quality_score=0.65,
            threshold=0.8
        )
        
        assert "0.65" in error.message
        assert "0.80" in error.message
        assert error.error_code == "TRANS_004"


class TestErrorHandler:
    """Test cases for ErrorHandler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    def test_handle_document_translation_error(self):
        """Test handling DocumentTranslationError."""
        error = DocumentTranslationError(
            message="Test error",
            error_code="TEST_001",
            category=ErrorCategory.TRANSLATION,
            recoverable=True
        )
        
        response = self.error_handler.handle_error(error)
        
        assert isinstance(response, ErrorResponse)
        assert response.status == ResponseStatus.RETRY
        assert response.message == "Test error"
        assert response.error_code == "TEST_001"
    
    def test_handle_generic_exception(self):
        """Test handling generic Python exception."""
        error = ValueError("Generic error")
        
        response = self.error_handler.handle_error(error)
        
        assert isinstance(response, ErrorResponse)
        assert response.status == ResponseStatus.ERROR
        assert "Generic error" in response.message
        assert response.error_code == "UNKNOWN_001"
    
    def test_recovery_actions_generation(self):
        """Test recovery actions generation."""
        error = TranslationServiceError(
            service_name="test_service",
            details="Connection failed"
        )
        
        response = self.error_handler.handle_error(error)
        
        assert len(response.recovery_actions) > 0
        # Should have retry action for service errors
        retry_actions = [
            action for action in response.recovery_actions 
            if action.action_type == "retry"
        ]
        assert len(retry_actions) > 0
    
    def test_error_statistics(self):
        """Test error statistics collection."""
        # Generate some errors
        for i in range(3):
            error = DocumentTranslationError(
                message=f"Error {i}",
                error_code="TEST_001",
                category=ErrorCategory.TRANSLATION
            )
            self.error_handler.handle_error(error)
        
        stats = self.error_handler.get_error_statistics()
        
        assert stats['total_errors'] == 3
        assert stats['error_counts_by_code']['TEST_001'] == 3
        assert len(stats['recent_errors']) == 3


class TestErrorLogger:
    """Test cases for ErrorLogger."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.logger = ErrorLogger("test_logger")
    
    def test_log_error(self):
        """Test error logging."""
        error = DocumentTranslationError(
            message="Test error",
            error_code="TEST_001",
            category=ErrorCategory.FILE_PROCESSING,
            severity=ErrorSeverity.HIGH
        )
        
        self.logger.log_error(error)
        
        assert self.logger.error_counts["TEST_001"] == 1
        assert len(self.logger.error_history) == 1
    
    def test_error_statistics(self):
        """Test error statistics generation."""
        # Log multiple errors
        for i in range(5):
            error = DocumentTranslationError(
                message=f"Error {i}",
                error_code=f"TEST_{i:03d}",
                category=ErrorCategory.TRANSLATION
            )
            self.logger.log_error(error)
        
        stats = self.logger.get_error_statistics()
        
        assert stats['total_errors'] == 5
        assert len(stats['error_counts_by_code']) == 5
        assert len(stats['recent_errors']) == 5


class TestRecoveryStrategies:
    """Test cases for recovery strategies."""
    
    @pytest_asyncio.async_test
    async def test_retry_strategy(self):
        """Test RetryStrategy."""
        strategy = RetryStrategy(max_retries=2, backoff_factor=1.0)
        
        error = TranslationServiceError(
            service_name="test_service",
            details="Temporary failure"
        )
        
        assert strategy.can_handle(error)
        
        context = {'retry_count': 0}
        success, message = await strategy.execute(error, context)
        
        assert success
        assert context['retry_count'] == 1
        assert "attempt 1" in message
    
    @pytest_asyncio.async_test
    async def test_retry_strategy_max_retries(self):
        """Test RetryStrategy with max retries exceeded."""
        strategy = RetryStrategy(max_retries=2)
        
        error = TranslationServiceError(
            service_name="test_service",
            details="Persistent failure"
        )
        
        context = {'retry_count': 2}
        success, message = await strategy.execute(error, context)
        
        assert not success
        assert "Maximum retries" in message
    
    @pytest_asyncio.async_test
    async def test_fallback_service_strategy(self):
        """Test FallbackServiceStrategy."""
        strategy = FallbackServiceStrategy(['service1', 'service2', 'service3'])
        
        error = TranslationServiceError(
            service_name="original_service",
            details="Service unavailable"
        )
        
        assert strategy.can_handle(error)
        
        context = {'current_service': 'original_service', 'used_services': []}
        success, message = await strategy.execute(error, context)
        
        assert success
        assert context['current_service'] == 'service1'
        assert 'original_service' in context['used_services']
    
    @pytest_asyncio.async_test
    async def test_resource_optimization_strategy(self):
        """Test ResourceOptimizationStrategy."""
        strategy = ResourceOptimizationStrategy()
        
        from src.errors.exceptions import MemoryExceededError
        error = MemoryExceededError(current_usage=2048, limit=1024)
        
        assert strategy.can_handle(error)
        
        context = {'batch_size': 10}
        success, message = await strategy.execute(error, context)
        
        assert success
        assert context['low_memory_mode'] is True
        assert context['batch_size'] == 5
        assert "low-memory mode" in message


class TestRecoveryManager:
    """Test cases for RecoveryManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.recovery_manager = RecoveryManager()
    
    @pytest_asyncio.async_test
    async def test_attempt_recovery_success(self):
        """Test successful recovery attempt."""
        error = TranslationServiceError(
            service_name="test_service",
            details="Temporary failure"
        )
        
        context = {'retry_count': 0}
        success, attempts = await self.recovery_manager.attempt_recovery(error, context)
        
        assert success
        assert len(attempts) > 0
        assert attempts[0].status == RecoveryStatus.SUCCESS
    
    @pytest_asyncio.async_test
    async def test_attempt_recovery_no_strategies(self):
        """Test recovery attempt with no applicable strategies."""
        error = DocumentTranslationError(
            message="Unrecoverable error",
            error_code="UNRECOVERABLE_001",
            category=ErrorCategory.VALIDATION
        )
        
        success, attempts = await self.recovery_manager.attempt_recovery(error)
        
        assert not success
        assert len(attempts) == 0
    
    def test_recovery_statistics(self):
        """Test recovery statistics generation."""
        # Add some mock recovery attempts
        from src.errors.recovery import RecoveryAttempt
        
        attempt = RecoveryAttempt(
            action=RecoveryAction(
                action_type="TestStrategy",
                description="Test recovery"
            ),
            status=RecoveryStatus.SUCCESS,
            start_time=1000.0,
            end_time=1001.0
        )
        
        self.recovery_manager.recovery_history.append(attempt)
        
        stats = self.recovery_manager.get_recovery_statistics()
        
        assert stats['total_attempts'] == 1
        assert stats['successful_attempts'] == 1
        assert stats['success_rate'] == 1.0


class TestAutoRecoveryHandler:
    """Test cases for AutoRecoveryHandler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
        self.recovery_manager = RecoveryManager()
        self.auto_recovery = AutoRecoveryHandler(
            self.error_handler, 
            self.recovery_manager
        )
    
    @pytest_asyncio.async_test
    async def test_handle_error_with_recovery(self):
        """Test error handling with recovery."""
        error = TranslationServiceError(
            service_name="test_service",
            details="Temporary failure"
        )
        
        context = ErrorContext(job_id="test_job")
        job_context = {'retry_count': 0}
        
        result = await self.auto_recovery.handle_error_with_recovery(
            error, context, job_context
        )
        
        assert 'error_response' in result
        assert 'recovery_attempted' in result
        assert 'recovery_successful' in result
        assert result['recovery_attempted'] is True
    
    @pytest_asyncio.async_test
    async def test_handle_non_recoverable_error(self):
        """Test handling non-recoverable error."""
        error = DocumentTranslationError(
            message="Non-recoverable error",
            error_code="FATAL_001",
            category=ErrorCategory.VALIDATION,
            recoverable=False
        )
        
        context = ErrorContext(job_id="test_job")
        job_context = {}
        
        result = await self.auto_recovery.handle_error_with_recovery(
            error, context, job_context
        )
        
        assert result['recovery_attempted'] is False
        assert result['recovery_successful'] is False
    
    def test_is_recovery_active(self):
        """Test recovery active status tracking."""
        job_id = "test_job"
        
        assert not self.auto_recovery.is_recovery_active(job_id)
        
        self.auto_recovery.active_recoveries[job_id] = True
        assert self.auto_recovery.is_recovery_active(job_id)


class TestIntegrationScenarios:
    """Integration tests for complete error handling scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
        self.recovery_manager = RecoveryManager()
        self.auto_recovery = AutoRecoveryHandler(
            self.error_handler,
            self.recovery_manager
        )
    
    @pytest_asyncio.async_test
    async def test_translation_service_failure_recovery(self):
        """Test complete recovery flow for translation service failure."""
        # Simulate translation service failure
        error = TranslationServiceError(
            service_name="primary_service",
            details="Service temporarily unavailable"
        )
        
        context = ErrorContext(
            job_id="translation_job_123",
            stage="translation",
            component="translation_service"
        )
        
        job_context = {
            'current_service': 'primary_service',
            'used_services': [],
            'retry_count': 0
        }
        
        # Handle error with recovery
        result = await self.auto_recovery.handle_error_with_recovery(
            error, context, job_context
        )
        
        # Verify error was handled
        assert result['error_response']['status'] == 'retry'
        assert result['recovery_attempted'] is True
        
        # Verify recovery was successful
        if result['recovery_successful']:
            assert len(result['recovery_attempts']) > 0
            successful_attempts = [
                attempt for attempt in result['recovery_attempts']
                if attempt['status'] == 'success'
            ]
            assert len(successful_attempts) > 0
    
    @pytest.mark.asyncio
    async def test_file_processing_error_handling(self):
        """Test file processing error handling."""
        error = InvalidFileFormatError(
            file_format="txt",
            supported_formats=["pdf", "docx", "epub"]
        )
        
        context = ErrorContext(
            job_id="upload_job_456",
            file_path="/tmp/document.txt",
            stage="parsing"
        )
        
        # Handle error (no recovery expected for format errors)
        result = await self.auto_recovery.handle_error_with_recovery(
            error, context, {}
        )
        
        # Verify error response
        assert result['error_response']['error_code'] == 'FILE_001'
        assert 'Unsupported file format' in result['error_response']['message']
        assert len(result['error_response']['suggestions']) > 0
        
        # Format errors are typically not recoverable automatically
        assert result['recovery_attempted'] is False
    
    def test_error_statistics_collection(self):
        """Test comprehensive error statistics collection."""
        # Generate various types of errors
        errors = [
            InvalidFileFormatError("txt", ["pdf", "docx"]),
            TranslationServiceError("service1", "Connection failed"),
            QualityThresholdError(0.6, 0.8),
            FileSizeExceededError(10000, 5000)
        ]
        
        for error in errors:
            self.error_handler.handle_error(error)
        
        # Get statistics
        stats = self.error_handler.get_error_statistics()
        
        assert stats['total_errors'] == 4
        assert len(stats['error_counts_by_code']) == 4
        assert 'FILE_001' in stats['error_counts_by_code']
        assert 'TRANS_002' in stats['error_counts_by_code']
        assert 'TRANS_004' in stats['error_counts_by_code']
        assert 'FILE_002' in stats['error_counts_by_code']


if __name__ == "__main__":
    pytest.main([__file__])
"""Example integration of comprehensive error handling with services."""

import asyncio
from typing import Optional

from .exceptions import (
    DocumentTranslationError,
    FileProcessingError,
    InvalidFileFormatError,
    TranslationServiceError,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory
)

from .handlers import ErrorHandler, ErrorResponse
from .recovery import RecoveryManager, AutoRecoveryHandler


class ExampleTranslationService:
    """Example service showing error handling integration."""
    
    def __init__(self):
        """Initialize service with error handling."""
        self.error_handler = ErrorHandler()
        self.recovery_manager = RecoveryManager()
        self.auto_recovery = AutoRecoveryHandler(
            self.error_handler, 
            self.recovery_manager
        )
    
    async def translate_document(self, file_path: str, source_lang: str, 
                               target_lang: str) -> dict:
        """Translate document with comprehensive error handling."""
        
        context = ErrorContext(
            file_path=file_path,
            stage="translation",
            component="translation_service",
            metadata={
                'source_lang': source_lang,
                'target_lang': target_lang
            }
        )
        
        try:
            # Simulate file validation
            if not file_path.endswith(('.pdf', '.docx', '.epub')):
                raise InvalidFileFormatError(
                    file_format=file_path.split('.')[-1],
                    supported_formats=['pdf', 'docx', 'epub'],
                    context=context
                )
            
            # Simulate translation service call
            if source_lang == target_lang:
                raise DocumentTranslationError(
                    message="Source and target languages cannot be the same",
                    error_code="TRANS_005",
                    category=ErrorCategory.VALIDATION,
                    context=context
                )
            
            # Simulate service failure
            if target_lang == "unsupported":
                raise TranslationServiceError(
                    service_name="example_translator",
                    details="Language not supported",
                    context=context
                )
            
            # Simulate successful translation
            return {
                'status': 'success',
                'translated_text': f"Translated from {source_lang} to {target_lang}",
                'quality_score': 0.95
            }
            
        except Exception as error:
            # Handle error with recovery
            job_context = {
                'source_lang': source_lang,
                'target_lang': target_lang,
                'retry_count': 0,
                'max_retries': 3
            }
            
            result = await self.auto_recovery.handle_error_with_recovery(
                error, context, job_context
            )
            
            return {
                'status': 'error',
                'error_response': result['error_response'],
                'recovery_attempted': result['recovery_attempted'],
                'recovery_successful': result['recovery_successful']
            }
    
    def get_error_statistics(self) -> dict:
        """Get error statistics for monitoring."""
        return {
            'error_handler': self.error_handler.get_error_statistics(),
            'recovery_manager': self.recovery_manager.get_recovery_statistics()
        }


async def demonstrate_error_handling():
    """Demonstrate the error handling system."""
    
    service = ExampleTranslationService()
    
    print("=== Error Handling System Demonstration ===\n")
    
    # Test 1: Invalid file format
    print("1. Testing invalid file format...")
    result = await service.translate_document("document.txt", "en", "fr")
    print(f"Result: {result['status']}")
    if result['status'] == 'error':
        error_response = result['error_response']
        print(f"Error: {error_response['message']}")
        print(f"Suggestions: {error_response['suggestions']}")
    print()
    
    # Test 2: Same source and target language
    print("2. Testing validation error...")
    result = await service.translate_document("document.pdf", "en", "en")
    print(f"Result: {result['status']}")
    if result['status'] == 'error':
        error_response = result['error_response']
        print(f"Error: {error_response['message']}")
    print()
    
    # Test 3: Service failure with recovery
    print("3. Testing service failure with recovery...")
    result = await service.translate_document("document.pdf", "en", "unsupported")
    print(f"Result: {result['status']}")
    if result['status'] == 'error':
        print(f"Recovery attempted: {result['recovery_attempted']}")
        print(f"Recovery successful: {result['recovery_successful']}")
        if result['recovery_attempted']:
            print(f"Recovery attempts: {len(result.get('recovery_attempts', []))}")
    print()
    
    # Test 4: Successful translation
    print("4. Testing successful translation...")
    result = await service.translate_document("document.pdf", "en", "fr")
    print(f"Result: {result['status']}")
    if result['status'] == 'success':
        print(f"Translation: {result['translated_text']}")
        print(f"Quality: {result['quality_score']}")
    print()
    
    # Show error statistics
    print("5. Error Statistics:")
    stats = service.get_error_statistics()
    print(f"Total errors: {stats['error_handler']['total_errors']}")
    print(f"Recovery attempts: {stats['recovery_manager']['total_attempts']}")
    print(f"Recovery success rate: {stats['recovery_manager']['success_rate']:.2%}")


if __name__ == "__main__":
    asyncio.run(demonstrate_error_handling())
"""Translation services and language detection."""

from .base import TranslationService
from .language_detection import LanguageDetectionService

__all__ = [
    'TranslationService',
    'LanguageDetectionService',
]
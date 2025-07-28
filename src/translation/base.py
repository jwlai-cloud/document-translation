"""Base classes for translation services."""

from abc import ABC, abstractmethod
from typing import List
from src.models.translation import LanguageDetection, TranslatedRegion
from src.models.layout import TextRegion


class TranslationService(ABC):
    """Abstract base class for translation services."""
    
    @abstractmethod
    def detect_language(self, text: str) -> LanguageDetection:
        """Detect the language of the given text.
        
        Args:
            text: Text to analyze
            
        Returns:
            LanguageDetection with detected language and confidence
        """
        pass
    
    @abstractmethod
    def translate_with_context(self, regions: List[TextRegion], 
                             source_lang: str, target_lang: str) -> List[TranslatedRegion]:
        """Translate text regions with context awareness.
        
        Args:
            regions: List of text regions to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            List of translated regions with confidence scores
        """
        pass
    
    @abstractmethod
    def preserve_formatting(self, original: TextRegion, translated: str):
        """Preserve formatting in translated text.
        
        Args:
            original: Original text region with formatting
            translated: Translated text content
            
        Returns:
            FormattedText with preserved formatting
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes.
        
        Returns:
            List of supported language codes
        """
        pass
    
    @abstractmethod
    def validate_language_pair(self, source_lang: str, target_lang: str) -> bool:
        """Validate if a language pair is supported.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            True if language pair is supported
        """
        pass
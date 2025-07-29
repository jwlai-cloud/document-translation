"""Language detection service using langdetect library."""

from langdetect import detect, detect_langs, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from typing import List, Dict, Optional, Tuple
import logging
import re
from collections import Counter

from .base import TranslationService
from src.models.translation import LanguageDetection
from src.models.document import DocumentStructure, TextRegion
from src.config import SUPPORTED_LANGUAGES, LANGUAGE_NAMES


# Set seed for consistent results
DetectorFactory.seed = 0


class LanguageDetectionService:
    """Service for detecting languages in text and documents."""
    
    def __init__(self):
        """Initialize the language detection service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.min_text_length = 10  # Minimum text length for reliable detection
        self.confidence_threshold = 0.7  # Minimum confidence for reliable detection
    
    def detect_language(self, text: str) -> LanguageDetection:
        """Detect the language of the given text.
        
        Args:
            text: Text to analyze
            
        Returns:
            LanguageDetection with detected language and confidence
        """
        try:
            # Clean and validate text
            cleaned_text = self._clean_text_for_detection(text)
            
            if len(cleaned_text) < self.min_text_length:
                return LanguageDetection(
                    detected_language="unknown",
                    confidence=0.0,
                    alternative_languages=[],
                    detection_method="insufficient_text"
                )
            
            # Detect language with probabilities
            lang_probs = detect_langs(cleaned_text)
            
            if not lang_probs:
                return LanguageDetection(
                    detected_language="unknown",
                    confidence=0.0,
                    alternative_languages=[],
                    detection_method="detection_failed"
                )
            
            # Get primary language
            primary_lang = lang_probs[0]
            detected_lang = primary_lang.lang
            confidence = primary_lang.prob
            
            # Map to supported language if possible
            mapped_lang = self._map_to_supported_language(detected_lang)
            
            # Get alternative languages
            alternatives = []
            for lang_prob in lang_probs[1:5]:  # Top 4 alternatives
                alt_lang = self._map_to_supported_language(lang_prob.lang)
                if alt_lang != mapped_lang:  # Don't include same language
                    alternatives.append((alt_lang, lang_prob.prob))
            
            self.logger.info(
                f"Detected language: {mapped_lang} "
                f"(confidence: {confidence:.3f})"
            )
            
            return LanguageDetection(
                detected_language=mapped_lang,
                confidence=confidence,
                alternative_languages=alternatives,
                detection_method="langdetect"
            )
            
        except LangDetectException as e:
            self.logger.warning(f"Language detection failed: {str(e)}")
            return LanguageDetection(
                detected_language="unknown",
                confidence=0.0,
                alternative_languages=[],
                detection_method="detection_error"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in language detection: {str(e)}")
            return LanguageDetection(
                detected_language="unknown",
                confidence=0.0,
                alternative_languages=[],
                detection_method="unexpected_error"
            )
    
    def detect_document_language(self, document: DocumentStructure) -> LanguageDetection:
        """Detect the primary language of a document.
        
        Args:
            document: Document structure to analyze
            
        Returns:
            LanguageDetection for the document's primary language
        """
        try:
            # Collect all text from the document
            all_text = document.get_total_text_content()
            
            if not all_text.strip():
                return LanguageDetection(
                    detected_language="unknown",
                    confidence=0.0,
                    alternative_languages=[],
                    detection_method="no_text_content"
                )
            
            # Detect language for the entire document
            detection = self.detect_language(all_text)
            
            # If confidence is low, try page-by-page detection
            if detection.confidence < self.confidence_threshold:
                page_detections = self._detect_by_pages(document)
                if page_detections:
                    # Use majority vote from pages
                    detection = self._combine_page_detections(page_detections)
            
            self.logger.info(
                f"Document language detected: {detection.detected_language} "
                f"(confidence: {detection.confidence:.3f})"
            )
            
            return detection
            
        except Exception as e:
            self.logger.error(f"Document language detection failed: {str(e)}")
            return LanguageDetection(
                detected_language="unknown",
                confidence=0.0,
                alternative_languages=[],
                detection_method="document_detection_error"
            )
    
    def detect_text_regions_languages(self, text_regions: List[TextRegion]) -> List[LanguageDetection]:
        """Detect languages for individual text regions.
        
        Args:
            text_regions: List of text regions to analyze
            
        Returns:
            List of LanguageDetection objects for each region
        """
        detections = []
        
        for region in text_regions:
            detection = self.detect_language(region.text_content)
            detections.append(detection)
        
        return detections
    
    def is_detection_reliable(self, detection: LanguageDetection) -> bool:
        """Check if a language detection is reliable.
        
        Args:
            detection: LanguageDetection to evaluate
            
        Returns:
            True if detection is considered reliable
        """
        return (
            detection.confidence >= self.confidence_threshold and
            detection.detected_language != "unknown" and
            detection.detected_language in SUPPORTED_LANGUAGES
        )
    
    def get_language_suggestions(self, detection: LanguageDetection) -> List[str]:
        """Get language suggestions when detection is unreliable.
        
        Args:
            detection: LanguageDetection with low confidence
            
        Returns:
            List of suggested language codes
        """
        suggestions = []
        
        # Add alternatives if they're supported
        for alt_lang, confidence in detection.alternative_languages:
            if alt_lang in SUPPORTED_LANGUAGES and confidence > 0.3:
                suggestions.append(alt_lang)
        
        # Add common languages if no good alternatives
        if not suggestions:
            common_languages = ["en", "es", "fr", "de", "zh", "ja"]
            suggestions = [lang for lang in common_languages if lang in SUPPORTED_LANGUAGES]
        
        return suggestions[:5]  # Limit to top 5 suggestions
    
    def _clean_text_for_detection(self, text: str) -> str:
        """Clean text for better language detection.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text suitable for detection
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove URLs
        cleaned = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', cleaned)
        
        # Remove email addresses
        cleaned = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', cleaned)
        
        # Remove numbers and special characters that don't help with language detection
        cleaned = re.sub(r'[0-9]+', '', cleaned)
        cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
        
        # Remove excessive whitespace again
        cleaned = re.sub(r'\s+', ' ', cleaned.strip())
        
        return cleaned
    
    def _map_to_supported_language(self, detected_lang: str) -> str:
        """Map detected language to supported language code.
        
        Args:
            detected_lang: Language code from detection
            
        Returns:
            Supported language code or original if supported
        """
        # Direct mapping for supported languages
        if detected_lang in SUPPORTED_LANGUAGES:
            return detected_lang
        
        # Language code mappings
        language_mappings = {
            'zh-cn': 'zh',  # Chinese (Simplified)
            'zh-tw': 'zh',  # Chinese (Traditional) -> Simplified
            'pt-br': 'pt',  # Portuguese (Brazil) -> Portuguese
            'pt-pt': 'pt',  # Portuguese (Portugal) -> Portuguese
            'es-es': 'es',  # Spanish (Spain) -> Spanish
            'es-mx': 'es',  # Spanish (Mexico) -> Spanish
            'en-us': 'en',  # English (US) -> English
            'en-gb': 'en',  # English (UK) -> English
            'fr-fr': 'fr',  # French (France) -> French
            'fr-ca': 'fr',  # French (Canada) -> French
            'de-de': 'de',  # German (Germany) -> German
            'it-it': 'it',  # Italian (Italy) -> Italian
            'ru-ru': 'ru',  # Russian (Russia) -> Russian
            'ko-kr': 'ko',  # Korean (Korea) -> Korean
            'ja-jp': 'ja',  # Japanese (Japan) -> Japanese
        }
        
        mapped = language_mappings.get(detected_lang.lower())
        if mapped and mapped in SUPPORTED_LANGUAGES:
            return mapped
        
        # If no mapping found, return original
        return detected_lang
    
    def _detect_by_pages(self, document: DocumentStructure) -> List[LanguageDetection]:
        """Detect language for each page separately.
        
        Args:
            document: Document to analyze page by page
            
        Returns:
            List of LanguageDetection objects for each page
        """
        page_detections = []
        
        for page in document.pages:
            page_text = page.get_text_content()
            if page_text.strip():
                detection = self.detect_language(page_text)
                page_detections.append(detection)
        
        return page_detections
    
    def _combine_page_detections(self, page_detections: List[LanguageDetection]) -> LanguageDetection:
        """Combine multiple page detections into a single result.
        
        Args:
            page_detections: List of page-level detections
            
        Returns:
            Combined LanguageDetection
        """
        if not page_detections:
            return LanguageDetection(
                detected_language="unknown",
                confidence=0.0,
                alternative_languages=[],
                detection_method="no_page_detections"
            )
        
        # Count language occurrences weighted by confidence
        language_scores = Counter()
        total_confidence = 0
        
        for detection in page_detections:
            if detection.detected_language != "unknown":
                weight = detection.confidence
                language_scores[detection.detected_language] += weight
                total_confidence += weight
        
        if not language_scores:
            return LanguageDetection(
                detected_language="unknown",
                confidence=0.0,
                alternative_languages=[],
                detection_method="no_reliable_detections"
            )
        
        # Get most common language
        most_common_lang = language_scores.most_common(1)[0][0]
        combined_confidence = language_scores[most_common_lang] / total_confidence
        
        # Get alternatives
        alternatives = []
        for lang, score in language_scores.most_common()[1:4]:
            if lang != most_common_lang:
                alt_confidence = score / total_confidence
                alternatives.append((lang, alt_confidence))
        
        return LanguageDetection(
            detected_language=most_common_lang,
            confidence=combined_confidence,
            alternative_languages=alternatives,
            detection_method="page_majority_vote"
        )
    
    def get_language_name(self, language_code: str) -> str:
        """Get human-readable language name.
        
        Args:
            language_code: Language code (e.g., 'en', 'fr')
            
        Returns:
            Human-readable language name
        """
        return LANGUAGE_NAMES.get(language_code, language_code.upper())
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes.
        
        Returns:
            List of supported language codes
        """
        return SUPPORTED_LANGUAGES.copy()
    
    def get_supported_language_names(self) -> Dict[str, str]:
        """Get mapping of language codes to names.
        
        Returns:
            Dictionary mapping codes to names
        """
        return LANGUAGE_NAMES.copy()
    
    def validate_language_code(self, language_code: str) -> bool:
        """Validate if a language code is supported.
        
        Args:
            language_code: Language code to validate
            
        Returns:
            True if language code is supported
        """
        return language_code in SUPPORTED_LANGUAGES
    
    def get_detection_statistics(self, detections: List[LanguageDetection]) -> Dict[str, any]:
        """Get statistics about a set of language detections.
        
        Args:
            detections: List of language detections
            
        Returns:
            Dictionary with detection statistics
        """
        if not detections:
            return {
                "total_detections": 0,
                "reliable_detections": 0,
                "average_confidence": 0.0,
                "language_distribution": {},
                "detection_methods": {}
            }
        
        reliable_count = sum(1 for d in detections if self.is_detection_reliable(d))
        total_confidence = sum(d.confidence for d in detections)
        average_confidence = total_confidence / len(detections)
        
        # Language distribution
        lang_counts = Counter(d.detected_language for d in detections)
        
        # Detection method distribution
        method_counts = Counter(d.detection_method for d in detections)
        
        return {
            "total_detections": len(detections),
            "reliable_detections": reliable_count,
            "reliability_rate": reliable_count / len(detections),
            "average_confidence": average_confidence,
            "language_distribution": dict(lang_counts),
            "detection_methods": dict(method_counts)
        }
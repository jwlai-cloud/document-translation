"""Tests for language detection service."""

import pytest
from unittest.mock import Mock, patch
from collections import Counter

from src.translation.language_detection import LanguageDetectionService
from src.models.translation import LanguageDetection
from src.models.document import DocumentStructure, PageStructure, TextRegion, Dimensions, BoundingBox


class TestLanguageDetectionService:
    """Test cases for LanguageDetectionService."""
    
    def test_initialization(self):
        """Test language detection service initialization."""
        service = LanguageDetectionService()
        
        assert hasattr(service, 'logger')
        assert service.min_text_length == 10
        assert service.confidence_threshold == 0.7
    
    @patch('src.translation.language_detection.detect_langs')
    def test_detect_language_success(self, mock_detect_langs):
        """Test successful language detection."""
        service = LanguageDetectionService()
        
        # Mock language detection results
        mock_lang1 = Mock()
        mock_lang1.lang = 'en'
        mock_lang1.prob = 0.85
        
        mock_lang2 = Mock()
        mock_lang2.lang = 'fr'
        mock_lang2.prob = 0.12
        
        mock_detect_langs.return_value = [mock_lang1, mock_lang2]
        
        result = service.detect_language("This is a test sentence in English.")
        
        assert isinstance(result, LanguageDetection)
        assert result.detected_language == 'en'
        assert result.confidence == 0.85
        assert len(result.alternative_languages) == 1
        assert result.alternative_languages[0] == ('fr', 0.12)
        assert result.detection_method == 'langdetect'
    
    @patch('src.translation.language_detection.detect_langs')
    def test_detect_language_insufficient_text(self, mock_detect_langs):
        """Test language detection with insufficient text."""
        service = LanguageDetectionService()
        
        result = service.detect_language("Hi")  # Too short
        
        assert result.detected_language == "unknown"
        assert result.confidence == 0.0
        assert result.detection_method == "insufficient_text"
        mock_detect_langs.assert_not_called()
    
    @patch('src.translation.language_detection.detect_langs')
    def test_detect_language_detection_failed(self, mock_detect_langs):
        """Test language detection when detection fails."""
        service = LanguageDetectionService()
        
        mock_detect_langs.return_value = []  # No results
        
        result = service.detect_language("This is a longer text that should be detectable.")
        
        assert result.detected_language == "unknown"
        assert result.confidence == 0.0
        assert result.detection_method == "detection_failed"
    
    @patch('src.translation.language_detection.detect_langs')
    def test_detect_language_exception_handling(self, mock_detect_langs):
        """Test language detection exception handling."""
        service = LanguageDetectionService()
        
        from langdetect.lang_detect_exception import LangDetectException
        mock_detect_langs.side_effect = LangDetectException("Detection error", "ERROR")
        
        result = service.detect_language("This should cause an exception.")
        
        assert result.detected_language == "unknown"
        assert result.confidence == 0.0
        assert result.detection_method == "detection_error"
    
    def test_clean_text_for_detection(self):
        """Test text cleaning for detection."""
        service = LanguageDetectionService()
        
        # Test with URLs and emails
        dirty_text = "Visit https://example.com or email test@example.com for more info."
        cleaned = service._clean_text_for_detection(dirty_text)
        assert "https://example.com" not in cleaned
        assert "test@example.com" not in cleaned
        assert "Visit" in cleaned
        assert "for more info" in cleaned
        
        # Test with numbers and special characters
        dirty_text = "The price is $123.45 and the code is ABC-123!"
        cleaned = service._clean_text_for_detection(dirty_text)
        assert "$" not in cleaned
        assert "123" not in cleaned
        assert "45" not in cleaned
        assert "!" not in cleaned
        assert "The price is" in cleaned
        assert "and the code is ABC" in cleaned
        
        # Test with excessive whitespace
        dirty_text = "  Multiple   spaces    here  "
        cleaned = service._clean_text_for_detection(dirty_text)
        assert cleaned == "Multiple spaces here"
    
    def test_map_to_supported_language(self):
        """Test language code mapping."""
        service = LanguageDetectionService()
        
        # Test direct supported languages
        assert service._map_to_supported_language('en') == 'en'
        assert service._map_to_supported_language('fr') == 'fr'
        assert service._map_to_supported_language('zh') == 'zh'
        
        # Test language variants
        assert service._map_to_supported_language('zh-cn') == 'zh'
        assert service._map_to_supported_language('pt-br') == 'pt'
        assert service._map_to_supported_language('en-us') == 'en'
        
        # Test unsupported language
        assert service._map_to_supported_language('xyz') == 'xyz'
    
    def test_is_detection_reliable(self):
        """Test detection reliability checking."""
        service = LanguageDetectionService()
        
        # Reliable detection
        reliable = LanguageDetection(
            detected_language='en',
            confidence=0.85,
            alternative_languages=[],
            detection_method='langdetect'
        )
        assert service.is_detection_reliable(reliable) is True
        
        # Low confidence
        low_confidence = LanguageDetection(
            detected_language='en',
            confidence=0.5,
            alternative_languages=[],
            detection_method='langdetect'
        )
        assert service.is_detection_reliable(low_confidence) is False
        
        # Unknown language
        unknown = LanguageDetection(
            detected_language='unknown',
            confidence=0.9,
            alternative_languages=[],
            detection_method='langdetect'
        )
        assert service.is_detection_reliable(unknown) is False
        
        # Unsupported language
        unsupported = LanguageDetection(
            detected_language='xyz',
            confidence=0.9,
            alternative_languages=[],
            detection_method='langdetect'
        )
        assert service.is_detection_reliable(unsupported) is False
    
    def test_get_language_suggestions(self):
        """Test language suggestions for unreliable detections."""
        service = LanguageDetectionService()
        
        # Detection with good alternatives
        detection = LanguageDetection(
            detected_language='unknown',
            confidence=0.3,
            alternative_languages=[('en', 0.4), ('fr', 0.35), ('de', 0.25)],
            detection_method='langdetect'
        )
        
        suggestions = service.get_language_suggestions(detection)
        assert 'en' in suggestions
        assert 'fr' in suggestions
        # 'de' might be included if confidence > 0.3
        
        # Detection with no good alternatives
        detection_no_alt = LanguageDetection(
            detected_language='unknown',
            confidence=0.3,
            alternative_languages=[('xyz', 0.2)],
            detection_method='langdetect'
        )
        
        suggestions = service.get_language_suggestions(detection_no_alt)
        assert len(suggestions) > 0
        assert 'en' in suggestions  # Common language fallback
    
    @patch('src.translation.language_detection.detect_langs')
    def test_detect_document_language(self, mock_detect_langs):
        """Test document language detection."""
        service = LanguageDetectionService()
        
        # Mock detection result
        mock_lang = Mock()
        mock_lang.lang = 'en'
        mock_lang.prob = 0.9
        mock_detect_langs.return_value = [mock_lang]
        
        # Create test document
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        
        text_region = TextRegion(
            bounding_box=BoundingBox(x=0, y=0, width=100, height=20),
            text_content="This is English text for testing."
        )
        page.text_regions.append(text_region)
        doc.add_page(page)
        
        result = service.detect_document_language(doc)
        
        assert result.detected_language == 'en'
        assert result.confidence == 0.9
    
    def test_detect_document_language_no_text(self):
        """Test document language detection with no text."""
        service = LanguageDetectionService()
        
        # Create empty document
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        doc.add_page(page)
        
        result = service.detect_document_language(doc)
        
        assert result.detected_language == "unknown"
        assert result.confidence == 0.0
        assert result.detection_method == "no_text_content"
    
    @patch('src.translation.language_detection.detect_langs')
    def test_detect_text_regions_languages(self, mock_detect_langs):
        """Test language detection for text regions."""
        service = LanguageDetectionService()
        
        # Mock detection results
        mock_lang1 = Mock()
        mock_lang1.lang = 'en'
        mock_lang1.prob = 0.9
        
        mock_lang2 = Mock()
        mock_lang2.lang = 'fr'
        mock_lang2.prob = 0.85
        
        mock_detect_langs.side_effect = [[mock_lang1], [mock_lang2]]
        
        # Create test regions
        region1 = TextRegion(
            bounding_box=BoundingBox(x=0, y=0, width=100, height=20),
            text_content="This is English text."
        )
        region2 = TextRegion(
            bounding_box=BoundingBox(x=0, y=30, width=100, height=20),
            text_content="Ceci est du texte français."
        )
        
        results = service.detect_text_regions_languages([region1, region2])
        
        assert len(results) == 2
        assert results[0].detected_language == 'en'
        assert results[1].detected_language == 'fr'
    
    def test_combine_page_detections(self):
        """Test combining page detections."""
        service = LanguageDetectionService()
        
        # Create page detections
        detection1 = LanguageDetection(
            detected_language='en',
            confidence=0.8,
            alternative_languages=[],
            detection_method='langdetect'
        )
        detection2 = LanguageDetection(
            detected_language='en',
            confidence=0.9,
            alternative_languages=[],
            detection_method='langdetect'
        )
        detection3 = LanguageDetection(
            detected_language='fr',
            confidence=0.7,
            alternative_languages=[],
            detection_method='langdetect'
        )
        
        combined = service._combine_page_detections([detection1, detection2, detection3])
        
        # English should win (higher total score: 0.8 + 0.9 = 1.7 vs 0.7)
        assert combined.detected_language == 'en'
        assert combined.detection_method == 'page_majority_vote'
        assert len(combined.alternative_languages) == 1
        assert combined.alternative_languages[0][0] == 'fr'
    
    def test_combine_page_detections_empty(self):
        """Test combining empty page detections."""
        service = LanguageDetectionService()
        
        combined = service._combine_page_detections([])
        
        assert combined.detected_language == "unknown"
        assert combined.detection_method == "no_page_detections"
    
    def test_get_language_name(self):
        """Test getting language names."""
        service = LanguageDetectionService()
        
        assert service.get_language_name('en') == 'English'
        assert service.get_language_name('fr') == 'French'
        assert service.get_language_name('zh') == 'Simplified Chinese'
        assert service.get_language_name('xyz') == 'XYZ'  # Unknown language
    
    def test_get_supported_languages(self):
        """Test getting supported languages."""
        service = LanguageDetectionService()
        
        languages = service.get_supported_languages()
        assert isinstance(languages, list)
        assert 'en' in languages
        assert 'fr' in languages
        assert 'zh' in languages
    
    def test_get_supported_language_names(self):
        """Test getting supported language names."""
        service = LanguageDetectionService()
        
        names = service.get_supported_language_names()
        assert isinstance(names, dict)
        assert names['en'] == 'English'
        assert names['fr'] == 'French'
    
    def test_validate_language_code(self):
        """Test language code validation."""
        service = LanguageDetectionService()
        
        assert service.validate_language_code('en') is True
        assert service.validate_language_code('fr') is True
        assert service.validate_language_code('xyz') is False
        assert service.validate_language_code('') is False
    
    def test_get_detection_statistics(self):
        """Test detection statistics calculation."""
        service = LanguageDetectionService()
        
        # Create test detections
        detections = [
            LanguageDetection('en', 0.9, [], 'langdetect'),
            LanguageDetection('en', 0.8, [], 'langdetect'),
            LanguageDetection('fr', 0.6, [], 'langdetect'),  # Low confidence
            LanguageDetection('unknown', 0.0, [], 'detection_failed')
        ]
        
        stats = service.get_detection_statistics(detections)
        
        assert stats['total_detections'] == 4
        assert stats['reliable_detections'] == 2  # Only first two are reliable
        assert stats['reliability_rate'] == 0.5
        assert stats['average_confidence'] == 0.575  # (0.9 + 0.8 + 0.6 + 0.0) / 4
        assert stats['language_distribution']['en'] == 2
        assert stats['language_distribution']['fr'] == 1
        assert stats['language_distribution']['unknown'] == 1
        assert stats['detection_methods']['langdetect'] == 3
        assert stats['detection_methods']['detection_failed'] == 1
    
    def test_get_detection_statistics_empty(self):
        """Test detection statistics with empty list."""
        service = LanguageDetectionService()
        
        stats = service.get_detection_statistics([])
        
        assert stats['total_detections'] == 0
        assert stats['reliable_detections'] == 0
        assert stats['average_confidence'] == 0.0
        assert stats['language_distribution'] == {}
        assert stats['detection_methods'] == {}
    
    @patch('src.translation.language_detection.detect_langs')
    def test_detect_by_pages(self, mock_detect_langs):
        """Test page-by-page detection."""
        service = LanguageDetectionService()
        
        # Mock detection results
        mock_lang1 = Mock()
        mock_lang1.lang = 'en'
        mock_lang1.prob = 0.8
        
        mock_lang2 = Mock()
        mock_lang2.lang = 'fr'
        mock_lang2.prob = 0.9
        
        mock_detect_langs.side_effect = [[mock_lang1], [mock_lang2]]
        
        # Create test document with multiple pages
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        
        # Page 1 - English
        page1 = PageStructure(page_number=1, dimensions=dims)
        text_region1 = TextRegion(
            bounding_box=BoundingBox(x=0, y=0, width=100, height=20),
            text_content="This is English text."
        )
        page1.text_regions.append(text_region1)
        doc.add_page(page1)
        
        # Page 2 - French
        page2 = PageStructure(page_number=2, dimensions=dims)
        text_region2 = TextRegion(
            bounding_box=BoundingBox(x=0, y=0, width=100, height=20),
            text_content="Ceci est du texte français."
        )
        page2.text_regions.append(text_region2)
        doc.add_page(page2)
        
        page_detections = service._detect_by_pages(doc)
        
        assert len(page_detections) == 2
        assert page_detections[0].detected_language == 'en'
        assert page_detections[1].detected_language == 'fr'
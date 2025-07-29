"""Integration tests for language detection service with document parsers."""

import pytest
from unittest.mock import Mock, patch

from src.translation.language_detection import LanguageDetectionService
from src.parsers import get_parser_factory
from src.models.document import DocumentStructure, PageStructure, TextRegion, Dimensions, BoundingBox
from src.models.translation import LanguageDetection


class TestLanguageDetectionIntegration:
    """Integration tests for language detection with document processing."""
    
    def test_language_detection_service_creation(self):
        """Test creating language detection service."""
        service = LanguageDetectionService()
        
        assert isinstance(service, LanguageDetectionService)
        assert hasattr(service, 'detect_language')
        assert hasattr(service, 'detect_document_language')
        assert hasattr(service, 'detect_text_regions_languages')
    
    @patch('src.translation.language_detection.detect_langs')
    def test_detect_language_with_parsed_document(self, mock_detect_langs):
        """Test language detection with a parsed document structure."""
        service = LanguageDetectionService()
        
        # Mock language detection
        mock_lang = Mock()
        mock_lang.lang = 'en'
        mock_lang.prob = 0.9
        mock_detect_langs.return_value = [mock_lang]
        
        # Create document structure (as would come from parser)
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        
        # Add multiple text regions
        regions = [
            "This document contains English text that should be detected.",
            "The language detection service analyzes the entire document.",
            "Multiple text regions provide more context for accurate detection."
        ]
        
        for i, text in enumerate(regions):
            region = TextRegion(
                bounding_box=BoundingBox(x=50, y=50 + i * 30, width=500, height=25),
                text_content=text
            )
            page.text_regions.append(region)
        
        doc.add_page(page)
        
        # Test document-level detection
        detection = service.detect_document_language(doc)
        
        assert detection.detected_language == 'en'
        assert detection.confidence == 0.9
        assert service.is_detection_reliable(detection)
    
    @patch('src.translation.language_detection.detect_langs')
    def test_multilingual_document_detection(self, mock_detect_langs):
        """Test detection with multilingual document."""
        service = LanguageDetectionService()
        
        # Mock different detections for different calls
        mock_lang_en = Mock()
        mock_lang_en.lang = 'en'
        mock_lang_en.prob = 0.85
        
        mock_lang_fr = Mock()
        mock_lang_fr.lang = 'fr'
        mock_lang_fr.prob = 0.8
        
        # First call (document level) returns mixed result
        # Subsequent calls (page level) return specific languages
        mock_detect_langs.side_effect = [
            [mock_lang_en, mock_lang_fr],  # Document level - mixed
            [mock_lang_en],  # Page 1 - English
            [mock_lang_fr],  # Page 2 - French
        ]
        
        # Create multilingual document
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        
        # English page
        page1 = PageStructure(page_number=1, dimensions=dims)
        region1 = TextRegion(
            bounding_box=BoundingBox(x=50, y=50, width=500, height=25),
            text_content="This is English content in the first page."
        )
        page1.text_regions.append(region1)
        doc.add_page(page1)
        
        # French page
        page2 = PageStructure(page_number=2, dimensions=dims)
        region2 = TextRegion(
            bounding_box=BoundingBox(x=50, y=50, width=500, height=25),
            text_content="Ceci est le contenu français de la deuxième page."
        )
        page2.text_regions.append(region2)
        doc.add_page(page2)
        
        # Test document detection (should trigger page-by-page analysis)
        detection = service.detect_document_language(doc)
        
        # Should detect primary language based on page majority
        assert detection.detected_language in ['en', 'fr']
        assert detection.detection_method == 'page_majority_vote'
    
    def test_language_detection_with_parser_factory(self):
        """Test language detection integration with parser factory."""
        service = LanguageDetectionService()
        factory = get_parser_factory()
        
        # Verify that both services can work together
        assert "pdf" in factory.get_supported_formats()
        assert "docx" in factory.get_supported_formats()
        assert "epub" in factory.get_supported_formats()
        
        supported_langs = service.get_supported_languages()
        assert "en" in supported_langs
        assert "fr" in supported_langs
        assert "zh" in supported_langs
    
    @patch('src.translation.language_detection.detect_langs')
    def test_region_level_language_detection(self, mock_detect_langs):
        """Test language detection at text region level."""
        service = LanguageDetectionService()
        
        # Mock different languages for different regions
        mock_lang_en = Mock()
        mock_lang_en.lang = 'en'
        mock_lang_en.prob = 0.9
        
        mock_lang_fr = Mock()
        mock_lang_fr.lang = 'fr'
        mock_lang_fr.prob = 0.85
        
        mock_lang_es = Mock()
        mock_lang_es.lang = 'es'
        mock_lang_es.prob = 0.8
        
        mock_detect_langs.side_effect = [
            [mock_lang_en],
            [mock_lang_fr],
            [mock_lang_es]
        ]
        
        # Create text regions in different languages
        regions = [
            TextRegion(
                bounding_box=BoundingBox(x=50, y=50, width=500, height=25),
                text_content="This is English text in the first region."
            ),
            TextRegion(
                bounding_box=BoundingBox(x=50, y=80, width=500, height=25),
                text_content="Ceci est du texte français dans la deuxième région."
            ),
            TextRegion(
                bounding_box=BoundingBox(x=50, y=110, width=500, height=25),
                text_content="Este es texto en español en la tercera región."
            )
        ]
        
        # Detect languages for all regions
        detections = service.detect_text_regions_languages(regions)
        
        assert len(detections) == 3
        assert detections[0].detected_language == 'en'
        assert detections[1].detected_language == 'fr'
        assert detections[2].detected_language == 'es'
        
        # All should be reliable
        for detection in detections:
            assert service.is_detection_reliable(detection)
    
    def test_language_validation_with_supported_formats(self):
        """Test language validation with supported document formats."""
        service = LanguageDetectionService()
        factory = get_parser_factory()
        
        # Test that all supported languages are valid
        supported_languages = service.get_supported_languages()
        for lang in supported_languages:
            assert service.validate_language_code(lang)
        
        # Test that parser factory and language service are compatible
        parser_formats = factory.get_supported_formats()
        assert len(parser_formats) >= 3  # PDF, DOCX, EPUB
        
        # Language service should work with content from any parser
        for format_type in parser_formats:
            parser = factory.create_parser(format_type)
            assert parser is not None
    
    @patch('src.translation.language_detection.detect_langs')
    def test_low_confidence_detection_handling(self, mock_detect_langs):
        """Test handling of low confidence detections."""
        service = LanguageDetectionService()
        
        # Mock low confidence detection
        mock_lang = Mock()
        mock_lang.lang = 'en'
        mock_lang.prob = 0.4  # Below threshold
        mock_detect_langs.return_value = [mock_lang]
        
        # Create document with ambiguous text
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        
        region = TextRegion(
            bounding_box=BoundingBox(x=50, y=50, width=500, height=25),
            text_content="Short ambiguous text."
        )
        page.text_regions.append(region)
        doc.add_page(page)
        
        detection = service.detect_document_language(doc)
        
        # Should detect but be marked as unreliable
        assert detection.detected_language == 'en'
        assert detection.confidence == 0.4
        assert not service.is_detection_reliable(detection)
        
        # Should provide suggestions
        suggestions = service.get_language_suggestions(detection)
        assert len(suggestions) > 0
        assert 'en' in suggestions  # Should include common languages
    
    def test_detection_statistics_integration(self):
        """Test detection statistics with realistic data."""
        service = LanguageDetectionService()
        
        # Create realistic detection results
        detections = [
            LanguageDetection('en', 0.95, [('fr', 0.03)], 'langdetect'),
            LanguageDetection('en', 0.87, [('de', 0.08)], 'langdetect'),
            LanguageDetection('fr', 0.92, [('en', 0.05)], 'langdetect'),
            LanguageDetection('zh', 0.88, [('ja', 0.07)], 'langdetect'),
            LanguageDetection('es', 0.65, [('pt', 0.25)], 'langdetect'),  # Unreliable
            LanguageDetection('unknown', 0.0, [], 'insufficient_text'),
        ]
        
        stats = service.get_detection_statistics(detections)
        
        # Verify statistics calculation
        assert stats['total_detections'] == 6
        assert stats['reliable_detections'] == 4  # en, en, fr, zh are reliable
        assert stats['reliability_rate'] == 4/6
        
        # Check language distribution
        assert stats['language_distribution']['en'] == 2
        assert stats['language_distribution']['fr'] == 1
        assert stats['language_distribution']['zh'] == 1
        assert stats['language_distribution']['es'] == 1
        assert stats['language_distribution']['unknown'] == 1
        
        # Verify average confidence calculation
        expected_avg = (0.95 + 0.87 + 0.92 + 0.88 + 0.65 + 0.0) / 6
        assert abs(stats['average_confidence'] - expected_avg) < 0.001
    
    def test_language_name_mapping(self):
        """Test language name mapping functionality."""
        service = LanguageDetectionService()
        
        # Test all supported languages have names
        supported_languages = service.get_supported_languages()
        language_names = service.get_supported_language_names()
        
        for lang_code in supported_languages:
            assert lang_code in language_names
            name = service.get_language_name(lang_code)
            assert name != lang_code  # Should be human-readable
            assert len(name) > 2  # Should be actual name, not just code
        
        # Test specific mappings
        assert service.get_language_name('en') == 'English'
        assert service.get_language_name('fr') == 'French'
        assert service.get_language_name('zh') == 'Simplified Chinese'
        assert service.get_language_name('ja') == 'Japanese'
    
    def test_text_cleaning_integration(self):
        """Test text cleaning with realistic document content."""
        service = LanguageDetectionService()
        
        # Test with content that might come from parsed documents
        messy_texts = [
            "Visit our website at https://example.com for more information.",
            "Contact us at info@company.com or call +1-555-0123.",
            "Price: $123.45   Special offer!!!   Limited time only.",
            "   Multiple    spaces    and    formatting   issues   ",
            "Mixed content: English text with números 123 and símbolos @#$%"
        ]
        
        for text in messy_texts:
            cleaned = service._clean_text_for_detection(text)
            
            # Should remove URLs, emails, excessive punctuation
            assert "https://" not in cleaned
            assert "@" not in cleaned
            assert "$" not in cleaned
            assert "123" not in cleaned
            
            # Should preserve meaningful text
            assert len(cleaned.strip()) > 0
            assert not re.search(r'\s{2,}', cleaned)  # No multiple spaces
    
    @patch('src.translation.language_detection.detect_langs')
    def test_error_recovery_integration(self, mock_detect_langs):
        """Test error recovery in integrated scenarios."""
        service = LanguageDetectionService()
        
        # Test with detection exception
        from langdetect.lang_detect_exception import LangDetectException
        mock_detect_langs.side_effect = LangDetectException("Test error", "ERROR")
        
        # Create document that would normally be detectable
        doc = DocumentStructure(format="pdf")
        dims = Dimensions(width=612, height=792)
        page = PageStructure(page_number=1, dimensions=dims)
        
        region = TextRegion(
            bounding_box=BoundingBox(x=50, y=50, width=500, height=25),
            text_content="This should be detectable English text but will cause an error."
        )
        page.text_regions.append(region)
        doc.add_page(page)
        
        detection = service.detect_document_language(doc)
        
        # Should handle error gracefully
        assert detection.detected_language == "unknown"
        assert detection.confidence == 0.0
        assert detection.detection_method == "detection_error"
        
        # Should still provide suggestions
        suggestions = service.get_language_suggestions(detection)
        assert len(suggestions) > 0
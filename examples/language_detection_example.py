"""Example usage of language detection service."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from translation.language_detection import LanguageDetectionService
from models.document import DocumentStructure, PageStructure, TextRegion, Dimensions, BoundingBox


def demonstrate_language_detection():
    """Demonstrate language detection functionality."""
    print("Language Detection Service Example")
    print("=" * 50)
    
    # Create language detection service
    service = LanguageDetectionService()
    
    print(f"Supported languages: {service.get_supported_languages()}")
    print(f"Confidence threshold: {service.confidence_threshold}")
    print(f"Minimum text length: {service.min_text_length}")
    
    # Test text samples in different languages
    test_texts = {
        "English": "This is a sample text in English. It contains multiple sentences to provide enough content for reliable language detection.",
        "French": "Ceci est un exemple de texte en français. Il contient plusieurs phrases pour fournir suffisamment de contenu pour une détection fiable de la langue.",
        "Spanish": "Este es un texto de ejemplo en español. Contiene varias oraciones para proporcionar suficiente contenido para una detección confiable del idioma.",
        "German": "Dies ist ein Beispieltext auf Deutsch. Er enthält mehrere Sätze, um genügend Inhalt für eine zuverlässige Spracherkennung zu bieten.",
        "Chinese": "这是一个中文示例文本。它包含多个句子，为可靠的语言检测提供足够的内容。",
        "Japanese": "これは日本語のサンプルテキストです。信頼性の高い言語検出のために十分なコンテンツを提供するために、複数の文が含まれています。",
        "Mixed": "This text contains English and français mixed together. Es una mezcla de idiomas diferentes."
    }
    
    print("\nLanguage Detection Results:")
    print("-" * 30)
    
    for language, text in test_texts.items():
        try:
            detection = service.detect_language(text)
            reliability = "✓ Reliable" if service.is_detection_reliable(detection) else "⚠ Unreliable"
            
            print(f"\n{language} Text:")
            print(f"  Detected: {detection.detected_language} ({service.get_language_name(detection.detected_language)})")
            print(f"  Confidence: {detection.confidence:.3f}")
            print(f"  Reliability: {reliability}")
            print(f"  Method: {detection.detection_method}")
            
            if detection.alternative_languages:
                print("  Alternatives:")
                for alt_lang, alt_conf in detection.alternative_languages[:3]:
                    print(f"    {alt_lang} ({service.get_language_name(alt_lang)}): {alt_conf:.3f}")
            
            if not service.is_detection_reliable(detection):
                suggestions = service.get_language_suggestions(detection)
                print(f"  Suggestions: {suggestions}")
        
        except Exception as e:
            print(f"\n{language} Text: Error - {str(e)}")


def demonstrate_document_detection():
    """Demonstrate document-level language detection."""
    print("\n\nDocument Language Detection")
    print("=" * 35)
    
    service = LanguageDetectionService()
    
    # Create a test document with multiple text regions
    doc = DocumentStructure(format="pdf")
    dims = Dimensions(width=612, height=792)
    page = PageStructure(page_number=1, dimensions=dims)
    
    # Add text regions in English
    english_texts = [
        "Welcome to our comprehensive document translation service.",
        "We provide high-quality translation while preserving document layout.",
        "Our system supports multiple document formats including PDF, DOCX, and EPUB.",
        "Advanced language detection ensures accurate source language identification."
    ]
    
    for i, text in enumerate(english_texts):
        region = TextRegion(
            bounding_box=BoundingBox(x=50, y=50 + i * 30, width=500, height=25),
            text_content=text
        )
        page.text_regions.append(region)
    
    doc.add_page(page)
    
    # Detect document language
    detection = service.detect_document_language(doc)
    
    print(f"Document Language: {detection.detected_language} ({service.get_language_name(detection.detected_language)})")
    print(f"Confidence: {detection.confidence:.3f}")
    print(f"Method: {detection.detection_method}")
    print(f"Reliable: {'Yes' if service.is_detection_reliable(detection) else 'No'}")
    
    # Test individual text regions
    print("\nIndividual Text Region Detection:")
    region_detections = service.detect_text_regions_languages(page.text_regions)
    
    for i, (region, detection) in enumerate(zip(page.text_regions, region_detections)):
        print(f"  Region {i+1}: {detection.detected_language} (conf: {detection.confidence:.3f})")


def demonstrate_detection_statistics():
    """Demonstrate detection statistics."""
    print("\n\nDetection Statistics")
    print("=" * 25)
    
    service = LanguageDetectionService()
    
    # Create sample detections
    from models.translation import LanguageDetection
    
    sample_detections = [
        LanguageDetection('en', 0.95, [('fr', 0.03)], 'langdetect'),
        LanguageDetection('en', 0.87, [('de', 0.08)], 'langdetect'),
        LanguageDetection('fr', 0.92, [('en', 0.05)], 'langdetect'),
        LanguageDetection('es', 0.65, [('pt', 0.25)], 'langdetect'),  # Low confidence
        LanguageDetection('unknown', 0.0, [], 'insufficient_text'),
        LanguageDetection('de', 0.78, [('en', 0.15)], 'langdetect'),
    ]
    
    stats = service.get_detection_statistics(sample_detections)
    
    print(f"Total detections: {stats['total_detections']}")
    print(f"Reliable detections: {stats['reliable_detections']}")
    print(f"Reliability rate: {stats['reliability_rate']:.1%}")
    print(f"Average confidence: {stats['average_confidence']:.3f}")
    
    print("\nLanguage distribution:")
    for lang, count in stats['language_distribution'].items():
        lang_name = service.get_language_name(lang)
        print(f"  {lang} ({lang_name}): {count}")
    
    print("\nDetection methods:")
    for method, count in stats['detection_methods'].items():
        print(f"  {method}: {count}")


def show_supported_languages():
    """Show all supported languages."""
    print("\n\nSupported Languages")
    print("=" * 25)
    
    service = LanguageDetectionService()
    language_names = service.get_supported_language_names()
    
    print("Code | Language Name")
    print("-----|-------------")
    for code, name in sorted(language_names.items()):
        print(f"{code:4} | {name}")


def demonstrate_edge_cases():
    """Demonstrate edge cases and error handling."""
    print("\n\nEdge Cases and Error Handling")
    print("=" * 35)
    
    service = LanguageDetectionService()
    
    edge_cases = {
        "Empty text": "",
        "Very short": "Hi",
        "Numbers only": "123 456 789",
        "Special chars": "!@#$%^&*()",
        "URLs and emails": "Visit https://example.com or email test@example.com",
        "Mixed content": "Price: $123.45 Contact: info@company.com Phone: +1-555-0123"
    }
    
    for case_name, text in edge_cases.items():
        detection = service.detect_language(text)
        print(f"\n{case_name}:")
        print(f"  Input: '{text}'")
        print(f"  Result: {detection.detected_language}")
        print(f"  Confidence: {detection.confidence:.3f}")
        print(f"  Method: {detection.detection_method}")


if __name__ == "__main__":
    demonstrate_language_detection()
    demonstrate_document_detection()
    demonstrate_detection_statistics()
    show_supported_languages()
    demonstrate_edge_cases()
    
    print("\n" + "=" * 50)
    print("Language Detection Service Features:")
    print("• Automatic language detection using langdetect")
    print("• Support for 10+ major languages")
    print("• Document-level and region-level detection")
    print("• Confidence scoring and reliability assessment")
    print("• Alternative language suggestions")
    print("• Robust error handling and edge case management")
    print("• Statistical analysis of detection results")
    print("• Text cleaning and preprocessing")
    print("• Language code mapping and validation")
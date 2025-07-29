"""Example usage of context-aware translation service."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from translation.translation_service import ContextAwareTranslationService
from models.layout import TextRegion
from models.document import BoundingBox, TextFormatting
from models.translation import TranslationContext, LanguagePair


def demonstrate_translation_service():
    """Demonstrate translation service functionality."""
    print("Context-Aware Translation Service Example")
    print("=" * 50)
    
    # Create translation service
    service = ContextAwareTranslationService(device="cpu")
    
    print(f"Device: {service.device}")
    print(f"Max length: {service.max_length}")
    print(f"Batch size: {service.batch_size}")
    print(f"Context window: {service.context_window}")
    
    # Show supported languages
    languages = service.get_supported_languages()
    print(f"\nSupported languages: {languages}")
    
    # Show supported language pairs
    pairs = service.get_supported_language_pairs()
    print(f"\nSupported language pairs: {len(pairs)} pairs")
    
    # Show some example pairs
    print("\nExample language pairs:")
    for pair in pairs[:10]:  # Show first 10
        quality_stars = "★" * int(pair.quality_rating * 5)
        print(f"  {pair.source_language} → {pair.target_language}: {quality_stars} ({pair.quality_rating:.2f})")


def demonstrate_language_pair_validation():
    """Demonstrate language pair validation."""
    print("\n\nLanguage Pair Validation")
    print("=" * 30)
    
    service = ContextAwareTranslationService()
    
    test_pairs = [
        ("en", "fr"),   # Valid
        ("fr", "en"),   # Valid
        ("en", "de"),   # Valid
        ("zh", "ja"),   # May not be valid (no direct pair)
        ("en", "en"),   # Invalid (same language)
        ("xyz", "abc"), # Invalid (unsupported)
    ]
    
    for source, target in test_pairs:
        is_valid = service.validate_language_pair(source, target)
        status = "✓ Valid" if is_valid else "✗ Invalid"
        print(f"  {source} → {target}: {status}")


def demonstrate_context_building():
    """Demonstrate translation context building."""
    print("\n\nTranslation Context Building")
    print("=" * 35)
    
    service = ContextAwareTranslationService()
    
    # Create sample text regions
    regions = [
        TextRegion(text_content="Welcome to our document translation service."),
        TextRegion(text_content="We provide high-quality translations."),
        TextRegion(text_content="Our system preserves document formatting."),  # Current
        TextRegion(text_content="Advanced algorithms ensure accuracy."),
        TextRegion(text_content="Try our service today for best results.")
    ]
    
    # Build context for the middle region (index 2)
    current_region = regions[2]
    context = service._build_translation_context(current_region, regions, 2)
    
    print(f"Current text: '{current_region.text_content}'")
    print(f"Preceding context: '{context.preceding_text}'")
    print(f"Following context: '{context.following_text}'")
    print(f"Element type: {context.element_type}")


def demonstrate_formatting_preservation():
    """Demonstrate formatting preservation."""
    print("\n\nFormatting Preservation")
    print("=" * 25)
    
    service = ContextAwareTranslationService()
    
    # Create text region with formatting
    formatting = TextFormatting(
        font_family="Arial",
        font_size=14.0,
        is_bold=True,
        is_italic=True,
        color="#FF0000",
        alignment="center"
    )
    
    region = TextRegion(
        text_content="Important formatted text",
        formatting=formatting
    )
    
    # Demonstrate formatting extraction
    tags = service._extract_formatting_tags(region)
    print("Extracted formatting tags:")
    for tag in tags:
        print(f"  {tag}")
    
    # Demonstrate style mapping
    style_map = service._create_style_mapping(formatting)
    print("\nStyle mapping:")
    for prop, value in style_map.items():
        print(f"  {prop}: {value}")
    
    # Demonstrate formatting preservation
    formatted_text = service.preserve_formatting(region, "Texte formaté important")
    print(f"\nPreserved formatting:")
    print(f"  Content: {formatted_text.content}")
    print(f"  Tags: {len(formatted_text.formatting_tags)} tags")
    print(f"  Styles: {len(formatted_text.style_mapping)} properties")


def demonstrate_translation_batch():
    """Demonstrate translation batch creation."""
    print("\n\nTranslation Batch Creation")
    print("=" * 30)
    
    service = ContextAwareTranslationService()
    
    # Create sample regions
    regions = [
        TextRegion(text_content="First sentence to translate."),
        TextRegion(text_content="Second sentence for translation."),
        TextRegion(text_content="Third sentence in the batch.")
    ]
    
    # Create language pair
    language_pair = LanguagePair(
        source_language="en",
        target_language="fr",
        is_supported=True,
        quality_rating=0.9
    )
    
    # Create context
    context = TranslationContext(
        document_title="Sample Document",
        element_type="paragraph"
    )
    
    # Create batch
    batch = service.create_translation_batch(regions, language_pair, context)
    
    print(f"Batch ID: {batch.id}")
    print(f"Number of regions: {len(batch.regions)}")
    print(f"Language pair: {batch.language_pair}")
    print(f"Total text length: {batch.get_total_text_length()} characters")
    print(f"Combined text: '{batch.get_combined_text()[:100]}...'")
    print(f"Created at: {batch.created_at}")


def demonstrate_translation_progress():
    """Demonstrate translation progress tracking."""
    print("\n\nTranslation Progress Tracking")
    print("=" * 35)
    
    service = ContextAwareTranslationService()
    
    # Simulate progress at different stages
    stages = [
        (100, 0),   # Starting
        (100, 25),  # 25% complete
        (100, 50),  # 50% complete
        (100, 75),  # 75% complete
        (100, 100), # Complete
    ]
    
    for total, completed in stages:
        progress = service.get_translation_progress(total, completed)
        
        print(f"Progress: {progress.completion_percentage:5.1f}% "
              f"({progress.completed_regions}/{progress.total_regions})")
        print(f"  Success rate: {progress.success_rate:5.1f}%")
        print(f"  Operation: {progress.current_operation}")


def show_translation_models():
    """Show available translation models."""
    print("\n\nAvailable Translation Models")
    print("=" * 35)
    
    service = ContextAwareTranslationService()
    
    print("Supported model pairs:")
    for pair_key, model_info in service._supported_pairs.items():
        source, target = pair_key.split('-')
        model_name = model_info['model']
        quality = model_info['quality']
        
        print(f"  {source} → {target}: {model_name} (quality: {quality:.2f})")


def demonstrate_error_handling():
    """Demonstrate error handling scenarios."""
    print("\n\nError Handling Scenarios")
    print("=" * 30)
    
    service = ContextAwareTranslationService()
    
    # Test unsupported language pair
    try:
        service.validate_language_pair("xyz", "abc")
        print("✗ Should have failed for unsupported pair")
    except:
        print("✓ Correctly handled unsupported language pair")
    
    # Test invalid pipeline request
    try:
        service._get_translation_pipeline("invalid", "pair")
        print("✗ Should have failed for invalid pipeline")
    except ValueError as e:
        print(f"✓ Correctly handled invalid pipeline: {str(e)[:50]}...")
    
    # Test edge cases in context building
    empty_regions = []
    single_region = [TextRegion(text_content="Single region")]
    
    # Context for empty list (should handle gracefully)
    try:
        context = service._build_translation_context(single_region[0], empty_regions, 0)
        print("✓ Handled empty regions list")
    except:
        print("✗ Failed to handle empty regions list")


def show_service_capabilities():
    """Show service capabilities and features."""
    print("\n\nService Capabilities")
    print("=" * 25)
    
    capabilities = [
        "✓ Context-aware neural translation",
        "✓ Batch processing for efficiency",
        "✓ Formatting preservation",
        "✓ Multiple language pair support",
        "✓ Quality scoring and confidence",
        "✓ Progress tracking",
        "✓ Error handling and fallbacks",
        "✓ Model caching and optimization",
        "✓ GPU/CPU device selection",
        "✓ Memory management and cleanup"
    ]
    
    for capability in capabilities:
        print(f"  {capability}")


if __name__ == "__main__":
    demonstrate_translation_service()
    demonstrate_language_pair_validation()
    demonstrate_context_building()
    demonstrate_formatting_preservation()
    demonstrate_translation_batch()
    demonstrate_translation_progress()
    show_translation_models()
    demonstrate_error_handling()
    show_service_capabilities()
    
    print("\n" + "=" * 50)
    print("Context-Aware Translation Service Features:")
    print("• Neural machine translation with Transformers")
    print("• Context-aware translation using surrounding text")
    print("• Formatting preservation and style mapping")
    print("• Batch processing for improved efficiency")
    print("• Multiple language pair support (20+ pairs)")
    print("• Quality scoring and confidence assessment")
    print("• Progress tracking for long translations")
    print("• Robust error handling and fallback strategies")
    print("• Model caching and memory management")
    print("• Integration with language detection service")
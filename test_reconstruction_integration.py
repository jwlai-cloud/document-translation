#!/usr/bin/env python3
"""Integration test for layout reconstruction engine."""

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, Dimensions, TextFormatting, DocumentMetadata
)
from src.layout.reconstruction_engine import DefaultLayoutReconstructionEngine

def test_reconstruction_integration():
    """Test complete reconstruction workflow."""
    
    print("🧪 Testing Layout Reconstruction Integration...")
    
    # Create reconstruction engine
    engine = DefaultLayoutReconstructionEngine()
    
    # Create test document with multiple regions
    region1 = TextRegion(
        id="title",
        bounding_box=BoundingBox(50, 50, 300, 40),
        text_content="Document Title",
        formatting=TextFormatting(font_size=18.0, is_bold=True, alignment="center"),
        reading_order=0
    )
    
    region2 = TextRegion(
        id="paragraph1",
        bounding_box=BoundingBox(50, 120, 300, 60),
        text_content="This is the first paragraph of the document with some content.",
        formatting=TextFormatting(font_size=12.0, alignment="justify"),
        reading_order=1
    )
    
    region3 = TextRegion(
        id="paragraph2",
        bounding_box=BoundingBox(50, 200, 300, 80),
        text_content="This is a longer second paragraph that contains more text and might require adjustments when translated to other languages.",
        formatting=TextFormatting(font_size=12.0, alignment="justify"),
        reading_order=2
    )
    
    # Add a visual element
    image = VisualElement(
        id="image1",
        element_type="image",
        bounding_box=BoundingBox(50, 300, 200, 150),
        metadata={"description": "Test image"}
    )
    
    page = PageStructure(
        page_number=1,
        dimensions=Dimensions(width=400, height=600),
        text_regions=[region1, region2, region3],
        visual_elements=[image]
    )
    
    # Test different document formats
    formats_to_test = ["pdf", "docx", "epub"]
    
    for format_type in formats_to_test:
        print(f"\n✓ Testing {format_type.upper()} reconstruction...")
        
        document = DocumentStructure(
            format=format_type,
            pages=[page],
            metadata=DocumentMetadata(title=f"Test {format_type.upper()} Document")
        )
        
        # Prepare translations (simulate French translations)
        translated_regions = {
            "1": {
                "title": "Titre du Document",
                "paragraph1": "Ceci est le premier paragraphe du document avec du contenu.",
                "paragraph2": "Ceci est un deuxième paragraphe plus long qui contient plus de texte et pourrait nécessiter des ajustements lorsqu'il est traduit dans d'autres langues."
            }
        }
        
        # Test text fitting first
        print(f"  - Testing text fitting for {format_type}...")
        for region_id, translated_text in translated_regions["1"].items():
            original_region = next(r for r in page.text_regions if r.id == region_id)
            adjusted = engine.fit_translated_text(original_region, translated_text)
            
            print(f"    {region_id}: fit quality = {adjusted.fit_quality:.2f}, adjustments = {len(adjusted.adjustments)}")
        
        # Test full reconstruction
        print(f"  - Testing full reconstruction for {format_type}...")
        try:
            result = engine.reconstruct_document(document, translated_regions)
            
            print(f"    ✓ Reconstruction successful: {len(result)} bytes")
            
            # Verify content is present
            content = result.decode('utf-8', errors='ignore')
            
            # Check for translated content
            translations_found = 0
            for translated_text in translated_regions["1"].values():
                if translated_text in content:
                    translations_found += 1
            
            print(f"    ✓ Found {translations_found}/{len(translated_regions['1'])} translations in output")
            
            # Format-specific checks
            if format_type == "pdf":
                assert "%PDF" in content, "PDF header not found"
                print("    ✓ PDF format validated")
            elif format_type == "docx":
                assert "w:document" in content, "DOCX structure not found"
                print("    ✓ DOCX format validated")
            elif format_type == "epub":
                assert "<!DOCTYPE html>" in content, "HTML structure not found"
                print("    ✓ EPUB format validated")
            
        except Exception as e:
            print(f"    ❌ Reconstruction failed: {e}")
            raise
    
    print("\n🎉 Layout reconstruction integration test completed successfully!")
    return True

def test_conflict_resolution():
    """Test conflict detection and resolution."""
    
    print("\n🧪 Testing Conflict Resolution...")
    
    engine = DefaultLayoutReconstructionEngine()
    
    # Create overlapping regions after translation expansion
    region1 = TextRegion(
        id="overlap1",
        bounding_box=BoundingBox(10, 10, 200, 40),
        text_content="Short text",
        formatting=TextFormatting(font_size=12.0)
    )
    
    region2 = TextRegion(
        id="overlap2",
        bounding_box=BoundingBox(10, 45, 200, 40),  # Close to region1
        text_content="Another short text",
        formatting=TextFormatting(font_size=12.0)
    )
    
    # Simulate translation that causes expansion and overlap
    long_translation1 = "This is a much longer translated text that will expand significantly"
    long_translation2 = "This is another very long translated text that will also expand and potentially overlap"
    
    adjusted1 = engine.fit_translated_text(region1, long_translation1)
    adjusted2 = engine.fit_translated_text(region2, long_translation2)
    
    print(f"✓ Region 1 adjustments: {len(adjusted1.adjustments)}, fit quality: {adjusted1.fit_quality:.2f}")
    print(f"✓ Region 2 adjustments: {len(adjusted2.adjustments)}, fit quality: {adjusted2.fit_quality:.2f}")
    
    # Test conflict detection
    adjusted_regions = [adjusted1, adjusted2]
    conflicts = engine.layout_adjustment_engine.detect_layout_conflicts(adjusted_regions)
    
    print(f"✓ Detected conflicts: {len(conflicts)}")
    for i, conflict in enumerate(conflicts):
        print(f"  {i+1}. {conflict.conflict_type} (severity: {conflict.severity:.2f})")
    
    # Test conflict resolution
    if conflicts:
        resolutions = engine.layout_adjustment_engine.resolve_conflicts(conflicts, adjusted_regions)
        print(f"✓ Generated resolutions: {len(resolutions)}")
        
        for i, resolution in enumerate(resolutions):
            print(f"  {i+1}. {resolution.resolution_type} (success probability: {resolution.success_probability:.2f})")
    
    print("✓ Conflict resolution test completed!")

def test_extreme_cases():
    """Test extreme reconstruction cases."""
    
    print("\n🧪 Testing Extreme Cases...")
    
    engine = DefaultLayoutReconstructionEngine()
    
    # Test with very small region and very long text
    tiny_region = TextRegion(
        id="tiny",
        bounding_box=BoundingBox(0, 0, 50, 20),
        text_content="Hi",
        formatting=TextFormatting(font_size=8.0)
    )
    
    very_long_text = "This is an extremely long text that definitely will not fit in the tiny region and will require significant adjustments including truncation " * 3
    
    adjusted = engine.fit_translated_text(tiny_region, very_long_text)
    print(f"✓ Tiny region with long text: fit quality = {adjusted.fit_quality:.2f}")
    print(f"  - Requires truncation: {any('truncation' in adj.reason.lower() for adj in adjusted.adjustments)}")
    print(f"  - Text length: {len(adjusted.adjusted_text)} chars (original: {len(very_long_text)})")
    
    # Test with empty document
    empty_page = PageStructure(
        page_number=1,
        dimensions=Dimensions(width=400, height=600),
        text_regions=[],
        visual_elements=[]
    )
    
    empty_document = DocumentStructure(
        format="pdf",
        pages=[empty_page],
        metadata=DocumentMetadata(title="Empty Document")
    )
    
    result = engine.reconstruct_document(empty_document, {})
    print(f"✓ Empty document reconstruction: {len(result)} bytes")
    
    print("✓ Extreme cases handled successfully!")

if __name__ == "__main__":
    try:
        test_reconstruction_integration()
        test_conflict_resolution()
        test_extreme_cases()
        print("\n✅ All reconstruction integration tests passed!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise
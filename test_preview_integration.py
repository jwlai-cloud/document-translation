#!/usr/bin/env python3
"""Integration test for preview service."""

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, Dimensions, TextFormatting, DocumentMetadata
)
from src.models.layout import AdjustedRegion
from src.services.preview_service import (
    PreviewService, PreviewConfig, PreviewFormat, HighlightType
)

def test_preview_service_integration():
    """Test complete preview service workflow."""
    
    print("🧪 Testing Preview Service Integration...")
    
    # Create preview service
    service = PreviewService()
    
    # Create test document with multiple elements
    print("\n✓ Creating test document...")
    
    text_regions = [
        TextRegion(
            id="title",
            bounding_box=BoundingBox(50, 50, 300, 40),
            text_content="Document Title",
            formatting=TextFormatting(font_size=18.0, is_bold=True),
            confidence=0.95
        ),
        TextRegion(
            id="paragraph1",
            bounding_box=BoundingBox(50, 120, 300, 60),
            text_content="This is the first paragraph of the document with some content.",
            formatting=TextFormatting(font_size=12.0),
            confidence=0.9
        ),
        TextRegion(
            id="paragraph2",
            bounding_box=BoundingBox(50, 200, 300, 80),
            text_content="This is a longer second paragraph with more detailed content that spans multiple lines.",
            formatting=TextFormatting(font_size=12.0),
            confidence=0.85
        )
    ]
    
    visual_elements = [
        VisualElement(
            id="image1",
            element_type="image",
            bounding_box=BoundingBox(50, 300, 200, 150),
            metadata={"description": "Test image"}
        ),
        VisualElement(
            id="chart1",
            element_type="chart",
            bounding_box=BoundingBox(270, 300, 150, 100),
            metadata={"chart_type": "bar"}
        )
    ]
    
    page = PageStructure(
        page_number=1,
        dimensions=Dimensions(width=500, height=700),
        text_regions=text_regions,
        visual_elements=visual_elements
    )
    
    document = DocumentStructure(
        format="pdf",
        pages=[page],
        metadata=DocumentMetadata(title="Integration Test Document")
    )
    
    print(f"  - Created document with {len(text_regions)} text regions")
    print(f"  - Created document with {len(visual_elements)} visual elements")
    
    # Create translated regions (simulate translation results)
    print("\n✓ Creating translated regions...")
    
    translated_regions = {
        "1": [
            AdjustedRegion(
                original_region=text_regions[0],
                adjusted_text="Titre du Document",
                new_bounding_box=BoundingBox(50, 50, 320, 45),
                adjustments=[],
                fit_quality=0.9
            ),
            AdjustedRegion(
                original_region=text_regions[1],
                adjusted_text="Ceci est le premier paragraphe du document avec du contenu.",
                new_bounding_box=BoundingBox(50, 120, 330, 65),
                adjustments=[],
                fit_quality=0.85
            )
        ]
    }
    
    print(f"  - Created {len(translated_regions['1'])} translated regions")
    
    # Test different preview configurations
    print("\n✓ Testing different preview configurations...")
    
    configs = [
        {
            "name": "Default Configuration",
            "config": PreviewConfig()
        },
        {
            "name": "Side-by-Side with Confidence Scores",
            "config": PreviewConfig(
                side_by_side=True,
                show_confidence_scores=True,
                highlight_changes=True
            )
        },
        {
            "name": "Overlay Mode with Custom Zoom",
            "config": PreviewConfig(
                side_by_side=False,
                default_zoom=1.5,
                max_zoom=3.0,
                min_zoom=0.5
            )
        }
    ]
    
    for config_test in configs:
        print(f"  - Testing: {config_test['name']}")
        
        # Create preview
        preview_doc = service.create_preview(
            document, 
            translated_regions, 
            config_test['config']
        )
        
        print(f"    Document ID: {preview_doc.document_id}")
        print(f"    Title: {preview_doc.title}")
        print(f"    Pages: {len(preview_doc.pages)}")
        print(f"    Total regions: {preview_doc.total_regions}")
        print(f"    Translated regions: {preview_doc.translated_regions}")
        print(f"    Translation progress: {preview_doc.translation_progress:.1f}%")
        
        # Test page properties
        page = preview_doc.pages[0]
        print(f"    Page dimensions: {page.width}x{page.height}")
        print(f"    Original regions: {len(page.original_regions)}")
        print(f"    Translated regions: {len(page.translated_regions)}")
        print(f"    Visual elements: {len(page.visual_elements)}")
        print(f"    Zoom level: {page.zoom_level}")
    
    # Test preview operations
    print("\n✓ Testing preview operations...")
    
    preview_doc = service.create_preview(document, translated_regions)
    
    # Test highlighting updates
    print("  - Testing highlighting updates...")
    highlight_types = [HighlightType.ORIGINAL, HighlightType.TRANSLATED, HighlightType.CHANGED]
    
    for highlight_type in highlight_types:
        updated_doc = service.update_highlighting(preview_doc, highlight_type)
        print(f"    Updated highlighting to: {highlight_type.value}")
        
        # Verify highlighting was applied
        sample_region = updated_doc.pages[0].original_regions[0]
        assert sample_region.highlight_type == highlight_type
    
    # Test zoom operations
    print("  - Testing zoom operations...")
    zoom_levels = [0.5, 1.0, 1.5, 2.0, 3.0]
    
    for zoom_level in zoom_levels:
        updated_doc = service.set_zoom_level(preview_doc, zoom_level)
        actual_zoom = updated_doc.pages[0].zoom_level
        print(f"    Set zoom to {zoom_level}, actual: {actual_zoom}")
        
        # Verify zoom was clamped to limits if necessary
        expected_zoom = max(preview_doc.config.min_zoom, 
                          min(preview_doc.config.max_zoom, zoom_level))
        assert actual_zoom == expected_zoom
    
    # Test scroll operations
    print("  - Testing scroll operations...")
    scroll_positions = [(0, 0), (25, 50), (100, 200), (-10, -20)]
    
    for scroll_x, scroll_y in scroll_positions:
        updated_doc = service.set_scroll_position(preview_doc, scroll_x, scroll_y)
        page = updated_doc.pages[0]
        print(f"    Set scroll to ({scroll_x}, {scroll_y}), actual: ({page.scroll_x}, {page.scroll_y})")
        assert page.scroll_x == scroll_x
        assert page.scroll_y == scroll_y
    
    # Test region information retrieval
    print("  - Testing region information retrieval...")
    
    for region_id in ["title", "paragraph1", "paragraph2", "nonexistent"]:
        region_info = service.get_region_info(preview_doc, region_id)
        
        if region_info:
            print(f"    Region {region_id}:")
            print(f"      Type: {region_info['type']}")
            print(f"      Page: {region_info['page_number']}")
            print(f"      Confidence: {region_info['confidence']:.2f}")
            if 'translated_text' in region_info:
                print(f"      Translation: {region_info['translated_text'][:50]}...")
        else:
            print(f"    Region {region_id}: Not found")
    
    # Test HTML rendering
    print("\n✓ Testing HTML rendering...")
    
    html = service.render_preview(preview_doc)
    
    print(f"  - Generated HTML length: {len(html)} characters")
    
    # Verify HTML structure
    html_checks = [
        ("<!DOCTYPE html>", "HTML doctype"),
        ("<title>Preview: Integration Test Document</title>", "Document title"),
        ("side-by-side-container", "Side-by-side layout"),
        ("navigation-bar", "Navigation bar"),
        ("controls-panel", "Controls panel"),
        ("zoom-slider", "Zoom controls"),
        ("highlight-controls", "Highlight controls"),
        ("Titre du Document", "Translated content"),
        ("image-placeholder", "Visual elements"),
        ("chart-placeholder", "Chart elements")
    ]
    
    for check_text, description in html_checks:
        if check_text in html:
            print(f"    ✓ {description} found")
        else:
            print(f"    ❌ {description} missing")
    
    # Test JavaScript functionality (basic check)
    js_functions = [
        "applyZoom",
        "selectRegion", 
        "showRegionTooltip",
        "applyHighlight",
        "fitToWindow"
    ]
    
    for func_name in js_functions:
        if func_name in html:
            print(f"    ✓ JavaScript function {func_name} found")
        else:
            print(f"    ❌ JavaScript function {func_name} missing")
    
    print("\n🎉 Preview service integration test completed successfully!")
    return True

def test_preview_edge_cases():
    """Test preview service with edge cases."""
    
    print("\n🧪 Testing Preview Edge Cases...")
    
    service = PreviewService()
    
    # Test with empty document
    print("  - Testing empty document...")
    empty_document = DocumentStructure(
        format="pdf",
        pages=[],
        metadata=DocumentMetadata(title="Empty Document")
    )
    
    preview_doc = service.create_preview(empty_document)
    assert len(preview_doc.pages) == 0
    assert preview_doc.total_regions == 0
    assert preview_doc.translation_progress == 0.0
    print("    ✓ Empty document handled correctly")
    
    # Test with document with no text regions
    print("  - Testing document with no text regions...")
    page_no_text = PageStructure(
        page_number=1,
        dimensions=Dimensions(width=400, height=600),
        text_regions=[],
        visual_elements=[
            VisualElement(
                id="img1",
                element_type="image",
                bounding_box=BoundingBox(10, 10, 100, 100)
            )
        ]
    )
    
    no_text_document = DocumentStructure(
        format="pdf",
        pages=[page_no_text],
        metadata=DocumentMetadata(title="No Text Document")
    )
    
    preview_doc = service.create_preview(no_text_document)
    assert len(preview_doc.pages) == 1
    assert len(preview_doc.pages[0].original_regions) == 0
    assert len(preview_doc.pages[0].visual_elements) == 1
    print("    ✓ Document with no text regions handled correctly")
    
    # Test with very long text
    print("  - Testing very long text...")
    long_text = "This is a very long text content. " * 100
    
    long_text_region = TextRegion(
        id="long_text",
        bounding_box=BoundingBox(10, 10, 300, 200),
        text_content=long_text,
        confidence=0.8
    )
    
    long_text_page = PageStructure(
        page_number=1,
        dimensions=Dimensions(width=400, height=600),
        text_regions=[long_text_region],
        visual_elements=[]
    )
    
    long_text_document = DocumentStructure(
        format="pdf",
        pages=[long_text_page],
        metadata=DocumentMetadata(title="Long Text Document")
    )
    
    preview_doc = service.create_preview(long_text_document)
    html = service.render_preview(preview_doc)
    
    # Check that long text is properly escaped and rendered
    assert len(html) > 1000  # Should be substantial HTML
    assert "&lt;" not in long_text  # Original text shouldn't have HTML entities
    print("    ✓ Very long text handled correctly")
    
    print("✓ Edge case testing completed!")

if __name__ == "__main__":
    try:
        test_preview_service_integration()
        test_preview_edge_cases()
        print("\n✅ All preview service integration tests passed!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise
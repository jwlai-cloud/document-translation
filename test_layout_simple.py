#!/usr/bin/env python3
"""Simple test to verify layout analysis engine works."""

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, Dimensions, TextFormatting, DocumentMetadata
)
from src.layout.analysis_engine import DefaultLayoutAnalysisEngine

def test_basic_functionality():
    """Test basic layout analysis functionality."""
    
    # Create test data
    engine = DefaultLayoutAnalysisEngine()
    
    text_region = TextRegion(
        id="test1",
        bounding_box=BoundingBox(10, 10, 100, 20),
        text_content="Test text",
        formatting=TextFormatting(font_size=12.0),
        confidence=0.9
    )
    
    visual_element = VisualElement(
        id="img1",
        element_type="image",
        bounding_box=BoundingBox(10, 50, 200, 100)
    )
    
    page = PageStructure(
        page_number=1,
        dimensions=Dimensions(width=400, height=600),
        text_regions=[text_region],
        visual_elements=[visual_element]
    )
    
    document = DocumentStructure(
        format="pdf",
        pages=[page],
        metadata=DocumentMetadata(title="Test")
    )
    
    # Test the analysis
    try:
        analyses = engine.analyze_layout(document)
        print(f"✓ Analysis completed successfully")
        print(f"✓ Found {len(analyses)} page analyses")
        print(f"✓ Page 1 has {len(analyses[0].text_regions)} text regions")
        print(f"✓ Page 1 has {len(analyses[0].visual_elements)} visual elements")
        print(f"✓ Page 1 has {len(analyses[0].spatial_relationships)} spatial relationships")
        print(f"✓ Layout complexity: {analyses[0].layout_complexity:.2f}")
        return True
    except Exception as e:
        print(f"✗ Error during analysis: {e}")
        return False

if __name__ == "__main__":
    success = test_basic_functionality()
    if success:
        print("\n🎉 Layout analysis engine is working correctly!")
    else:
        print("\n❌ Layout analysis engine has issues")
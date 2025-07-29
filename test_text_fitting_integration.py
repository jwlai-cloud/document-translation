#!/usr/bin/env python3
"""Integration test for text fitting and layout adjustment."""

from src.models.document import TextRegion, BoundingBox, TextFormatting
from src.layout.text_fitting import TextFittingEngine, LayoutAdjustmentEngine

def test_text_fitting_integration():
    """Test complete text fitting workflow."""
    
    print("🧪 Testing Text Fitting Integration...")
    
    # Create text fitting engine
    fitting_engine = TextFittingEngine()
    adjustment_engine = LayoutAdjustmentEngine()
    
    # Create test regions
    region1 = TextRegion(
        id="test1",
        bounding_box=BoundingBox(10, 10, 150, 40),
        text_content="Hello world",
        formatting=TextFormatting(font_size=12.0),
        confidence=0.9
    )
    
    region2 = TextRegion(
        id="test2", 
        bounding_box=BoundingBox(10, 60, 150, 40),
        text_content="Second line",
        formatting=TextFormatting(font_size=12.0),
        confidence=0.85
    )
    
    # Test text fitting
    print("✓ Testing text fitting...")
    
    # Fit longer text that requires adjustment
    long_text1 = "This is a much longer text that will require some adjustments to fit properly"
    long_text2 = "Another long text that might cause layout conflicts when expanded"
    
    adjusted1 = fitting_engine.fit_text_to_region(region1, long_text1)
    adjusted2 = fitting_engine.fit_text_to_region(region2, long_text2)
    
    print(f"  - Region 1 fit quality: {adjusted1.fit_quality:.2f}")
    print(f"  - Region 1 adjustments: {len(adjusted1.adjustments)}")
    print(f"  - Region 2 fit quality: {adjusted2.fit_quality:.2f}")
    print(f"  - Region 2 adjustments: {len(adjusted2.adjustments)}")
    
    # Test conflict detection
    print("✓ Testing conflict detection...")
    
    adjusted_regions = [adjusted1, adjusted2]
    conflicts = adjustment_engine.detect_layout_conflicts(adjusted_regions)
    
    print(f"  - Detected conflicts: {len(conflicts)}")
    for i, conflict in enumerate(conflicts):
        print(f"    {i+1}. {conflict.conflict_type} (severity: {conflict.severity:.2f})")
    
    # Test conflict resolution
    if conflicts:
        print("✓ Testing conflict resolution...")
        resolutions = adjustment_engine.resolve_conflicts(conflicts, adjusted_regions)
        
        print(f"  - Generated resolutions: {len(resolutions)}")
        for i, resolution in enumerate(resolutions):
            print(f"    {i+1}. {resolution.resolution_type} (probability: {resolution.success_probability:.2f})")
            print(f"       Actions: {len(resolution.actions)}")
    
    print("\n🎉 Text fitting integration test completed successfully!")
    return True

def test_extreme_cases():
    """Test extreme text fitting cases."""
    
    print("\n🧪 Testing Extreme Cases...")
    
    fitting_engine = TextFittingEngine()
    
    # Very small region
    tiny_region = TextRegion(
        id="tiny",
        bounding_box=BoundingBox(0, 0, 20, 10),
        text_content="Hi",
        formatting=TextFormatting(font_size=8.0)
    )
    
    # Very long text
    very_long_text = "This is an extremely long text that definitely will not fit in a tiny region " * 5
    
    result = fitting_engine.fit_text_to_region(tiny_region, very_long_text)
    
    print(f"✓ Tiny region with long text:")
    print(f"  - Fit quality: {result.fit_quality:.2f}")
    print(f"  - Requires truncation: {result.requires_truncation}")
    print(f"  - Adjustments: {len(result.adjustments)}")
    
    # Empty text
    empty_result = fitting_engine.fit_text_to_region(tiny_region, "")
    print(f"✓ Empty text fit quality: {empty_result.fit_quality:.2f}")
    
    print("✓ Extreme cases handled successfully!")

if __name__ == "__main__":
    try:
        test_text_fitting_integration()
        test_extreme_cases()
        print("\n✅ All integration tests passed!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise
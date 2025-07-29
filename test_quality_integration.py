#!/usr/bin/env python3
"""Integration test for quality assessment service."""

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, BoundingBox, 
    TextFormatting, DocumentMetadata, Dimensions
)
from src.models.layout import (
    LayoutAnalysis, AdjustedRegion, LayoutAdjustment, 
    LayoutAdjustmentType, SpatialRelationship
)
from src.quality.assessment_service import QualityAssessmentService

def test_quality_assessment_integration():
    """Test complete quality assessment workflow."""
    
    print("🧪 Testing Quality Assessment Integration...")
    
    # Create quality assessment service
    service = QualityAssessmentService()
    
    # Test translation quality assessment
    print("\n✓ Testing Translation Quality Assessment...")
    
    test_cases = [
        {
            "name": "Good Translation",
            "original": "Hello world, this is a test document with multiple sentences.",
            "translated": "Bonjour le monde, ceci est un document de test avec plusieurs phrases.",
            "source_lang": "en",
            "target_lang": "fr"
        },
        {
            "name": "Poor Translation (Empty)",
            "original": "Hello world, this is a test.",
            "translated": "",
            "source_lang": "en", 
            "target_lang": "fr"
        },
        {
            "name": "Translation with Preserved Elements",
            "original": "Contact us at support@example.com or visit https://example.com on 2024-01-15.",
            "translated": "Contactez-nous à support@example.com ou visitez https://example.com le 15-01-2024.",
            "source_lang": "en",
            "target_lang": "fr"
        },
        {
            "name": "Translation with Length Issues",
            "original": "This is a comprehensive document with extensive content and detailed explanations.",
            "translated": "Document.",  # Very short translation
            "source_lang": "en",
            "target_lang": "fr"
        }
    ]
    
    for test_case in test_cases:
        print(f"  - Testing: {test_case['name']}")
        
        quality_score = service.assess_translation_quality(
            test_case["original"],
            test_case["translated"],
            test_case["source_lang"],
            test_case["target_lang"]
        )
        
        print(f"    Overall Score: {quality_score.overall_score:.2f} (Grade: {quality_score.grade})")
        print(f"    Translation Accuracy: {quality_score.metrics.translation_accuracy:.2f}")
        print(f"    Readability: {quality_score.metrics.readability:.2f}")
        print(f"    Issues Found: {len(quality_score.issues)}")
        print(f"    Critical Issues: {len(quality_score.critical_issues)}")
        print(f"    Needs Review: {quality_score.needs_review}")
        
        if quality_score.issues:
            print("    Top Issues:")
            for issue in quality_score.issues[:3]:  # Show first 3 issues
                print(f"      - {issue.severity.value}: {issue.description}")
    
    # Test layout preservation assessment
    print("\n✓ Testing Layout Preservation Assessment...")
    
    # Create test layout analysis
    original_regions = [
        TextRegion(
            id="title",
            bounding_box=BoundingBox(50, 50, 300, 40),
            text_content="Document Title",
            formatting=TextFormatting(font_size=18.0, is_bold=True),
            reading_order=0
        ),
        TextRegion(
            id="paragraph1",
            bounding_box=BoundingBox(50, 120, 300, 60),
            text_content="This is the first paragraph with some content.",
            formatting=TextFormatting(font_size=12.0),
            reading_order=1
        ),
        TextRegion(
            id="paragraph2",
            bounding_box=BoundingBox(50, 200, 300, 80),
            text_content="This is a longer second paragraph with more detailed content.",
            formatting=TextFormatting(font_size=12.0),
            reading_order=2
        )
    ]
    
    layout_analysis = LayoutAnalysis(
        page_number=1,
        text_regions=original_regions,
        spatial_relationships=[
            SpatialRelationship("title", "paragraph1", "above", 30.0, 0.9),
            SpatialRelationship("paragraph1", "paragraph2", "above", 20.0, 0.9)
        ],
        reading_order=["title", "paragraph1", "paragraph2"]
    )
    
    # Test different layout preservation scenarios
    layout_scenarios = [
        {
            "name": "Perfect Preservation",
            "adjustments": []  # No adjustments
        },
        {
            "name": "Minor Font Adjustments",
            "adjustments": [
                LayoutAdjustment(
                    adjustment_type=LayoutAdjustmentType.FONT_SIZE_CHANGE,
                    element_id="paragraph1",
                    original_value=12.0,
                    new_value=11.0,
                    reason="Minor font reduction for fitting"
                )
            ]
        },
        {
            "name": "Significant Layout Changes",
            "adjustments": [
                LayoutAdjustment(
                    adjustment_type=LayoutAdjustmentType.FONT_SIZE_CHANGE,
                    element_id="paragraph2",
                    original_value=12.0,
                    new_value=9.0,
                    reason="Major font reduction"
                ),
                LayoutAdjustment(
                    adjustment_type=LayoutAdjustmentType.BOUNDARY_EXPANSION,
                    element_id="paragraph2",
                    original_value=(300, 80),
                    new_value=(350, 100),
                    reason="Boundary expansion"
                ),
                LayoutAdjustment(
                    adjustment_type=LayoutAdjustmentType.POSITION_SHIFT,
                    element_id="paragraph2",
                    original_value=(50, 200),
                    new_value=(50, 220),
                    reason="Position adjustment"
                )
            ]
        }
    ]
    
    for scenario in layout_scenarios:
        print(f"  - Testing: {scenario['name']}")
        
        # Create adjusted regions based on scenario
        adjusted_regions = []
        for region in original_regions:
            # Find adjustments for this region
            region_adjustments = [adj for adj in scenario["adjustments"] if adj.element_id == region.id]
            
            # Apply adjustments to create adjusted region
            new_bounding_box = BoundingBox(
                x=region.bounding_box.x,
                y=region.bounding_box.y,
                width=region.bounding_box.width,
                height=region.bounding_box.height
            )
            
            fit_quality = 1.0
            for adj in region_adjustments:
                if adj.adjustment_type == LayoutAdjustmentType.FONT_SIZE_CHANGE:
                    fit_quality *= 0.9  # Slight quality reduction
                elif adj.adjustment_type == LayoutAdjustmentType.BOUNDARY_EXPANSION:
                    new_bounding_box.width, new_bounding_box.height = adj.new_value
                    fit_quality *= 0.8
                elif adj.adjustment_type == LayoutAdjustmentType.POSITION_SHIFT:
                    new_bounding_box.x, new_bounding_box.y = adj.new_value
                    fit_quality *= 0.9
            
            adjusted_region = AdjustedRegion(
                original_region=region,
                adjusted_text=f"Translated {region.text_content}",
                new_bounding_box=new_bounding_box,
                adjustments=region_adjustments,
                fit_quality=fit_quality
            )
            adjusted_regions.append(adjusted_region)
        
        # Assess layout preservation
        layout_quality = service.assess_layout_preservation(layout_analysis, adjusted_regions)
        
        print(f"    Overall Score: {layout_quality.overall_score:.2f}")
        print(f"    Layout Preservation: {layout_quality.metrics.layout_preservation:.2f}")
        print(f"    Formatting Preservation: {layout_quality.metrics.formatting_preservation:.2f}")
        print(f"    Visual Consistency: {layout_quality.metrics.visual_consistency:.2f}")
        print(f"    Issues Found: {len(layout_quality.issues)}")
        
        if layout_quality.issues:
            print("    Top Issues:")
            for issue in layout_quality.issues[:2]:
                print(f"      - {issue.severity.value}: {issue.description}")
    
    # Test quality report generation
    print("\n✓ Testing Quality Report Generation...")
    
    # Create test document
    document = DocumentStructure(
        format="pdf",
        pages=[
            PageStructure(
                page_number=1,
                dimensions=Dimensions(width=400, height=600),
                text_regions=original_regions
            )
        ],
        metadata=DocumentMetadata(title="Integration Test Document")
    )
    
    # Create overall assessment (combining translation and layout)
    overall_assessment = service.assess_translation_quality(
        "This is a comprehensive test document with multiple sections and detailed content.",
        "Ceci est un document de test complet avec plusieurs sections et un contenu détaillé."
    )
    
    # Create page assessments
    page_assessments = [overall_assessment]
    
    # Generate report
    report = service.generate_quality_report(document, page_assessments, overall_assessment)
    
    print(f"  - Document ID: {report.document_id}")
    print(f"  - Overall Score: {report.overall_score.overall_score:.2f} (Grade: {report.overall_score.grade})")
    print(f"  - Average Page Score: {report.average_page_score:.2f}")
    print(f"  - Total Issues: {report.total_issues}")
    print(f"  - Recommendations: {len(report.recommendations)}")
    print(f"  - High Priority Recommendations: {len(report.high_priority_recommendations)}")
    print(f"  - Summary: {report.summary}")
    
    if report.recommendations:
        print("  - Top Recommendations:")
        for rec in report.recommendations[:3]:
            print(f"    {rec.priority}/5: {rec.description} (Effort: {rec.estimated_effort})")
    
    print("\n🎉 Quality assessment integration test completed successfully!")
    return True

def test_quality_thresholds():
    """Test quality threshold functionality."""
    
    print("\n🧪 Testing Quality Thresholds...")
    
    from src.models.quality import QualityThreshold, QualityScore, QualityMetrics
    
    # Test different threshold scenarios
    thresholds = [
        {
            "name": "Lenient Thresholds",
            "threshold": QualityThreshold(
                minimum_overall_score=0.6,
                minimum_translation_accuracy=0.7,
                minimum_layout_preservation=0.6
            )
        },
        {
            "name": "Standard Thresholds", 
            "threshold": QualityThreshold()  # Default values
        },
        {
            "name": "Strict Thresholds",
            "threshold": QualityThreshold(
                minimum_overall_score=0.9,
                minimum_translation_accuracy=0.95,
                minimum_layout_preservation=0.9
            )
        }
    ]
    
    # Test quality score
    test_quality = QualityScore(
        overall_score=0.8,
        metrics=QualityMetrics(
            translation_accuracy=0.85,
            layout_preservation=0.75,
            readability=0.8
        )
    )
    
    for threshold_config in thresholds:
        print(f"  - Testing: {threshold_config['name']}")
        threshold = threshold_config["threshold"]
        meets_threshold = threshold.meets_threshold(test_quality)
        
        print(f"    Minimum Overall: {threshold.minimum_overall_score:.2f} (Actual: {test_quality.overall_score:.2f})")
        print(f"    Minimum Translation: {threshold.minimum_translation_accuracy:.2f} (Actual: {test_quality.metrics.translation_accuracy:.2f})")
        print(f"    Minimum Layout: {threshold.minimum_layout_preservation:.2f} (Actual: {test_quality.metrics.layout_preservation:.2f})")
        print(f"    Meets Threshold: {meets_threshold}")
        
        # Test with service
        service = QualityAssessmentService(quality_threshold=threshold)
        recommendations = service._generate_recommendations(test_quality, [])
        print(f"    Generated Recommendations: {len(recommendations)}")
    
    print("✓ Quality threshold testing completed!")

if __name__ == "__main__":
    try:
        test_quality_assessment_integration()
        test_quality_thresholds()
        print("\n✅ All quality assessment integration tests passed!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise
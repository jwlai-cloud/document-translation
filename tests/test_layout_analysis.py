"""Tests for layout analysis engine."""

import pytest
from unittest.mock import Mock, patch

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement,
    BoundingBox, Dimensions, TextFormatting, DocumentMetadata
)
from src.models.layout import LayoutAnalysis, SpatialRelationship
from src.layout.analysis_engine import DefaultLayoutAnalysisEngine


class TestDefaultLayoutAnalysisEngine:
    """Test cases for DefaultLayoutAnalysisEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = DefaultLayoutAnalysisEngine(proximity_threshold=10.0)
        
        # Create test text regions
        self.text_region1 = TextRegion(
            id="text1",
            bounding_box=BoundingBox(10, 10, 100, 20),
            text_content="First line of text",
            formatting=TextFormatting(font_size=12.0),
            confidence=0.9
        )
        
        self.text_region2 = TextRegion(
            id="text2", 
            bounding_box=BoundingBox(10, 40, 100, 20),
            text_content="Second line of text",
            formatting=TextFormatting(font_size=12.0),
            confidence=0.85
        )
        
        self.text_region3 = TextRegion(
            id="text3",
            bounding_box=BoundingBox(150, 10, 100, 20),
            text_content="Right column text",
            formatting=TextFormatting(font_size=12.0),
            confidence=0.88
        )
        
        # Create test visual elements
        self.visual_element1 = VisualElement(
            id="img1",
            element_type="image",
            bounding_box=BoundingBox(10, 80, 200, 100),
            metadata={"description": "Test image"}
        )
        
        self.visual_element2 = VisualElement(
            id="chart1",
            element_type="chart", 
            bounding_box=BoundingBox(250, 10, 150, 80),
            metadata={"chart_type": "bar"}
        )
        
        # Create test page
        self.test_page = PageStructure(
            page_number=1,
            dimensions=Dimensions(width=400, height=600),
            text_regions=[self.text_region1, self.text_region2, self.text_region3],
            visual_elements=[self.visual_element1, self.visual_element2]
        )
        
        # Create test document
        self.test_document = DocumentStructure(
            format="pdf",
            pages=[self.test_page],
            metadata=DocumentMetadata(title="Test Document")
        )
    
    def test_analyze_layout_returns_list(self):
        """Test that analyze_layout returns a list of LayoutAnalysis objects."""
        result = self.engine.analyze_layout(self.test_document)
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], LayoutAnalysis)
        assert result[0].page_number == 1
    
    def test_extract_text_regions_preserves_content(self):
        """Test that text region extraction preserves content."""
        regions = self.engine.extract_text_regions(self.test_page)
        
        assert len(regions) >= 3  # May merge some regions
        
        # Check that all original text content is preserved
        extracted_text = " ".join(r.text_content for r in regions)
        original_text = " ".join(r.text_content for r in self.test_page.text_regions)
        
        # Text should be preserved (order might change)
        for original_region in self.test_page.text_regions:
            assert original_region.text_content in extracted_text
    
    def test_extract_text_regions_sets_reading_order(self):
        """Test that reading order is properly set."""
        regions = self.engine.extract_text_regions(self.test_page)
        
        # Reading order should be sequential
        reading_orders = [r.reading_order for r in regions]
        assert reading_orders == list(range(len(regions)))
    
    def test_detect_visual_elements_enhances_classification(self):
        """Test that visual element detection enhances classification."""
        elements = self.engine.detect_visual_elements(self.test_page)
        
        assert len(elements) >= 2
        
        # Check that metadata was enhanced
        for element in elements:
            assert 'aspect_ratio' in element.metadata
            assert 'area' in element.metadata
            assert 'analysis_confidence' in element.metadata
    
    def test_calculate_spatial_relationships_finds_relationships(self):
        """Test that spatial relationships are calculated correctly."""
        all_elements = self.test_page.text_regions + self.test_page.visual_elements
        relationships = self.engine._calculate_spatial_relationships(all_elements)
        
        assert isinstance(relationships, list)
        assert len(relationships) > 0
        
        # Check relationship structure
        for rel in relationships:
            assert isinstance(rel, SpatialRelationship)
            assert rel.element1_id in [e.id for e in all_elements]
            assert rel.element2_id in [e.id for e in all_elements]
            assert rel.relationship_type in ["above", "below", "left", "right", "overlaps", "adjacent"]
            assert 0.0 <= rel.confidence <= 1.0
    
    def test_determine_spatial_relationship_detects_overlap(self):
        """Test overlap detection in spatial relationships."""
        # Create overlapping elements
        elem1 = TextRegion(
            id="overlap1",
            bounding_box=BoundingBox(10, 10, 50, 20)
        )
        elem2 = TextRegion(
            id="overlap2", 
            bounding_box=BoundingBox(30, 15, 50, 20)  # Overlaps with elem1
        )
        
        relationship = self.engine._determine_spatial_relationship(elem1, elem2)
        
        assert relationship.relationship_type == "overlaps"
        assert relationship.distance == 0.0
    
    def test_determine_spatial_relationship_detects_positions(self):
        """Test position detection in spatial relationships."""
        # Create elements with clear positional relationships
        left_elem = TextRegion(id="left", bounding_box=BoundingBox(10, 10, 20, 20))
        right_elem = TextRegion(id="right", bounding_box=BoundingBox(100, 10, 20, 20))
        
        relationship = self.engine._determine_spatial_relationship(left_elem, right_elem)
        
        assert relationship.relationship_type == "right"
        assert relationship.distance > 0
    
    def test_should_merge_regions_same_line(self):
        """Test region merging logic for same-line regions."""
        region1 = TextRegion(
            id="merge1",
            bounding_box=BoundingBox(10, 10, 30, 15),
            formatting=TextFormatting(font_family="Arial", font_size=12.0)
        )
        region2 = TextRegion(
            id="merge2",
            bounding_box=BoundingBox(45, 12, 30, 15),  # Same line, close proximity
            formatting=TextFormatting(font_family="Arial", font_size=12.0)
        )
        
        should_merge = self.engine._should_merge_regions(region1, region2)
        assert should_merge is True
    
    def test_should_not_merge_regions_different_lines(self):
        """Test that regions on different lines are not merged."""
        region1 = TextRegion(
            id="nomerge1",
            bounding_box=BoundingBox(10, 10, 30, 15),
            formatting=TextFormatting(font_family="Arial", font_size=12.0)
        )
        region2 = TextRegion(
            id="nomerge2", 
            bounding_box=BoundingBox(10, 50, 30, 15),  # Different line
            formatting=TextFormatting(font_family="Arial", font_size=12.0)
        )
        
        should_merge = self.engine._should_merge_regions(region1, region2)
        assert should_merge is False
    
    def test_merge_region_group_combines_content(self):
        """Test that region group merging combines content correctly."""
        regions = [
            TextRegion(
                id="group1",
                bounding_box=BoundingBox(10, 10, 20, 15),
                text_content="Hello",
                confidence=0.9
            ),
            TextRegion(
                id="group2",
                bounding_box=BoundingBox(35, 10, 20, 15), 
                text_content="world",
                confidence=0.8
            )
        ]
        
        merged = self.engine._merge_region_group(regions)
        
        assert merged.text_content == "Hello world"
        assert merged.confidence == 0.85  # Average of 0.9 and 0.8
        assert merged.bounding_box.x == 10
        assert merged.bounding_box.width == 45  # Spans both regions
    
    def test_determine_reading_order_sorts_correctly(self):
        """Test that reading order is determined correctly."""
        regions = [
            TextRegion(id="bottom", bounding_box=BoundingBox(10, 100, 50, 20)),
            TextRegion(id="top", bounding_box=BoundingBox(10, 10, 50, 20)),
            TextRegion(id="middle", bounding_box=BoundingBox(10, 50, 50, 20))
        ]
        
        reading_order = self.engine._determine_reading_order(regions)
        
        assert reading_order == ["top", "middle", "bottom"]
    
    def test_detect_column_structure_groups_columns(self):
        """Test column structure detection."""
        regions = [
            TextRegion(id="left1", bounding_box=BoundingBox(10, 10, 50, 20)),
            TextRegion(id="left2", bounding_box=BoundingBox(15, 40, 50, 20)),
            TextRegion(id="right1", bounding_box=BoundingBox(200, 10, 50, 20)),
            TextRegion(id="right2", bounding_box=BoundingBox(205, 40, 50, 20))
        ]
        
        columns = self.engine._detect_column_structure(regions)
        
        assert len(columns) == 2  # Two columns detected
        # Each column should have 2 regions
        assert all(len(col) == 2 for col in columns)
    
    def test_calculate_layout_complexity_returns_valid_score(self):
        """Test layout complexity calculation."""
        text_regions = [self.text_region1, self.text_region2]
        visual_elements = [self.visual_element1]
        relationships = [
            SpatialRelationship("text1", "text2", "below", 30.0, 0.9),
            SpatialRelationship("text1", "img1", "above", 50.0, 0.8)
        ]
        
        complexity = self.engine._calculate_layout_complexity(
            text_regions, visual_elements, relationships
        )
        
        assert 0.0 <= complexity <= 1.0
        assert isinstance(complexity, float)
    
    def test_analyze_page_layout_complete_analysis(self):
        """Test complete page layout analysis."""
        analysis = self.engine._analyze_page_layout(self.test_page)
        
        assert isinstance(analysis, LayoutAnalysis)
        assert analysis.page_number == 1
        assert len(analysis.text_regions) > 0
        assert len(analysis.visual_elements) > 0
        assert len(analysis.spatial_relationships) > 0
        assert len(analysis.reading_order) > 0
        assert 0.0 <= analysis.layout_complexity <= 1.0
    
    def test_empty_page_handling(self):
        """Test handling of empty pages."""
        empty_page = PageStructure(
            page_number=1,
            dimensions=Dimensions(width=400, height=600),
            text_regions=[],
            visual_elements=[]
        )
        
        analysis = self.engine._analyze_page_layout(empty_page)
        
        assert analysis.page_number == 1
        assert len(analysis.text_regions) == 0
        assert len(analysis.visual_elements) == 0
        assert len(analysis.spatial_relationships) == 0
        assert len(analysis.reading_order) == 0
        assert analysis.layout_complexity == 0.0
    
    def test_proximity_threshold_affects_relationships(self):
        """Test that proximity threshold affects relationship detection."""
        # Test with small threshold
        engine_small = DefaultLayoutAnalysisEngine(proximity_threshold=5.0)
        
        # Test with large threshold  
        engine_large = DefaultLayoutAnalysisEngine(proximity_threshold=50.0)
        
        elem1 = TextRegion(id="test1", bounding_box=BoundingBox(10, 10, 20, 20))
        elem2 = TextRegion(id="test2", bounding_box=BoundingBox(40, 10, 20, 20))
        
        rel_small = engine_small._determine_spatial_relationship(elem1, elem2)
        rel_large = engine_large._determine_spatial_relationship(elem1, elem2)
        
        # With large threshold, elements should be considered adjacent
        assert rel_large.relationship_type == "adjacent"
        # With small threshold, should be directional relationship
        assert rel_small.relationship_type in ["left", "right", "above", "below"]


if __name__ == "__main__":
    pytest.main([__file__])
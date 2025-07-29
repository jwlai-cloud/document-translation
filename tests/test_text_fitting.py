"""Tests for text fitting and layout adjustment algorithms."""

import pytest
from unittest.mock import Mock

from src.models.document import TextRegion, BoundingBox, TextFormatting
from src.models.layout import (
    LayoutAdjustment, LayoutAdjustmentType, AdjustedRegion,
    TextFittingResult, LayoutConflict, ConflictResolution
)
from src.layout.text_fitting import (
    TextFittingEngine, LayoutAdjustmentEngine, TextMetrics
)


class TestTextFittingEngine:
    """Test cases for TextFittingEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = TextFittingEngine(
            min_font_size=8.0,
            max_font_size=72.0,
            max_font_reduction=0.3,
            max_expansion_ratio=1.2
        )
        
        # Create test text region
        self.test_region = TextRegion(
            id="test_region",
            bounding_box=BoundingBox(10, 10, 200, 50),
            text_content="Hello world",
            formatting=TextFormatting(font_size=12.0, font_family="Arial"),
            confidence=0.9
        )
    
    def test_calculate_text_metrics_basic(self):
        """Test basic text metrics calculation."""
        formatting = TextFormatting(font_size=12.0)
        metrics = self.engine._calculate_text_metrics("Hello world", formatting)
        
        assert isinstance(metrics, TextMetrics)
        assert metrics.character_count == 11
        assert metrics.word_count == 2
        assert metrics.character_width == 12.0 * 0.6  # Expected calculation
        assert metrics.line_height == 12.0 * 1.2  # Expected calculation
        assert metrics.estimated_width > 0
        assert metrics.estimated_height > 0
    
    def test_calculate_text_metrics_empty_text(self):
        """Test text metrics calculation with empty text."""
        formatting = TextFormatting(font_size=12.0)
        metrics = self.engine._calculate_text_metrics("", formatting)
        
        assert metrics.character_count == 0
        assert metrics.word_count == 0
        assert metrics.estimated_width == 0
        assert metrics.estimated_height == 0
    
    def test_fit_text_to_region_no_adjustment_needed(self):
        """Test text fitting when no adjustment is needed."""
        # Short text that should fit easily
        short_text = "Hi"
        
        result = self.engine.fit_text_to_region(self.test_region, short_text)
        
        assert isinstance(result, AdjustedRegion)
        assert result.adjusted_text == short_text
        assert result.fit_quality == 1.0
        assert len(result.adjustments) == 0  # No adjustments needed
    
    def test_fit_text_to_region_font_reduction(self):
        """Test text fitting with font size reduction."""
        # Longer text that requires font reduction
        long_text = "This is a much longer text that will require font size reduction to fit properly"
        
        result = self.engine.fit_text_to_region(self.test_region, long_text)
        
        assert isinstance(result, AdjustedRegion)
        assert result.adjusted_text == long_text
        assert result.fit_quality < 1.0
        
        # Should have font size adjustment
        font_adjustments = [adj for adj in result.adjustments 
                          if adj.adjustment_type == LayoutAdjustmentType.FONT_SIZE_CHANGE]
        assert len(font_adjustments) > 0
        assert font_adjustments[0].new_value < font_adjustments[0].original_value
    
    def test_fit_text_to_region_truncation_required(self):
        """Test text fitting when truncation is required."""
        # Extremely long text that requires truncation
        very_long_text = "This is an extremely long text " * 50
        
        result = self.engine.fit_text_to_region(self.test_region, very_long_text)
        
        assert isinstance(result, AdjustedRegion)
        assert len(result.adjusted_text) < len(very_long_text)
        assert result.adjusted_text.endswith("...")
        assert result.fit_quality < 0.5  # Low quality due to truncation
    
    def test_determine_fitting_strategy_perfect_fit(self):
        """Test fitting strategy determination for perfect fit."""
        original_metrics = TextMetrics(7.2, 14.4, 2, 11, 79.2, 14.4)
        translated_metrics = TextMetrics(7.2, 14.4, 2, 10, 72.0, 14.4)  # Slightly smaller
        
        result = self.engine._determine_fitting_strategy(
            self.test_region, original_metrics, translated_metrics, "Hello test"
        )
        
        assert isinstance(result, TextFittingResult)
        assert result.fit_score == 1.0
        assert result.font_size_adjustment == 0.0
        assert not result.requires_truncation
    
    def test_determine_fitting_strategy_minor_reduction(self):
        """Test fitting strategy for minor font reduction."""
        original_metrics = TextMetrics(7.2, 14.4, 2, 11, 79.2, 14.4)
        translated_metrics = TextMetrics(7.2, 14.4, 3, 15, 108.0, 14.4)  # Slightly larger
        
        result = self.engine._determine_fitting_strategy(
            self.test_region, original_metrics, translated_metrics, "Hello test longer"
        )
        
        assert isinstance(result, TextFittingResult)
        assert result.fit_score == 0.8
        assert result.font_size_adjustment < 0.0  # Font reduction
        assert not result.requires_truncation
    
    def test_determine_fitting_strategy_truncation(self):
        """Test fitting strategy when truncation is needed."""
        original_metrics = TextMetrics(7.2, 14.4, 2, 11, 79.2, 14.4)
        translated_metrics = TextMetrics(7.2, 14.4, 20, 150, 1080.0, 144.0)  # Much larger
        
        result = self.engine._determine_fitting_strategy(
            self.test_region, original_metrics, translated_metrics, "Very long text " * 10
        )
        
        assert isinstance(result, TextFittingResult)
        assert result.fit_score < 0.5
        assert result.requires_truncation
        assert len(result.fitted_text) < len("Very long text " * 10)
    
    def test_apply_text_fitting_with_adjustments(self):
        """Test applying text fitting with various adjustments."""
        fitting_result = TextFittingResult(
            original_text="Hello",
            fitted_text="Hello world",
            font_size_adjustment=-0.2,  # 20% reduction
            line_spacing_adjustment=-0.1,  # 10% reduction
            requires_truncation=False,
            fit_score=0.7
        )
        
        result = self.engine._apply_text_fitting(self.test_region, fitting_result)
        
        assert isinstance(result, AdjustedRegion)
        assert result.adjusted_text == "Hello world"
        assert result.fit_quality == 0.7
        
        # Check for font size adjustment
        font_adjustments = [adj for adj in result.adjustments 
                          if adj.adjustment_type == LayoutAdjustmentType.FONT_SIZE_CHANGE]
        assert len(font_adjustments) == 1
        assert font_adjustments[0].new_value < font_adjustments[0].original_value
        
        # Check for line spacing adjustment
        spacing_adjustments = [adj for adj in result.adjustments 
                             if adj.adjustment_type == LayoutAdjustmentType.LINE_SPACING_CHANGE]
        assert len(spacing_adjustments) == 1
    
    def test_calculate_adjusted_bounding_box_expansion(self):
        """Test bounding box calculation with expansion."""
        fitting_result = TextFittingResult(
            original_text="Hi",
            fitted_text="This is much longer text",
            font_size_adjustment=0.0,
            fit_score=0.8
        )
        formatting = TextFormatting(font_size=12.0)
        
        new_box = self.engine._calculate_adjusted_bounding_box(
            self.test_region.bounding_box, fitting_result, formatting
        )
        
        assert isinstance(new_box, BoundingBox)
        assert new_box.x == self.test_region.bounding_box.x  # Position unchanged
        assert new_box.y == self.test_region.bounding_box.y
        # Width or height should be expanded
        assert (new_box.width >= self.test_region.bounding_box.width or 
                new_box.height >= self.test_region.bounding_box.height)
    
    def test_calculate_adjusted_bounding_box_no_expansion(self):
        """Test bounding box calculation without expansion needed."""
        fitting_result = TextFittingResult(
            original_text="Hello world",
            fitted_text="Hi",  # Shorter text
            font_size_adjustment=0.0,
            fit_score=1.0
        )
        formatting = TextFormatting(font_size=12.0)
        
        new_box = self.engine._calculate_adjusted_bounding_box(
            self.test_region.bounding_box, fitting_result, formatting
        )
        
        assert new_box.width == self.test_region.bounding_box.width
        assert new_box.height == self.test_region.bounding_box.height


class TestLayoutAdjustmentEngine:
    """Test cases for LayoutAdjustmentEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = LayoutAdjustmentEngine(overlap_threshold=5.0)
        
        # Create test adjusted regions
        self.region1 = AdjustedRegion(
            original_region=TextRegion(
                id="region1",
                bounding_box=BoundingBox(10, 10, 100, 30),
                text_content="First region"
            ),
            adjusted_text="First region translated",
            new_bounding_box=BoundingBox(10, 10, 120, 35),
            fit_quality=0.8
        )
        
        self.region2 = AdjustedRegion(
            original_region=TextRegion(
                id="region2", 
                bounding_box=BoundingBox(50, 50, 100, 30),
                text_content="Second region"
            ),
            adjusted_text="Second region translated",
            new_bounding_box=BoundingBox(50, 50, 110, 32),
            fit_quality=0.9
        )
        
        # Create overlapping region
        self.overlapping_region = AdjustedRegion(
            original_region=TextRegion(
                id="overlap",
                bounding_box=BoundingBox(80, 25, 100, 30),
                text_content="Overlapping region"
            ),
            adjusted_text="Overlapping region translated",
            new_bounding_box=BoundingBox(80, 25, 120, 35),
            fit_quality=0.7
        )
    
    def test_detect_layout_conflicts_no_conflicts(self):
        """Test conflict detection when no conflicts exist."""
        regions = [self.region1, self.region2]
        
        conflicts = self.engine.detect_layout_conflicts(regions)
        
        assert isinstance(conflicts, list)
        assert len(conflicts) == 0
    
    def test_detect_layout_conflicts_overlap(self):
        """Test conflict detection for overlapping regions."""
        regions = [self.region1, self.overlapping_region]
        
        conflicts = self.engine.detect_layout_conflicts(regions)
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "overlap"
        assert set(conflicts[0].element_ids) == {"region1", "overlap"}
        assert 0.0 < conflicts[0].severity <= 1.0
    
    def test_detect_layout_conflicts_spacing(self):
        """Test conflict detection for spacing issues."""
        # Create regions that are too close
        close_region = AdjustedRegion(
            original_region=TextRegion(
                id="close",
                bounding_box=BoundingBox(10, 47, 100, 30),  # Very close to region1
                text_content="Close region"
            ),
            adjusted_text="Close region translated",
            new_bounding_box=BoundingBox(10, 47, 100, 30),
            fit_quality=0.8
        )
        
        regions = [self.region1, close_region]
        
        conflicts = self.engine.detect_layout_conflicts(regions)
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "spacing"
        assert 0.0 < conflicts[0].severity <= 1.0
    
    def test_check_region_conflict_overlap(self):
        """Test individual region conflict checking for overlap."""
        conflict = self.engine._check_region_conflict(self.region1, self.overlapping_region)
        
        assert conflict is not None
        assert conflict.conflict_type == "overlap"
        assert set(conflict.element_ids) == {"region1", "overlap"}
        assert conflict.severity > 0.0
    
    def test_check_region_conflict_no_conflict(self):
        """Test individual region conflict checking when no conflict exists."""
        conflict = self.engine._check_region_conflict(self.region1, self.region2)
        
        assert conflict is None
    
    def test_calculate_minimum_distance(self):
        """Test minimum distance calculation between bounding boxes."""
        box1 = BoundingBox(10, 10, 50, 30)
        box2 = BoundingBox(80, 10, 50, 30)  # Separated horizontally
        
        distance = self.engine._calculate_minimum_distance(box1, box2)
        
        assert distance > 0
        assert isinstance(distance, float)
    
    def test_calculate_minimum_distance_overlapping(self):
        """Test minimum distance calculation for overlapping boxes."""
        box1 = BoundingBox(10, 10, 50, 30)
        box2 = BoundingBox(30, 20, 50, 30)  # Overlapping
        
        distance = self.engine._calculate_minimum_distance(box1, box2)
        
        assert distance == 0.0  # Overlapping boxes have 0 distance
    
    def test_resolve_conflicts_overlap(self):
        """Test conflict resolution for overlap conflicts."""
        conflict = LayoutConflict(
            conflict_type="overlap",
            element_ids=["region1", "overlap"],
            severity=0.8,
            description="Test overlap"
        )
        
        regions = [self.region1, self.overlapping_region]
        resolutions = self.engine.resolve_conflicts([conflict], regions)
        
        assert len(resolutions) == 1
        assert resolutions[0].resolution_type == "reposition"
        assert len(resolutions[0].actions) == 1
        assert resolutions[0].actions[0].adjustment_type == LayoutAdjustmentType.POSITION_SHIFT
    
    def test_resolve_conflicts_spacing(self):
        """Test conflict resolution for spacing conflicts."""
        conflict = LayoutConflict(
            conflict_type="spacing",
            element_ids=["region1", "region2"],
            severity=0.6,
            description="Test spacing"
        )
        
        regions = [self.region1, self.region2]
        resolutions = self.engine.resolve_conflicts([conflict], regions)
        
        assert len(resolutions) == 1
        assert resolutions[0].resolution_type == "reposition"
        assert len(resolutions[0].actions) == 1
        assert resolutions[0].success_probability > 0.0
    
    def test_resolve_single_conflict_invalid_elements(self):
        """Test conflict resolution with invalid element IDs."""
        conflict = LayoutConflict(
            conflict_type="overlap",
            element_ids=["nonexistent1", "nonexistent2"],
            severity=0.8
        )
        
        regions = [self.region1, self.region2]
        resolution = self.engine._resolve_single_conflict(conflict, regions)
        
        assert resolution is None
    
    def test_resolve_overlap_conflict_chooses_lower_quality(self):
        """Test that overlap resolution chooses to move the lower quality region."""
        # Set different fit qualities
        self.region1.fit_quality = 0.9  # Higher quality
        self.overlapping_region.fit_quality = 0.6  # Lower quality
        
        conflict = LayoutConflict(
            conflict_type="overlap",
            element_ids=["region1", "overlap"],
            severity=0.8
        )
        
        resolution = self.engine._resolve_overlap_conflict(
            conflict, self.region1, self.overlapping_region
        )
        
        assert resolution.actions[0].element_id == "overlap"  # Lower quality region moved
    
    def test_resolve_spacing_conflict_maintains_spacing(self):
        """Test that spacing conflict resolution maintains proper spacing."""
        conflict = LayoutConflict(
            conflict_type="spacing",
            element_ids=["region1", "region2"],
            severity=0.5
        )
        
        resolution = self.engine._resolve_spacing_conflict(
            conflict, self.region1, self.region2
        )
        
        assert len(resolution.actions) == 1
        action = resolution.actions[0]
        
        # Check that new position maintains spacing
        original_y = action.original_value[1]
        new_y = action.new_value[1]
        assert abs(new_y - original_y) >= self.engine.overlap_threshold
    
    def test_empty_regions_list(self):
        """Test handling of empty regions list."""
        conflicts = self.engine.detect_layout_conflicts([])
        assert len(conflicts) == 0
        
        resolutions = self.engine.resolve_conflicts([], [])
        assert len(resolutions) == 0
    
    def test_single_region_no_conflicts(self):
        """Test that single region produces no conflicts."""
        conflicts = self.engine.detect_layout_conflicts([self.region1])
        assert len(conflicts) == 0


if __name__ == "__main__":
    pytest.main([__file__])
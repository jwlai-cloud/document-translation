"""Text fitting and layout adjustment algorithms."""

import math
from typing import List, Tuple, Optional
from dataclasses import dataclass

from src.models.document import TextRegion, BoundingBox, TextFormatting
from src.models.layout import (
    LayoutAdjustment, LayoutAdjustmentType, AdjustedRegion, 
    TextFittingResult, LayoutConflict, ConflictResolution
)


@dataclass
class TextMetrics:
    """Metrics for text measurement."""
    character_width: float
    line_height: float
    word_count: int
    character_count: int
    estimated_width: float
    estimated_height: float


class TextFittingEngine:
    """Engine for fitting translated text into original layout regions."""
    
    def __init__(self, 
                 min_font_size: float = 8.0,
                 max_font_size: float = 72.0,
                 max_font_reduction: float = 0.3,
                 max_expansion_ratio: float = 1.2):
        """Initialize text fitting engine.
        
        Args:
            min_font_size: Minimum allowed font size
            max_font_size: Maximum allowed font size  
            max_font_reduction: Maximum font size reduction (as ratio)
            max_expansion_ratio: Maximum bounding box expansion ratio
        """
        self.min_font_size = min_font_size
        self.max_font_size = max_font_size
        self.max_font_reduction = max_font_reduction
        self.max_expansion_ratio = max_expansion_ratio
    
    def fit_text_to_region(self, region: TextRegion, translated_text: str) -> AdjustedRegion:
        """Fit translated text into a text region.
        
        Args:
            region: Original text region
            translated_text: Translated text to fit
            
        Returns:
            AdjustedRegion with fitted text and adjustments
        """
        # Calculate text metrics for original and translated text
        original_metrics = self._calculate_text_metrics(
            region.text_content, region.formatting
        )
        translated_metrics = self._calculate_text_metrics(
            translated_text, region.formatting
        )
        
        # Determine fitting strategy
        fitting_result = self._determine_fitting_strategy(
            region, original_metrics, translated_metrics, translated_text
        )
        
        # Apply adjustments
        adjusted_region = self._apply_text_fitting(region, fitting_result)
        
        return adjusted_region
    
    def _calculate_text_metrics(self, text: str, formatting: TextFormatting) -> TextMetrics:
        """Calculate metrics for text with given formatting."""
        if not text:
            return TextMetrics(0, 0, 0, 0, 0, 0)
        
        # Estimate character width based on font size
        # This is a simplified calculation - real implementation would use font metrics
        avg_char_width = formatting.font_size * 0.6  # Rough approximation
        line_height = formatting.font_size * 1.2  # Standard line height
        
        word_count = len(text.split())
        character_count = len(text)
        
        # Estimate dimensions
        estimated_width = character_count * avg_char_width
        
        # Estimate number of lines (rough calculation)
        words_per_line = max(1, int(estimated_width / (avg_char_width * 10)))  # Assume ~10 chars per word
        estimated_lines = max(1, math.ceil(word_count / words_per_line))
        estimated_height = estimated_lines * line_height
        
        return TextMetrics(
            character_width=avg_char_width,
            line_height=line_height,
            word_count=word_count,
            character_count=character_count,
            estimated_width=estimated_width,
            estimated_height=estimated_height
        )
    
    def _determine_fitting_strategy(self, 
                                  region: TextRegion,
                                  original_metrics: TextMetrics,
                                  translated_metrics: TextMetrics,
                                  translated_text: str) -> TextFittingResult:
        """Determine the best strategy for fitting translated text."""
        
        available_width = region.bounding_box.width
        available_height = region.bounding_box.height
        
        # Calculate expansion ratios
        width_ratio = translated_metrics.estimated_width / available_width
        height_ratio = translated_metrics.estimated_height / available_height
        
        # Start with no adjustments
        font_size_adjustment = 0.0
        line_spacing_adjustment = 0.0
        requires_truncation = False
        truncated_content = ""
        fitted_text = translated_text
        
        # Strategy 1: Text fits without adjustments
        if width_ratio <= 1.0 and height_ratio <= 1.0:
            fit_score = 1.0
        
        # Strategy 2: Minor font size reduction
        elif width_ratio <= 1.3 and height_ratio <= 1.3:
            reduction_needed = max(width_ratio, height_ratio)
            font_size_adjustment = -min(self.max_font_reduction, 1.0 - (1.0 / reduction_needed))
            fit_score = 0.8
        
        # Strategy 3: Significant adjustments needed
        elif width_ratio <= 2.0 and height_ratio <= 2.0:
            # Try more aggressive font reduction
            reduction_needed = max(width_ratio, height_ratio)
            font_size_adjustment = -min(self.max_font_reduction, 1.0 - (1.0 / reduction_needed))
            line_spacing_adjustment = -0.1  # Reduce line spacing
            fit_score = 0.6
        
        # Strategy 4: Truncation required
        else:
            font_size_adjustment = -self.max_font_reduction
            line_spacing_adjustment = -0.2
            requires_truncation = True
            
            # Calculate how much text can fit
            max_chars = int(original_metrics.character_count * 0.8)  # Conservative estimate
            if len(translated_text) > max_chars:
                fitted_text = translated_text[:max_chars-3] + "..."
                truncated_content = translated_text[max_chars-3:]
            
            fit_score = 0.3
        
        return TextFittingResult(
            original_text=region.text_content,
            fitted_text=fitted_text,
            font_size_adjustment=font_size_adjustment,
            line_spacing_adjustment=line_spacing_adjustment,
            requires_truncation=requires_truncation,
            truncated_content=truncated_content,
            fit_score=fit_score
        )
    
    def _apply_text_fitting(self, region: TextRegion, fitting_result: TextFittingResult) -> AdjustedRegion:
        """Apply text fitting adjustments to create adjusted region."""
        adjustments = []
        
        # Create new formatting with adjustments
        new_formatting = TextFormatting(
            font_family=region.formatting.font_family,
            font_size=region.formatting.font_size,
            is_bold=region.formatting.is_bold,
            is_italic=region.formatting.is_italic,
            is_underlined=region.formatting.is_underlined,
            color=region.formatting.color,
            background_color=region.formatting.background_color,
            alignment=region.formatting.alignment
        )
        
        # Apply font size adjustment
        if fitting_result.font_size_adjustment != 0.0:
            original_size = region.formatting.font_size
            new_size = max(
                self.min_font_size,
                min(self.max_font_size, original_size * (1 + fitting_result.font_size_adjustment))
            )
            new_formatting.font_size = new_size
            
            adjustments.append(LayoutAdjustment(
                adjustment_type=LayoutAdjustmentType.FONT_SIZE_CHANGE,
                element_id=region.id,
                original_value=original_size,
                new_value=new_size,
                confidence=0.9,
                reason=f"Font size adjusted by {fitting_result.font_size_adjustment:.1%}"
            ))
        
        # Apply line spacing adjustment (stored in metadata for now)
        if fitting_result.line_spacing_adjustment != 0.0:
            adjustments.append(LayoutAdjustment(
                adjustment_type=LayoutAdjustmentType.LINE_SPACING_CHANGE,
                element_id=region.id,
                original_value=1.0,  # Default line spacing
                new_value=1.0 + fitting_result.line_spacing_adjustment,
                confidence=0.8,
                reason=f"Line spacing adjusted by {fitting_result.line_spacing_adjustment:.1%}"
            ))
        
        # Calculate new bounding box (may need expansion)
        new_bounding_box = self._calculate_adjusted_bounding_box(
            region.bounding_box, fitting_result, new_formatting
        )
        
        # Add position adjustment if bounding box changed
        if (new_bounding_box.width != region.bounding_box.width or 
            new_bounding_box.height != region.bounding_box.height):
            adjustments.append(LayoutAdjustment(
                adjustment_type=LayoutAdjustmentType.BOUNDARY_EXPANSION,
                element_id=region.id,
                original_value=(region.bounding_box.width, region.bounding_box.height),
                new_value=(new_bounding_box.width, new_bounding_box.height),
                confidence=0.7,
                reason="Bounding box adjusted for text fitting"
            ))
        
        # Create adjusted region
        adjusted_region = AdjustedRegion(
            original_region=region,
            adjusted_text=fitting_result.fitted_text,
            new_bounding_box=new_bounding_box,
            adjustments=adjustments,
            fit_quality=fitting_result.fit_score
        )
        
        return adjusted_region
    
    def _calculate_adjusted_bounding_box(self, 
                                       original_box: BoundingBox,
                                       fitting_result: TextFittingResult,
                                       new_formatting: TextFormatting) -> BoundingBox:
        """Calculate adjusted bounding box based on text fitting."""
        
        # Recalculate text metrics with new formatting
        new_metrics = self._calculate_text_metrics(fitting_result.fitted_text, new_formatting)
        
        # Calculate required dimensions
        required_width = new_metrics.estimated_width
        required_height = new_metrics.estimated_height
        
        # Determine new dimensions
        new_width = original_box.width
        new_height = original_box.height
        
        # Expand if necessary (within limits)
        if required_width > original_box.width:
            expansion_ratio = min(self.max_expansion_ratio, required_width / original_box.width)
            new_width = original_box.width * expansion_ratio
        
        if required_height > original_box.height:
            expansion_ratio = min(self.max_expansion_ratio, required_height / original_box.height)
            new_height = original_box.height * expansion_ratio
        
        return BoundingBox(
            x=original_box.x,
            y=original_box.y,
            width=new_width,
            height=new_height
        )


class LayoutAdjustmentEngine:
    """Engine for handling layout adjustments and conflict resolution."""
    
    def __init__(self, overlap_threshold: float = 5.0):
        """Initialize layout adjustment engine.
        
        Args:
            overlap_threshold: Minimum overlap distance to consider as conflict
        """
        self.overlap_threshold = overlap_threshold
    
    def detect_layout_conflicts(self, adjusted_regions: List[AdjustedRegion]) -> List[LayoutConflict]:
        """Detect conflicts between adjusted regions.
        
        Args:
            adjusted_regions: List of adjusted text regions
            
        Returns:
            List of detected layout conflicts
        """
        conflicts = []
        
        for i, region1 in enumerate(adjusted_regions):
            for j, region2 in enumerate(adjusted_regions):
                if i >= j:  # Avoid duplicate checks
                    continue
                
                conflict = self._check_region_conflict(region1, region2)
                if conflict:
                    conflicts.append(conflict)
        
        return conflicts
    
    def resolve_conflicts(self, conflicts: List[LayoutConflict], 
                         adjusted_regions: List[AdjustedRegion]) -> List[ConflictResolution]:
        """Resolve layout conflicts.
        
        Args:
            conflicts: List of conflicts to resolve
            adjusted_regions: List of adjusted regions
            
        Returns:
            List of conflict resolutions
        """
        resolutions = []
        
        for conflict in conflicts:
            resolution = self._resolve_single_conflict(conflict, adjusted_regions)
            if resolution:
                resolutions.append(resolution)
        
        return resolutions
    
    def _check_region_conflict(self, region1: AdjustedRegion, region2: AdjustedRegion) -> Optional[LayoutConflict]:
        """Check if two regions have a layout conflict."""
        box1 = region1.new_bounding_box
        box2 = region2.new_bounding_box
        
        # Check for overlap
        if box1.overlaps_with(box2):
            # Calculate overlap area
            overlap_x = max(0, min(box1.x + box1.width, box2.x + box2.width) - max(box1.x, box2.x))
            overlap_y = max(0, min(box1.y + box1.height, box2.y + box2.height) - max(box1.y, box2.y))
            overlap_area = overlap_x * overlap_y
            
            # Calculate severity based on overlap percentage
            total_area = min(box1.area(), box2.area())
            severity = min(1.0, overlap_area / total_area) if total_area > 0 else 1.0
            
            return LayoutConflict(
                conflict_type="overlap",
                element_ids=[region1.original_region.id, region2.original_region.id],
                severity=severity,
                description=f"Regions overlap by {overlap_area:.1f} square units"
            )
        
        # Check for spacing issues (too close)
        min_distance = self._calculate_minimum_distance(box1, box2)
        if min_distance < self.overlap_threshold:
            severity = max(0.1, 1.0 - (min_distance / self.overlap_threshold))
            
            return LayoutConflict(
                conflict_type="spacing",
                element_ids=[region1.original_region.id, region2.original_region.id],
                severity=severity,
                description=f"Regions too close: {min_distance:.1f} units apart"
            )
        
        return None
    
    def _calculate_minimum_distance(self, box1: BoundingBox, box2: BoundingBox) -> float:
        """Calculate minimum distance between two bounding boxes."""
        # Calculate center points
        center1_x = box1.x + box1.width / 2
        center1_y = box1.y + box1.height / 2
        center2_x = box2.x + box2.width / 2
        center2_y = box2.y + box2.height / 2
        
        # Calculate distance between centers
        dx = abs(center2_x - center1_x) - (box1.width + box2.width) / 2
        dy = abs(center2_y - center1_y) - (box1.height + box2.height) / 2
        
        # Return minimum distance (0 if overlapping)
        return max(0, math.sqrt(max(0, dx)**2 + max(0, dy)**2))
    
    def _resolve_single_conflict(self, conflict: LayoutConflict, 
                               adjusted_regions: List[AdjustedRegion]) -> Optional[ConflictResolution]:
        """Resolve a single layout conflict."""
        if len(conflict.element_ids) != 2:
            return None
        
        # Find the conflicting regions
        region1 = None
        region2 = None
        
        for region in adjusted_regions:
            if region.original_region.id == conflict.element_ids[0]:
                region1 = region
            elif region.original_region.id == conflict.element_ids[1]:
                region2 = region
        
        if not region1 or not region2:
            return None
        
        # Choose resolution strategy based on conflict type and severity
        if conflict.conflict_type == "overlap":
            return self._resolve_overlap_conflict(conflict, region1, region2)
        elif conflict.conflict_type == "spacing":
            return self._resolve_spacing_conflict(conflict, region1, region2)
        
        return None
    
    def _resolve_overlap_conflict(self, conflict: LayoutConflict,
                                region1: AdjustedRegion, region2: AdjustedRegion) -> ConflictResolution:
        """Resolve an overlap conflict between two regions."""
        actions = []
        
        # Strategy: Move the region with lower fit quality
        if region1.fit_quality < region2.fit_quality:
            target_region = region1
            reference_region = region2
        else:
            target_region = region2
            reference_region = region1
        
        # Calculate new position (move below the reference region)
        new_y = reference_region.new_bounding_box.y + reference_region.new_bounding_box.height + 5
        
        actions.append(LayoutAdjustment(
            adjustment_type=LayoutAdjustmentType.POSITION_SHIFT,
            element_id=target_region.original_region.id,
            original_value=(target_region.new_bounding_box.x, target_region.new_bounding_box.y),
            new_value=(target_region.new_bounding_box.x, new_y),
            confidence=0.8,
            reason="Repositioned to resolve overlap conflict"
        ))
        
        return ConflictResolution(
            conflict_id=conflict.id,
            resolution_type="reposition",
            actions=actions,
            success_probability=0.8
        )
    
    def _resolve_spacing_conflict(self, conflict: LayoutConflict,
                                region1: AdjustedRegion, region2: AdjustedRegion) -> ConflictResolution:
        """Resolve a spacing conflict between two regions."""
        actions = []
        
        # Strategy: Add minimum spacing between regions
        box1 = region1.new_bounding_box
        box2 = region2.new_bounding_box
        
        # Determine which region to move (prefer moving the one with lower fit quality)
        if region1.fit_quality < region2.fit_quality:
            target_region = region1
            reference_region = region2
            target_box = box1
            reference_box = box2
        else:
            target_region = region2
            reference_region = region1
            target_box = box2
            reference_box = box1
        
        # Calculate new position with proper spacing
        if target_box.y < reference_box.y:
            # Target is above reference - move it up
            new_y = reference_box.y - target_box.height - self.overlap_threshold
        else:
            # Target is below reference - move it down
            new_y = reference_box.y + reference_box.height + self.overlap_threshold
        
        actions.append(LayoutAdjustment(
            adjustment_type=LayoutAdjustmentType.POSITION_SHIFT,
            element_id=target_region.original_region.id,
            original_value=(target_box.x, target_box.y),
            new_value=(target_box.x, new_y),
            confidence=0.9,
            reason="Repositioned to maintain proper spacing"
        ))
        
        return ConflictResolution(
            conflict_id=conflict.id,
            resolution_type="reposition",
            actions=actions,
            success_probability=0.9
        )
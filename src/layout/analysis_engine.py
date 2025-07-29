"""Layout analysis engine implementation."""

import math
from typing import List, Dict, Tuple, Set
from collections import defaultdict

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, VisualElement, 
    BoundingBox, SpatialMap
)
from src.models.layout import (
    LayoutAnalysis, SpatialRelationship, LayoutMetrics
)
from src.layout.base import LayoutAnalysisEngine


class DefaultLayoutAnalysisEngine(LayoutAnalysisEngine):
    """Default implementation of layout analysis engine."""
    
    def __init__(self, proximity_threshold: float = 10.0):
        """Initialize the layout analysis engine.
        
        Args:
            proximity_threshold: Distance threshold for considering elements as adjacent
        """
        self.proximity_threshold = proximity_threshold
    
    def analyze_layout(self, document: DocumentStructure) -> List[LayoutAnalysis]:
        """Analyze the layout of a document.
        
        Args:
            document: Document structure to analyze
            
        Returns:
            List of LayoutAnalysis objects, one per page
        """
        analyses = []
        
        for page in document.pages:
            analysis = self._analyze_page_layout(page)
            analyses.append(analysis)
        
        return analyses
    
    def _analyze_page_layout(self, page: PageStructure) -> LayoutAnalysis:
        """Analyze the layout of a single page."""
        # Extract text regions and visual elements
        text_regions = self.extract_text_regions(page)
        visual_elements = self.detect_visual_elements(page)
        
        # Calculate spatial relationships
        all_elements = text_regions + visual_elements
        spatial_relationships = self._calculate_spatial_relationships(all_elements)
        
        # Determine reading order
        reading_order = self._determine_reading_order(text_regions)
        
        # Detect column structure
        column_structure = self._detect_column_structure(text_regions)
        
        # Calculate layout complexity
        layout_complexity = self._calculate_layout_complexity(
            text_regions, visual_elements, spatial_relationships
        )
        
        return LayoutAnalysis(
            page_number=page.page_number,
            text_regions=text_regions,
            visual_elements=visual_elements,
            spatial_relationships=spatial_relationships,
            reading_order=reading_order,
            column_structure=column_structure,
            layout_complexity=layout_complexity
        )
    
    def extract_text_regions(self, page: PageStructure) -> List[TextRegion]:
        """Extract text regions from a page with enhanced bounding box analysis.
        
        Args:
            page: Page structure to analyze
            
        Returns:
            List of identified text regions with precise bounding boxes
        """
        # Start with existing text regions from the page
        text_regions = page.text_regions.copy()
        
        # Enhance bounding box precision
        for region in text_regions:
            region.bounding_box = self._refine_bounding_box(region)
        
        # Merge adjacent text regions if they belong together
        merged_regions = self._merge_adjacent_text_regions(text_regions)
        
        # Sort by reading order
        merged_regions.sort(key=lambda r: (r.bounding_box.y, r.bounding_box.x))
        
        # Update reading order
        for i, region in enumerate(merged_regions):
            region.reading_order = i
        
        return merged_regions
    
    def detect_visual_elements(self, page: PageStructure) -> List[VisualElement]:
        """Detect and classify visual elements in a page.
        
        Args:
            page: Page structure to analyze
            
        Returns:
            List of detected and classified visual elements
        """
        visual_elements = page.visual_elements.copy()
        
        # Enhance element classification
        for element in visual_elements:
            element = self._classify_visual_element(element)
        
        # Detect additional elements that might have been missed
        additional_elements = self._detect_additional_visual_elements(page)
        visual_elements.extend(additional_elements)
        
        return visual_elements
    
    def calculate_spatial_relationships(self, elements: List) -> SpatialMap:
        """Calculate spatial relationships between elements.
        
        Args:
            elements: List of page elements (TextRegion and VisualElement)
            
        Returns:
            SpatialMap containing element relationships
        """
        return self._calculate_spatial_relationships(elements)
    
    def _calculate_spatial_relationships(self, elements: List) -> List[SpatialRelationship]:
        """Calculate detailed spatial relationships between elements."""
        relationships = []
        
        for i, elem1 in enumerate(elements):
            for j, elem2 in enumerate(elements):
                if i >= j:  # Avoid duplicate relationships
                    continue
                
                relationship = self._determine_spatial_relationship(elem1, elem2)
                if relationship:
                    relationships.append(relationship)
        
        return relationships
    
    def _determine_spatial_relationship(self, elem1, elem2) -> SpatialRelationship:
        """Determine the spatial relationship between two elements."""
        box1 = elem1.bounding_box
        box2 = elem2.bounding_box
        
        # Check for overlap
        if box1.overlaps_with(box2):
            return SpatialRelationship(
                element1_id=elem1.id,
                element2_id=elem2.id,
                relationship_type="overlaps",
                distance=0.0,
                confidence=0.9
            )
        
        # Calculate centers
        center1_x = box1.x + box1.width / 2
        center1_y = box1.y + box1.height / 2
        center2_x = box2.x + box2.width / 2
        center2_y = box2.y + box2.height / 2
        
        # Calculate distance
        distance = math.sqrt((center2_x - center1_x)**2 + (center2_y - center1_y)**2)
        
        # Determine relationship type based on relative positions
        dx = center2_x - center1_x
        dy = center2_y - center1_y
        
        # Use thresholds to determine primary relationship
        if abs(dx) > abs(dy):
            # Horizontal relationship
            if dx > 0:
                relationship_type = "right"
            else:
                relationship_type = "left"
        else:
            # Vertical relationship
            if dy > 0:
                relationship_type = "below"
            else:
                relationship_type = "above"
        
        # Check if elements are adjacent (close enough)
        if distance <= self.proximity_threshold:
            relationship_type = "adjacent"
        
        confidence = max(0.1, 1.0 - (distance / 1000.0))  # Confidence decreases with distance
        
        return SpatialRelationship(
            element1_id=elem1.id,
            element2_id=elem2.id,
            relationship_type=relationship_type,
            distance=distance,
            confidence=min(1.0, confidence)
        )
    
    def _refine_bounding_box(self, region: TextRegion) -> BoundingBox:
        """Refine bounding box precision for a text region."""
        # For now, return the existing bounding box
        # In a real implementation, this could use OCR or text analysis
        # to get more precise boundaries
        return region.bounding_box
    
    def _merge_adjacent_text_regions(self, regions: List[TextRegion]) -> List[TextRegion]:
        """Merge text regions that should be combined."""
        if not regions:
            return regions
        
        merged = []
        current_group = [regions[0]]
        
        for i in range(1, len(regions)):
            current_region = regions[i]
            last_in_group = current_group[-1]
            
            # Check if regions should be merged (same line, close proximity)
            if self._should_merge_regions(last_in_group, current_region):
                current_group.append(current_region)
            else:
                # Merge current group and start new group
                merged_region = self._merge_region_group(current_group)
                merged.append(merged_region)
                current_group = [current_region]
        
        # Don't forget the last group
        if current_group:
            merged_region = self._merge_region_group(current_group)
            merged.append(merged_region)
        
        return merged
    
    def _should_merge_regions(self, region1: TextRegion, region2: TextRegion) -> bool:
        """Determine if two text regions should be merged."""
        box1, box2 = region1.bounding_box, region2.bounding_box
        
        # Check if they're on the same line (similar y coordinates)
        y_overlap = abs(box1.y - box2.y) < min(box1.height, box2.height) * 0.5
        
        # Check if they're close horizontally
        horizontal_gap = abs((box1.x + box1.width) - box2.x)
        close_horizontally = horizontal_gap < 20  # 20 units threshold
        
        # Check if they have similar formatting
        similar_formatting = (
            region1.formatting.font_family == region2.formatting.font_family and
            abs(region1.formatting.font_size - region2.formatting.font_size) < 2
        )
        
        return y_overlap and close_horizontally and similar_formatting
    
    def _merge_region_group(self, regions: List[TextRegion]) -> TextRegion:
        """Merge a group of text regions into one."""
        if len(regions) == 1:
            return regions[0]
        
        # Calculate combined bounding box
        min_x = min(r.bounding_box.x for r in regions)
        min_y = min(r.bounding_box.y for r in regions)
        max_x = max(r.bounding_box.x + r.bounding_box.width for r in regions)
        max_y = max(r.bounding_box.y + r.bounding_box.height for r in regions)
        
        combined_box = BoundingBox(
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y
        )
        
        # Combine text content
        combined_text = " ".join(r.text_content for r in regions)
        
        # Use formatting from the first region
        base_region = regions[0]
        
        # Calculate average confidence
        avg_confidence = sum(r.confidence for r in regions) / len(regions)
        
        return TextRegion(
            bounding_box=combined_box,
            text_content=combined_text,
            formatting=base_region.formatting,
            language=base_region.language,
            confidence=avg_confidence,
            reading_order=base_region.reading_order
        )
    
    def _classify_visual_element(self, element: VisualElement) -> VisualElement:
        """Enhance classification of a visual element."""
        # Basic classification based on size and aspect ratio
        box = element.bounding_box
        aspect_ratio = box.width / box.height if box.height > 0 else 1.0
        area = box.area()
        
        # Update metadata with analysis
        element.metadata.update({
            'aspect_ratio': aspect_ratio,
            'area': area,
            'analysis_confidence': 0.8
        })
        
        # Refine element type based on characteristics
        if aspect_ratio > 3.0 and box.height < 5:
            element.element_type = "line"
        elif aspect_ratio > 2.0 and area > 10000:
            element.element_type = "chart"
        elif 0.5 <= aspect_ratio <= 2.0 and area > 5000:
            element.element_type = "image"
        
        return element
    
    def _detect_additional_visual_elements(self, page: PageStructure) -> List[VisualElement]:
        """Detect additional visual elements that might have been missed."""
        # This is a placeholder for more sophisticated detection
        # In a real implementation, this could analyze gaps in text regions
        # to find potential visual elements
        return []
    
    def _determine_reading_order(self, text_regions: List[TextRegion]) -> List[str]:
        """Determine the reading order of text regions."""
        # Sort by vertical position first, then horizontal
        sorted_regions = sorted(
            text_regions,
            key=lambda r: (r.bounding_box.y, r.bounding_box.x)
        )
        
        return [region.id for region in sorted_regions]
    
    def _detect_column_structure(self, text_regions: List[TextRegion]) -> List[List[str]]:
        """Detect column structure in the text regions."""
        if not text_regions:
            return []
        
        # Group regions by approximate x-coordinate (column detection)
        columns = defaultdict(list)
        
        for region in text_regions:
            # Round x-coordinate to nearest column boundary
            column_key = round(region.bounding_box.x / 100) * 100
            columns[column_key].append(region.id)
        
        # Sort columns by x-coordinate and return as list
        sorted_columns = sorted(columns.items())
        return [region_ids for _, region_ids in sorted_columns]
    
    def _calculate_layout_complexity(
        self, 
        text_regions: List[TextRegion], 
        visual_elements: List[VisualElement],
        spatial_relationships: List[SpatialRelationship]
    ) -> float:
        """Calculate layout complexity score."""
        # Base complexity factors
        text_count = len(text_regions)
        visual_count = len(visual_elements)
        relationship_count = len(spatial_relationships)
        
        # Calculate complexity based on various factors
        element_complexity = min(1.0, (text_count + visual_count) / 50.0)
        relationship_complexity = min(1.0, relationship_count / 100.0)
        
        # Check for overlapping elements (increases complexity)
        overlap_count = sum(
            1 for rel in spatial_relationships 
            if rel.relationship_type == "overlaps"
        )
        overlap_complexity = min(1.0, overlap_count / 10.0)
        
        # Combine factors
        total_complexity = (
            element_complexity * 0.4 +
            relationship_complexity * 0.3 +
            overlap_complexity * 0.3
        )
        
        return min(1.0, total_complexity)
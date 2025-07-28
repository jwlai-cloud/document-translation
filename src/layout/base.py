"""Base classes for layout analysis and reconstruction."""

from abc import ABC, abstractmethod
from typing import List
from src.models.document import DocumentStructure, PageStructure
from src.models.layout import LayoutAnalysis, TextRegion, VisualElement, SpatialMap


class LayoutAnalysisEngine(ABC):
    """Abstract base class for layout analysis engines."""
    
    @abstractmethod
    def analyze_layout(self, document: DocumentStructure) -> LayoutAnalysis:
        """Analyze the layout of a document.
        
        Args:
            document: Document structure to analyze
            
        Returns:
            LayoutAnalysis containing spatial relationships and elements
        """
        pass
    
    @abstractmethod
    def extract_text_regions(self, page: PageStructure) -> List[TextRegion]:
        """Extract text regions from a page.
        
        Args:
            page: Page structure to analyze
            
        Returns:
            List of identified text regions
        """
        pass
    
    @abstractmethod
    def detect_visual_elements(self, page: PageStructure) -> List[VisualElement]:
        """Detect visual elements in a page.
        
        Args:
            page: Page structure to analyze
            
        Returns:
            List of detected visual elements
        """
        pass
    
    @abstractmethod
    def calculate_spatial_relationships(self, elements: List) -> SpatialMap:
        """Calculate spatial relationships between elements.
        
        Args:
            elements: List of page elements
            
        Returns:
            SpatialMap containing element relationships
        """
        pass


class LayoutReconstructionEngine(ABC):
    """Abstract base class for layout reconstruction engines."""
    
    @abstractmethod
    def fit_translated_text(self, region: TextRegion, translated: str):
        """Fit translated text into a text region.
        
        Args:
            region: Original text region
            translated: Translated text content
            
        Returns:
            AdjustedRegion with fitted text and layout adjustments
        """
        pass
    
    @abstractmethod
    def adjust_layout(self, page: PageStructure, adjustments: List):
        """Adjust page layout based on text changes.
        
        Args:
            page: Original page structure
            adjustments: List of layout adjustments
            
        Returns:
            Adjusted PageStructure
        """
        pass
    
    @abstractmethod
    def resolve_conflicts(self, conflicts: List):
        """Resolve layout conflicts between elements.
        
        Args:
            conflicts: List of layout conflicts
            
        Returns:
            List of conflict resolutions
        """
        pass
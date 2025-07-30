"""Preview service for side-by-side document comparison."""

import base64
import io
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid

from src.models.document import DocumentStructure, PageStructure, TextRegion, VisualElement, BoundingBox
from src.models.layout import AdjustedRegion


class PreviewFormat(Enum):
    """Supported preview formats."""
    HTML = "html"
    SVG = "svg"
    IMAGE = "image"


class HighlightType(Enum):
    """Types of highlighting for text regions."""
    ORIGINAL = "original"
    TRANSLATED = "translated"
    CHANGED = "changed"
    SELECTED = "selected"
    HOVER = "hover"


@dataclass
class PreviewRegion:
    """Represents a region in the preview with highlighting information."""
    region_id: str
    bounding_box: BoundingBox
    original_text: str
    translated_text: Optional[str] = None
    highlight_type: HighlightType = HighlightType.ORIGINAL
    confidence_score: float = 1.0
    is_visible: bool = True
    z_index: int = 1
    
    @property
    def display_text(self) -> str:
        """Get the text to display based on highlight type."""
        if self.highlight_type == HighlightType.TRANSLATED and self.translated_text:
            return self.translated_text
        return self.original_text


@dataclass
class PreviewPage:
    """Represents a page in the preview."""
    page_number: int
    width: float
    height: float
    original_regions: List[PreviewRegion]
    translated_regions: List[PreviewRegion]
    visual_elements: List[VisualElement]
    zoom_level: float = 1.0
    scroll_x: float = 0.0
    scroll_y: float = 0.0


@dataclass
class PreviewConfig:
    """Configuration for preview generation."""
    format: PreviewFormat = PreviewFormat.HTML
    show_original: bool = True
    show_translated: bool = True
    side_by_side: bool = True
    highlight_changes: bool = True
    show_confidence_scores: bool = False
    enable_zoom: bool = True
    enable_scroll: bool = True
    max_zoom: float = 5.0
    min_zoom: float = 0.1
    default_zoom: float = 1.0


@dataclass
class PreviewDocument:
    """Complete preview document with all pages and metadata."""
    document_id: str
    title: str
    pages: List[PreviewPage]
    config: PreviewConfig
    total_regions: int = 0
    translated_regions: int = 0
    
    @property
    def translation_progress(self) -> float:
        """Calculate translation progress as percentage."""
        if self.total_regions == 0:
            return 0.0
        return (self.translated_regions / self.total_regions) * 100.0


class PreviewRenderer:
    """Base class for preview renderers."""
    
    def __init__(self, config: PreviewConfig):
        """Initialize renderer with configuration."""
        self.config = config
    
    def render_page(self, page: PreviewPage) -> str:
        """Render a single page to the target format."""
        raise NotImplementedError
    
    def render_document(self, document: PreviewDocument) -> str:
        """Render complete document to the target format."""
        raise NotImplementedError


class HTMLPreviewRenderer(PreviewRenderer):
    """HTML renderer for document previews."""
    
    def __init__(self, config: PreviewConfig):
        """Initialize HTML renderer."""
        super().__init__(config)
        self.css_styles = self._generate_css_styles()
        self.javascript = self._generate_javascript()
    
    def render_document(self, document: PreviewDocument) -> str:
        """Render complete document as HTML."""
        html_parts = []
        
        # HTML header
        html_parts.append(self._generate_html_header(document))
        
        # Document container
        html_parts.append('<div class="preview-container">')
        
        # Navigation bar
        html_parts.append(self._generate_navigation_bar(document))
        
        # Main content area
        if self.config.side_by_side:
            html_parts.append('<div class="side-by-side-container">')
            html_parts.append('<div class="original-panel">')
            html_parts.append('<h3>Original Document</h3>')
            for page in document.pages:
                html_parts.append(self._render_page_panel(page, "original"))
            html_parts.append('</div>')
            
            html_parts.append('<div class="translated-panel">')
            html_parts.append('<h3>Translated Document</h3>')
            for page in document.pages:
                html_parts.append(self._render_page_panel(page, "translated"))
            html_parts.append('</div>')
            html_parts.append('</div>')
        else:
            # Single panel with toggle
            html_parts.append('<div class="single-panel-container">')
            for page in document.pages:
                html_parts.append(self.render_page(page))
            html_parts.append('</div>')
        
        # Controls panel
        html_parts.append(self._generate_controls_panel(document))
        
        html_parts.append('</div>')  # Close preview-container
        
        # JavaScript
        html_parts.append(f'<script>{self.javascript}</script>')
        
        # HTML footer
        html_parts.append('</body></html>')
        
        return '\n'.join(html_parts)
    
    def render_page(self, page: PreviewPage) -> str:
        """Render a single page as HTML."""
        return self._render_page_panel(page, "combined")
    
    def _generate_html_header(self, document: PreviewDocument) -> str:
        """Generate HTML header with styles."""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Preview: {document.title}</title>
    <style>{self.css_styles}</style>
</head>
<body>'''
    
    def _generate_navigation_bar(self, document: PreviewDocument) -> str:
        """Generate navigation bar."""
        nav_html = ['<div class="navigation-bar">']
        nav_html.append(f'<h2>{document.title}</h2>')
        nav_html.append('<div class="nav-info">')
        nav_html.append(f'<span>Pages: {len(document.pages)}</span>')
        nav_html.append(f'<span>Progress: {document.translation_progress:.1f}%</span>')
        nav_html.append('</div>')
        nav_html.append('</div>')
        return '\n'.join(nav_html)
    
    def _render_page_panel(self, page: PreviewPage, panel_type: str) -> str:
        """Render a page panel (original, translated, or combined)."""
        panel_html = []
        
        panel_html.append(f'<div class="page-panel page-{page.page_number}" data-page="{page.page_number}">')
        panel_html.append(f'<div class="page-header">Page {page.page_number}</div>')
        
        # SVG container for the page
        panel_html.append(f'''<div class="page-container" style="transform: scale({page.zoom_level});">
            <svg width="{page.width}" height="{page.height}" class="page-svg">''')
        
        # Render visual elements (background)
        for element in page.visual_elements:
            panel_html.append(self._render_visual_element(element))
        
        # Render text regions based on panel type
        if panel_type == "original" or panel_type == "combined":
            for region in page.original_regions:
                if region.is_visible:
                    panel_html.append(self._render_text_region(region, "original"))
        
        if panel_type == "translated" or panel_type == "combined":
            for region in page.translated_regions:
                if region.is_visible:
                    panel_html.append(self._render_text_region(region, "translated"))
        
        panel_html.append('</svg>')
        panel_html.append('</div>')  # Close page-container
        panel_html.append('</div>')  # Close page-panel
        
        return '\n'.join(panel_html)    
   
 def _render_text_region(self, region: PreviewRegion, region_type: str) -> str:
        """Render a text region as SVG elements."""
        box = region.bounding_box
        
        # Determine CSS classes based on highlight type and region type
        css_classes = [f"text-region", f"region-{region_type}", f"highlight-{region.highlight_type.value}"]
        
        if self.config.show_confidence_scores and region.confidence_score < 0.8:
            css_classes.append("low-confidence")
        
        # Create SVG group for the region
        svg_elements = []
        
        # Background rectangle
        svg_elements.append(f'''<rect x="{box.x}" y="{box.y}" width="{box.width}" height="{box.height}"
            class="{' '.join(css_classes)}" 
            data-region-id="{region.region_id}"
            data-confidence="{region.confidence_score:.2f}">
        </rect>''')
        
        # Text content
        text_y = box.y + box.height * 0.7  # Position text vertically centered
        svg_elements.append(f'''<text x="{box.x + 5}" y="{text_y}" 
            class="region-text {' '.join(css_classes)}"
            data-region-id="{region.region_id}">
            {self._escape_html(region.display_text)}
        </text>''')
        
        # Confidence indicator if enabled
        if self.config.show_confidence_scores:
            confidence_color = self._get_confidence_color(region.confidence_score)
            svg_elements.append(f'''<circle cx="{box.x + box.width - 10}" cy="{box.y + 10}" r="5"
                fill="{confidence_color}" class="confidence-indicator"
                title="Confidence: {region.confidence_score:.2f}">
            </circle>''')
        
        return '\n'.join(svg_elements)
    
    def _render_visual_element(self, element: VisualElement) -> str:
        """Render a visual element as SVG."""
        box = element.bounding_box
        
        if element.element_type == "image":
            # Placeholder for image
            return f'''<rect x="{box.x}" y="{box.y}" width="{box.width}" height="{box.height}"
                class="visual-element image-placeholder" fill="#f0f0f0" stroke="#ccc">
            </rect>
            <text x="{box.x + box.width/2}" y="{box.y + box.height/2}" 
                text-anchor="middle" class="placeholder-text">Image</text>'''
        
        elif element.element_type == "chart":
            return f'''<rect x="{box.x}" y="{box.y}" width="{box.width}" height="{box.height}"
                class="visual-element chart-placeholder" fill="#e8f4f8" stroke="#4a90e2">
            </rect>
            <text x="{box.x + box.width/2}" y="{box.y + box.height/2}" 
                text-anchor="middle" class="placeholder-text">Chart</text>'''
        
        elif element.element_type == "table":
            return f'''<rect x="{box.x}" y="{box.y}" width="{box.width}" height="{box.height}"
                class="visual-element table-placeholder" fill="#f8f8e8" stroke="#d4a574">
            </rect>
            <text x="{box.x + box.width/2}" y="{box.y + box.height/2}" 
                text-anchor="middle" class="placeholder-text">Table</text>'''
        
        else:
            # Generic visual element
            return f'''<rect x="{box.x}" y="{box.y}" width="{box.width}" height="{box.height}"
                class="visual-element generic-placeholder" fill="#f5f5f5" stroke="#999">
            </rect>'''
    
    def _generate_controls_panel(self, document: PreviewDocument) -> str:
        """Generate controls panel for zoom, scroll, and highlighting."""
        controls_html = ['<div class="controls-panel">']
        
        # Zoom controls
        if self.config.enable_zoom:
            controls_html.append('<div class="zoom-controls">')
            controls_html.append('<label>Zoom:</label>')
            controls_html.append(f'<input type="range" id="zoom-slider" min="{self.config.min_zoom}" max="{self.config.max_zoom}" step="0.1" value="{self.config.default_zoom}">')
            controls_html.append('<button id="zoom-fit">Fit</button>')
            controls_html.append('<button id="zoom-reset">Reset</button>')
            controls_html.append('</div>')
        
        # Highlight controls
        controls_html.append('<div class="highlight-controls">')
        controls_html.append('<label>Highlight:</label>')
        controls_html.append('<button id="highlight-original" class="active">Original</button>')
        controls_html.append('<button id="highlight-translated">Translated</button>')
        controls_html.append('<button id="highlight-changes">Changes</button>')
        controls_html.append('</div>')
        
        # View controls
        controls_html.append('<div class="view-controls">')
        controls_html.append('<label>View:</label>')
        controls_html.append('<button id="view-side-by-side" class="active">Side by Side</button>')
        controls_html.append('<button id="view-overlay">Overlay</button>')
        controls_html.append('</div>')
        
        # Progress indicator
        controls_html.append('<div class="progress-indicator">')
        controls_html.append(f'<div class="progress-bar" style="width: {document.translation_progress}%"></div>')
        controls_html.append(f'<span class="progress-text">{document.translation_progress:.1f}% Translated</span>')
        controls_html.append('</div>')
        
        controls_html.append('</div>')
        return '\n'.join(controls_html) 
   
    def _generate_css_styles(self) -> str:
        """Generate CSS styles for the preview."""
        return '''
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }
        
        .preview-container {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        
        .navigation-bar {
            background-color: #2c3e50;
            color: white;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .nav-info span {
            margin-left: 20px;
        }
        
        .side-by-side-container {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        
        .original-panel, .translated-panel {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            border-right: 1px solid #ddd;
        }
        
        .translated-panel {
            border-right: none;
        }
        
        .single-panel-container {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }
        
        .page-panel {
            margin-bottom: 30px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .page-header {
            background-color: #34495e;
            color: white;
            padding: 10px 15px;
            font-weight: bold;
        }
        
        .page-container {
            padding: 20px;
            overflow: auto;
            transform-origin: top left;
        }
        
        .page-svg {
            border: 1px solid #ddd;
            background: white;
        }
        
        .text-region {
            fill: rgba(52, 152, 219, 0.1);
            stroke: #3498db;
            stroke-width: 1;
            cursor: pointer;
        }
        
        .text-region:hover {
            fill: rgba(52, 152, 219, 0.2);
            stroke-width: 2;
        }
        
        .highlight-original {
            fill: rgba(46, 204, 113, 0.1);
            stroke: #2ecc71;
        }
        
        .highlight-translated {
            fill: rgba(155, 89, 182, 0.1);
            stroke: #9b59b6;
        }
        
        .highlight-changed {
            fill: rgba(231, 76, 60, 0.1);
            stroke: #e74c3c;
        }
        
        .highlight-selected {
            fill: rgba(241, 196, 15, 0.2);
            stroke: #f1c40f;
            stroke-width: 3;
        }
        
        .region-text {
            font-size: 12px;
            fill: #2c3e50;
            pointer-events: none;
        }
        
        .low-confidence {
            stroke-dasharray: 5,5;
        }
        
        .confidence-indicator {
            stroke: white;
            stroke-width: 1;
        }
        
        .visual-element {
            stroke-width: 1;
        }
        
        .placeholder-text {
            font-size: 14px;
            fill: #7f8c8d;
            font-style: italic;
        }
        
        .controls-panel {
            background-color: #ecf0f1;
            padding: 15px 20px;
            border-top: 1px solid #bdc3c7;
            display: flex;
            gap: 30px;
            align-items: center;
        }
        
        .zoom-controls, .highlight-controls, .view-controls {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .controls-panel button {
            padding: 5px 12px;
            border: 1px solid #bdc3c7;
            background: white;
            border-radius: 4px;
            cursor: pointer;
        }
        
        .controls-panel button.active {
            background-color: #3498db;
            color: white;
        }
        
        .controls-panel button:hover {
            background-color: #ecf0f1;
        }
        
        .controls-panel button.active:hover {
            background-color: #2980b9;
        }
        
        .progress-indicator {
            margin-left: auto;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .progress-bar {
            height: 20px;
            background-color: #2ecc71;
            border-radius: 10px;
            min-width: 100px;
            position: relative;
        }
        
        .progress-text {
            font-size: 12px;
            color: #7f8c8d;
        }
        '''    

    def _generate_javascript(self) -> str:
        """Generate JavaScript for interactive features."""
        return '''
        document.addEventListener('DOMContentLoaded', function() {
            // Zoom functionality
            const zoomSlider = document.getElementById('zoom-slider');
            const zoomFitBtn = document.getElementById('zoom-fit');
            const zoomResetBtn = document.getElementById('zoom-reset');
            
            if (zoomSlider) {
                zoomSlider.addEventListener('input', function() {
                    const zoomLevel = parseFloat(this.value);
                    applyZoom(zoomLevel);
                });
            }
            
            if (zoomFitBtn) {
                zoomFitBtn.addEventListener('click', function() {
                    fitToWindow();
                });
            }
            
            if (zoomResetBtn) {
                zoomResetBtn.addEventListener('click', function() {
                    applyZoom(1.0);
                    if (zoomSlider) zoomSlider.value = 1.0;
                });
            }
            
            // Highlight controls
            const highlightBtns = document.querySelectorAll('.highlight-controls button');
            highlightBtns.forEach(btn => {
                btn.addEventListener('click', function() {
                    highlightBtns.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    
                    const highlightType = this.id.replace('highlight-', '');
                    applyHighlight(highlightType);
                });
            });
            
            // View controls
            const viewBtns = document.querySelectorAll('.view-controls button');
            viewBtns.forEach(btn => {
                btn.addEventListener('click', function() {
                    viewBtns.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    
                    const viewType = this.id.replace('view-', '');
                    applyView(viewType);
                });
            });
            
            // Text region interactions
            const textRegions = document.querySelectorAll('.text-region');
            textRegions.forEach(region => {
                region.addEventListener('click', function() {
                    selectRegion(this);
                });
                
                region.addEventListener('mouseenter', function() {
                    showRegionTooltip(this);
                });
                
                region.addEventListener('mouseleave', function() {
                    hideRegionTooltip();
                });
            });
            
            function applyZoom(zoomLevel) {
                const pageContainers = document.querySelectorAll('.page-container');
                pageContainers.forEach(container => {
                    container.style.transform = `scale(${zoomLevel})`;
                });
            }
            
            function fitToWindow() {
                const pageContainer = document.querySelector('.page-container');
                const pageSvg = document.querySelector('.page-svg');
                
                if (pageContainer && pageSvg) {
                    const containerWidth = pageContainer.parentElement.clientWidth - 40;
                    const svgWidth = pageSvg.getAttribute('width');
                    const zoomLevel = containerWidth / svgWidth;
                    
                    applyZoom(zoomLevel);
                    if (zoomSlider) zoomSlider.value = zoomLevel;
                }
            }
            
            function applyHighlight(type) {
                const regions = document.querySelectorAll('.text-region');
                regions.forEach(region => {
                    region.classList.remove('highlight-original', 'highlight-translated', 'highlight-changes');
                    region.classList.add(`highlight-${type}`);
                });
            }
            
            function applyView(type) {
                const sideBySideContainer = document.querySelector('.side-by-side-container');
                const singlePanelContainer = document.querySelector('.single-panel-container');
                
                if (type === 'side-by-side') {
                    if (sideBySideContainer) sideBySideContainer.style.display = 'flex';
                    if (singlePanelContainer) singlePanelContainer.style.display = 'none';
                } else if (type === 'overlay') {
                    if (sideBySideContainer) sideBySideContainer.style.display = 'none';
                    if (singlePanelContainer) singlePanelContainer.style.display = 'block';
                }
            }
            
            function selectRegion(regionElement) {
                // Remove previous selection
                document.querySelectorAll('.text-region').forEach(r => {
                    r.classList.remove('highlight-selected');
                });
                
                // Add selection to clicked region
                regionElement.classList.add('highlight-selected');
                
                // Show region details
                const regionId = regionElement.getAttribute('data-region-id');
                const confidence = regionElement.getAttribute('data-confidence');
                console.log(`Selected region: ${regionId}, Confidence: ${confidence}`);
            }
            
            function showRegionTooltip(regionElement) {
                const regionId = regionElement.getAttribute('data-region-id');
                const confidence = regionElement.getAttribute('data-confidence');
                
                // Create tooltip (simplified)
                const tooltip = document.createElement('div');
                tooltip.id = 'region-tooltip';
                tooltip.innerHTML = `Region: ${regionId}<br>Confidence: ${confidence}`;
                tooltip.style.cssText = `
                    position: absolute;
                    background: rgba(0,0,0,0.8);
                    color: white;
                    padding: 5px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                    pointer-events: none;
                    z-index: 1000;
                `;
                
                document.body.appendChild(tooltip);
                
                // Position tooltip near mouse
                document.addEventListener('mousemove', positionTooltip);
            }
            
            function hideRegionTooltip() {
                const tooltip = document.getElementById('region-tooltip');
                if (tooltip) {
                    tooltip.remove();
                    document.removeEventListener('mousemove', positionTooltip);
                }
            }
            
            function positionTooltip(e) {
                const tooltip = document.getElementById('region-tooltip');
                if (tooltip) {
                    tooltip.style.left = (e.pageX + 10) + 'px';
                    tooltip.style.top = (e.pageY - 30) + 'px';
                }
            }
        });
        '''
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#x27;'))
    
    def _get_confidence_color(self, confidence: float) -> str:
        """Get color based on confidence score."""
        if confidence >= 0.9:
            return "#2ecc71"  # Green
        elif confidence >= 0.7:
            return "#f39c12"  # Orange
        else:
            return "#e74c3c"  # Red

class
 PreviewService:
    """Main service for generating document previews."""
    
    def __init__(self):
        """Initialize preview service."""
        self.renderers = {
            PreviewFormat.HTML: HTMLPreviewRenderer
        }
    
    def create_preview(self, original_document: DocumentStructure,
                      translated_regions: Optional[Dict[str, List[AdjustedRegion]]] = None,
                      config: Optional[PreviewConfig] = None) -> PreviewDocument:
        """Create a preview document from original and translated content.
        
        Args:
            original_document: Original document structure
            translated_regions: Dictionary mapping page numbers to translated regions
            config: Preview configuration
            
        Returns:
            PreviewDocument ready for rendering
        """
        if config is None:
            config = PreviewConfig()
        
        if translated_regions is None:
            translated_regions = {}
        
        preview_pages = []
        total_regions = 0
        translated_count = 0
        
        for page in original_document.pages:
            page_key = str(page.page_number)
            page_translated_regions = translated_regions.get(page_key, [])
            
            # Convert to preview regions
            original_preview_regions = []
            for region in page.text_regions:
                preview_region = PreviewRegion(
                    region_id=region.id,
                    bounding_box=region.bounding_box,
                    original_text=region.text_content,
                    highlight_type=HighlightType.ORIGINAL,
                    confidence_score=region.confidence
                )
                original_preview_regions.append(preview_region)
                total_regions += 1
            
            # Convert translated regions
            translated_preview_regions = []
            for adj_region in page_translated_regions:
                preview_region = PreviewRegion(
                    region_id=adj_region.original_region.id,
                    bounding_box=adj_region.new_bounding_box,
                    original_text=adj_region.original_region.text_content,
                    translated_text=adj_region.adjusted_text,
                    highlight_type=HighlightType.TRANSLATED,
                    confidence_score=adj_region.fit_quality
                )
                translated_preview_regions.append(preview_region)
                translated_count += 1
            
            # Create preview page
            preview_page = PreviewPage(
                page_number=page.page_number,
                width=page.dimensions.width,
                height=page.dimensions.height,
                original_regions=original_preview_regions,
                translated_regions=translated_preview_regions,
                visual_elements=page.visual_elements,
                zoom_level=config.default_zoom
            )
            preview_pages.append(preview_page)
        
        # Create preview document
        preview_document = PreviewDocument(
            document_id=str(uuid.uuid4()),
            title=original_document.metadata.title or "Untitled Document",
            pages=preview_pages,
            config=config,
            total_regions=total_regions,
            translated_regions=translated_count
        )
        
        return preview_document
    
    def render_preview(self, preview_document: PreviewDocument) -> str:
        """Render preview document to specified format.
        
        Args:
            preview_document: Preview document to render
            
        Returns:
            Rendered preview as string
        """
        renderer_class = self.renderers.get(preview_document.config.format)
        if not renderer_class:
            raise ValueError(f"Unsupported preview format: {preview_document.config.format}")
        
        renderer = renderer_class(preview_document.config)
        return renderer.render_document(preview_document)
    
    def update_highlighting(self, preview_document: PreviewDocument,
                          highlight_type: HighlightType,
                          region_ids: Optional[List[str]] = None) -> PreviewDocument:
        """Update highlighting for specific regions or all regions.
        
        Args:
            preview_document: Preview document to update
            highlight_type: Type of highlighting to apply
            region_ids: Specific region IDs to update (None for all)
            
        Returns:
            Updated preview document
        """
        for page in preview_document.pages:
            # Update original regions
            for region in page.original_regions:
                if region_ids is None or region.region_id in region_ids:
                    region.highlight_type = highlight_type
            
            # Update translated regions
            for region in page.translated_regions:
                if region_ids is None or region.region_id in region_i
ds:
                    region.highlight_type = highlight_type
        
        return preview_document
    
    def set_zoom_level(self, preview_document: PreviewDocument,
                      zoom_level: float, page_number: Optional[int] = None) -> PreviewDocument:
        """Set zoom level for specific page or all pages.
        
        Args:
            preview_document: Preview document to update
            zoom_level: New zoom level
            page_number: Specific page number (None for all pages)
            
        Returns:
            Updated preview document
        """
        # Clamp zoom level to configured limits
        zoom_level = max(preview_document.config.min_zoom,
                        min(preview_document.config.max_zoom, zoom_level))
        
        for page in preview_document.pages:
            if page_number is None or page.page_number == page_number:
                page.zoom_level = zoom_level
        
        return preview_document
    
    def set_scroll_position(self, preview_document: PreviewDocument,
                          scroll_x: float, scroll_y: float,
                          page_number: Optional[int] = None) -> PreviewDocument:
        """Set scroll position for specific page or all pages.
        
        Args:
            preview_document: Preview document to update
            scroll_x: Horizontal scroll position
            scroll_y: Vertical scroll position
            page_number: Specific page number (None for all pages)
            
        Returns:
            Updated preview document
        """
        for page in preview_document.pages:
            if page_number is None or page.page_number == page_number:
                page.scroll_x = scroll_x
                page.scroll_y = scroll_y
        
        return preview_document
    
    def get_region_info(self, preview_document: PreviewDocument,
                       region_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific region.
        
        Args:
            preview_document: Preview document
            region_id: Region ID to get info for
            
        Returns:
            Dictionary with region information or None if not found
        """
        for page in preview_document.pages:
            # Check original regions
            for region in page.original_regions:
                if region.region_id == region_id:
                    return {
                        'region_id': region.region_id,
                        'page_number': page.page_number,
                        'type': 'original',
                        'text': region.original_text,
                        'bounding_box': {
                            'x': region.bounding_box.x,
                            'y': region.bounding_box.y,
                            'width': region.bounding_box.width,
                            'height': region.bounding_box.height
                        },
                        'confidence': region.confidence_score,
                        'highlight_type': region.highlight_type.value
                    }
            
            # Check translated regions
            for region in page.translated_regions:
                if region.region_id == region_id:
                    return {
                        'region_id': region.region_id,
                        'page_number': page.page_number,
                        'type': 'translated',
                        'original_text': region.original_text,
                        'translated_text': region.translated_text,
                        'bounding_box': {
                            'x': region.bounding_box.x,
                            'y': region.bounding_box.y,
                            'width': region.bounding_box.width,
                            'height': region.bounding_box.height
                        },
                        'confidence': region.confidence_score,
                        'highlight_type': region.highlight_type.value
                    }
        
        return None
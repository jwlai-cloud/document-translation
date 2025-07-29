"""Example usage of EPUB parser."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parsers import get_parser_factory, EPUBParser
from models.document import DocumentStructure


def demonstrate_epub_parsing():
    """Demonstrate EPUB parsing functionality."""
    print("EPUB Parser Example")
    print("=" * 50)
    
    # Get the global parser factory
    factory = get_parser_factory()
    
    # Show supported formats
    print(f"Supported formats: {factory.get_supported_formats()}")
    
    # Check if EPUB is supported
    if factory.is_format_supported("epub"):
        print("✓ EPUB format is supported")
    else:
        print("✗ EPUB format is not supported")
        return
    
    # Create an EPUB parser
    epub_parser = factory.create_parser("epub")
    print(f"Created parser: {epub_parser.__class__.__name__}")
    print(f"Parser supports: {epub_parser.get_supported_formats()}")
    
    # Example of what would happen with a real EPUB file
    print("\nExample workflow:")
    print("1. Upload EPUB file")
    print("2. Validate file format and size")
    print("3. Parse EPUB structure:")
    print("   - Extract chapters as separate pages")
    print("   - Parse HTML content with BeautifulSoup")
    print("   - Extract text with CSS formatting")
    print("   - Extract embedded images and metadata")
    print("   - Build spatial relationships")
    print("   - Create document structure")
    print("4. Process for translation")
    print("5. Reconstruct translated EPUB")
    
    # Show what a parsed structure would look like
    print("\nExample parsed structure:")
    example_structure = DocumentStructure(format="epub")
    print(f"Format: {example_structure.format}")
    print(f"Pages: {len(example_structure.pages)} (each chapter = 1 page)")
    print(f"Metadata: {example_structure.metadata.title}")
    
    print("\nEPUB Parser Features:")
    features = [
        "✓ Chapter-based content extraction",
        "✓ HTML parsing with BeautifulSoup",
        "✓ CSS style interpretation and formatting",
        "✓ Semantic HTML element handling (h1-h6, p, div, etc.)",
        "✓ Image extraction with alt text and dimensions",
        "✓ Book metadata preservation (title, author, date)",
        "✓ Multi-chapter document reconstruction",
        "✓ XHTML generation with proper structure"
    ]
    
    for feature in features:
        print(f"  {feature}")


def show_epub_capabilities():
    """Show EPUB parser capabilities."""
    print("\nEPUB Parser Capabilities")
    print("=" * 30)
    
    capabilities = {
        "Content Extraction": [
            "Chapter-by-chapter processing",
            "HTML content parsing with BeautifulSoup",
            "Text extraction with HTML entity decoding",
            "Whitespace normalization and cleanup",
            "Semantic element recognition"
        ],
        "Formatting Support": [
            "CSS inline style parsing",
            "Font family, size, and color extraction",
            "Bold, italic, underline detection",
            "Text alignment handling",
            "Header hierarchy recognition (h1-h6)"
        ],
        "Visual Elements": [
            "Image extraction with metadata",
            "Alt text preservation",
            "Dimension handling (width/height)",
            "Source path tracking",
            "Approximate positioning"
        ],
        "Book Structure": [
            "Metadata extraction (title, author, date)",
            "Chapter organization",
            "Table of contents generation",
            "Navigation file creation",
            "Spine structure maintenance"
        ],
        "Reconstruction": [
            "XHTML chapter generation",
            "CSS style application",
            "Image reintegration",
            "Book metadata preservation",
            "EPUB package creation"
        ]
    }
    
    for category, items in capabilities.items():
        print(f"\n{category}:")
        for item in items:
            print(f"  • {item}")


def show_epub_format_characteristics():
    """Show EPUB format characteristics and parsing approach."""
    print("\nEPUB Format Characteristics")
    print("=" * 32)
    
    characteristics = {
        "File Structure": [
            "ZIP-based container format",
            "XHTML content files for chapters",
            "CSS stylesheets for formatting",
            "Images and media files",
            "Metadata and navigation files"
        ],
        "Content Model": [
            "Reflowable text content",
            "Chapter-based organization",
            "HTML/CSS-based formatting",
            "Semantic markup structure",
            "Responsive design principles"
        ],
        "Parsing Challenges": [
            "Variable HTML quality",
            "Inconsistent CSS usage",
            "Complex nested structures",
            "Multiple content files",
            "Format version differences"
        ],
        "Translation Considerations": [
            "Text reflow after translation",
            "Formatting preservation",
            "Image-text relationships",
            "Chapter boundary handling",
            "Metadata localization"
        ]
    }
    
    for category, items in characteristics.items():
        print(f"\n{category}:")
        for item in items:
            print(f"  • {item}")


def compare_document_formats():
    """Compare the three supported document formats."""
    print("\nDocument Format Comparison")
    print("=" * 30)
    
    comparison = {
        "Layout Model": {
            "PDF": "Fixed layout with precise positioning",
            "DOCX": "Flow-based with logical structure",
            "EPUB": "Reflowable with responsive design"
        },
        "Content Structure": {
            "PDF": "Page-based with visual elements",
            "DOCX": "Document flow with sections",
            "EPUB": "Chapter-based with HTML structure"
        },
        "Formatting Approach": {
            "PDF": "Embedded fonts and exact positioning",
            "DOCX": "Style-based with run formatting",
            "EPUB": "CSS-based with semantic markup"
        },
        "Translation Suitability": {
            "PDF": "Challenging due to fixed layout",
            "DOCX": "Good for content-based translation",
            "EPUB": "Excellent for reflowable content"
        },
        "Reconstruction Complexity": {
            "PDF": "High - requires precise positioning",
            "DOCX": "Medium - structure-based recreation",
            "EPUB": "Low - HTML/CSS generation"
        }
    }
    
    for aspect, formats in comparison.items():
        print(f"\n{aspect}:")
        for format_name, description in formats.items():
            print(f"  {format_name:4}: {description}")


if __name__ == "__main__":
    demonstrate_epub_parsing()
    show_epub_capabilities()
    show_epub_format_characteristics()
    compare_document_formats()
    
    print("\n" + "=" * 50)
    print("To use with a real EPUB file:")
    print("1. Ensure ebooklib is installed: pip install ebooklib")
    print("2. Ensure BeautifulSoup is installed: pip install beautifulsoup4")
    print("3. Use factory.parse_document('path/to/file.epub')")
    print("4. Process the returned DocumentStructure")
    print("5. Use factory.reconstruct_document(structure) to create new EPUB")
    print("\nNote: EPUB parsing excels at handling reflowable content")
    print("and is ideal for text-heavy documents with semantic structure.")
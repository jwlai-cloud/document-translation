"""Example usage of DOCX parser."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parsers import get_parser_factory, DOCXParser
from models.document import DocumentStructure


def demonstrate_docx_parsing():
    """Demonstrate DOCX parsing functionality."""
    print("DOCX Parser Example")
    print("=" * 50)
    
    # Get the global parser factory
    factory = get_parser_factory()
    
    # Show supported formats
    print(f"Supported formats: {factory.get_supported_formats()}")
    
    # Check if DOCX is supported
    if factory.is_format_supported("docx"):
        print("✓ DOCX format is supported")
    else:
        print("✗ DOCX format is not supported")
        return
    
    # Create a DOCX parser
    docx_parser = factory.create_parser("docx")
    print(f"Created parser: {docx_parser.__class__.__name__}")
    print(f"Parser supports: {docx_parser.get_supported_formats()}")
    
    # Example of what would happen with a real DOCX file
    print("\nExample workflow:")
    print("1. Upload DOCX file")
    print("2. Validate file format and size")
    print("3. Parse DOCX structure:")
    print("   - Extract paragraphs with run-level formatting")
    print("   - Extract tables with cell content")
    print("   - Extract embedded images and objects")
    print("   - Build spatial relationships")
    print("   - Create document structure")
    print("4. Process for translation")
    print("5. Reconstruct translated DOCX")
    
    # Show what a parsed structure would look like
    print("\nExample parsed structure:")
    example_structure = DocumentStructure(format="docx")
    print(f"Format: {example_structure.format}")
    print(f"Pages: {len(example_structure.pages)} (DOCX treated as single logical page)")
    print(f"Metadata: {example_structure.metadata.title}")
    
    print("\nDOCX Parser Features:")
    features = [
        "✓ Extract paragraphs with precise run-level formatting",
        "✓ Preserve font properties (family, size, style, color)",
        "✓ Handle tables with cell-by-cell content extraction",
        "✓ Extract embedded images and objects",
        "✓ Maintain document metadata (title, author, etc.)",
        "✓ Build spatial relationships between elements",
        "✓ Reconstruct DOCX with translated content",
        "✓ Preserve document structure and formatting"
    ]
    
    for feature in features:
        print(f"  {feature}")


def show_docx_capabilities():
    """Show DOCX parser capabilities."""
    print("\nDOCX Parser Capabilities")
    print("=" * 30)
    
    capabilities = {
        "Text Extraction": [
            "Paragraph-level content extraction",
            "Run-level formatting preservation",
            "Font family and size detection",
            "Bold, italic, underline detection",
            "Text color information",
            "Paragraph alignment handling"
        ],
        "Document Structure": [
            "Table extraction with cell content",
            "Header and footer handling",
            "Embedded object detection",
            "Image extraction with metadata",
            "Document metadata preservation"
        ],
        "Layout Analysis": [
            "Spatial relationship mapping",
            "Reading order determination",
            "Element positioning (approximate)",
            "Text flow analysis"
        ],
        "Reconstruction": [
            "Paragraph recreation with formatting",
            "Table reconstruction",
            "Image reintegration",
            "Metadata preservation",
            "Format-specific output generation"
        ]
    }
    
    for category, items in capabilities.items():
        print(f"\n{category}:")
        for item in items:
            print(f"  • {item}")


def show_docx_vs_pdf_differences():
    """Show differences between DOCX and PDF parsing."""
    print("\nDOCX vs PDF Parsing Differences")
    print("=" * 35)
    
    differences = {
        "Document Model": {
            "PDF": "Page-based with precise positioning",
            "DOCX": "Flow-based with logical structure"
        },
        "Text Extraction": {
            "PDF": "Character-level with exact coordinates",
            "DOCX": "Run-level with approximate positioning"
        },
        "Layout Handling": {
            "PDF": "Fixed layout with pixel precision",
            "DOCX": "Flexible layout with content flow"
        },
        "Visual Elements": {
            "PDF": "Embedded with exact positioning",
            "DOCX": "Inline or floating with relationships"
        },
        "Reconstruction": {
            "PDF": "Pixel-perfect recreation possible",
            "DOCX": "Structure-based recreation"
        }
    }
    
    for aspect, comparison in differences.items():
        print(f"\n{aspect}:")
        print(f"  PDF:  {comparison['PDF']}")
        print(f"  DOCX: {comparison['DOCX']}")


if __name__ == "__main__":
    demonstrate_docx_parsing()
    show_docx_capabilities()
    show_docx_vs_pdf_differences()
    
    print("\n" + "=" * 50)
    print("To use with a real DOCX file:")
    print("1. Ensure python-docx is installed: pip install python-docx")
    print("2. Use factory.parse_document('path/to/file.docx')")
    print("3. Process the returned DocumentStructure")
    print("4. Use factory.reconstruct_document(structure) to create new DOCX")
    print("\nNote: DOCX parsing focuses on content structure rather than")
    print("precise positioning, making it ideal for content-based translation.")
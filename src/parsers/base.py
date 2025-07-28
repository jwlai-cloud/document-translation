"""Base classes and interfaces for document parsers."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from src.models.document import DocumentStructure


class DocumentParser(ABC):
    """Abstract base class for document parsers."""

    @abstractmethod
    def parse(self, file_path: str) -> DocumentStructure:
        """Parse a document file and extract its structure.

        Args:
            file_path: Path to the document file

        Returns:
            DocumentStructure containing parsed content and layout
        """
        pass

    @abstractmethod
    def reconstruct(self, structure: DocumentStructure) -> bytes:
        """Reconstruct a document from its structure.

        Args:
            structure: DocumentStructure to reconstruct

        Returns:
            Binary content of the reconstructed document
        """
        pass

    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats.

        Returns:
            List of supported file extensions
        """
        pass


class DocumentParserFactory:
    """Factory for creating format-specific document parsers."""

    def __init__(self):
        self._parsers: Dict[str, type[DocumentParser]] = {}

    def register_parser(self, format_ext: str, parser_class: type[DocumentParser]):
        """Register a parser for a specific format.

        Args:
            format_ext: File extension (e.g., 'pdf', 'docx')
            parser_class: Parser class to handle this format
        """
        self._parsers[format_ext.lower()] = parser_class

    def create_parser(self, file_format: str) -> DocumentParser:
        """Create a parser for the specified format.

        Args:
            file_format: File extension or format identifier

        Returns:
            DocumentParser instance for the format

        Raises:
            ValueError: If format is not supported
        """
        format_key = file_format.lower().lstrip(".")
        if format_key not in self._parsers:
            raise ValueError(f"Unsupported format: {file_format}")

        parser_class = self._parsers[format_key]
        return parser_class()

    def get_supported_formats(self) -> list[str]:
        """Get all supported formats.

        Returns:
            List of supported file extensions
        """
        return list(self._parsers.keys())

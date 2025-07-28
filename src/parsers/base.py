"""Base classes and interfaces for document parsers."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union
from pathlib import Path
import logging

from src.models.document import DocumentStructure, DocumentMetadata
from src.models.validation import validate_file_format, validate_file_size


logger = logging.getLogger(__name__)


class ParsingError(Exception):
    """Exception raised during document parsing."""
    
    def __init__(self, message: str, file_path: str = "", 
                 error_code: str = "PARSING_ERROR"):
        self.message = message
        self.file_path = file_path
        self.error_code = error_code
        super().__init__(self.message)


class ReconstructionError(Exception):
    """Exception raised during document reconstruction."""
    
    def __init__(self, message: str, format_type: str = "", 
                 error_code: str = "RECONSTRUCTION_ERROR"):
        self.message = message
        self.format_type = format_type
        self.error_code = error_code
        super().__init__(self.message)


class DocumentParser(ABC):
    """Abstract base class for document parsers."""
    
    def __init__(self):
        """Initialize the parser."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def parse(self, file_path: str) -> DocumentStructure:
        """Parse a document file and extract its structure.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            DocumentStructure containing parsed content and layout
            
        Raises:
            ParsingError: If parsing fails
        """
        pass
    
    @abstractmethod
    def reconstruct(self, structure: DocumentStructure) -> bytes:
        """Reconstruct a document from its structure.
        
        Args:
            structure: DocumentStructure to reconstruct
            
        Returns:
            Binary content of the reconstructed document
            
        Raises:
            ReconstructionError: If reconstruction fails
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats.
        
        Returns:
            List of supported file extensions
        """
        pass
    
    def validate_file(self, file_path: str) -> bool:
        """Validate file before parsing.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            True if file is valid
            
        Raises:
            ParsingError: If file validation fails
        """
        try:
            # Check if file exists
            path = Path(file_path)
            if not path.exists():
                raise ParsingError(f"File not found: {file_path}", file_path)
            
            if not path.is_file():
                raise ParsingError(f"Path is not a file: {file_path}", file_path)
            
            # Validate file format
            validate_file_format(file_path)
            
            # Validate file size
            file_size = path.stat().st_size
            validate_file_size(file_size)
            
            # Check if format is supported by this parser
            file_ext = path.suffix.lower().lstrip('.')
            if file_ext not in self.get_supported_formats():
                raise ParsingError(
                    f"Format {file_ext} not supported by {self.__class__.__name__}",
                    file_path
                )
            
            return True
            
        except Exception as e:
            if isinstance(e, ParsingError):
                raise
            raise ParsingError(f"File validation failed: {str(e)}", file_path)
    
    def extract_metadata(self, file_path: str) -> DocumentMetadata:
        """Extract basic metadata from file.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            DocumentMetadata with basic file information
        """
        path = Path(file_path)
        stat = path.stat()
        
        return DocumentMetadata(
            title=path.stem,
            file_size=stat.st_size,
            creation_date=None,  # Will be set by DocumentMetadata.__post_init__
            modification_date=None
        )
    
    def parse_with_validation(self, file_path: str) -> DocumentStructure:
        """Parse document with validation.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            DocumentStructure containing parsed content and layout
            
        Raises:
            ParsingError: If validation or parsing fails
        """
        self.logger.info(f"Starting to parse document: {file_path}")
        
        try:
            # Validate file first
            self.validate_file(file_path)
            
            # Parse the document
            structure = self.parse(file_path)
            
            # Validate the parsed structure
            if not structure.pages:
                raise ParsingError(
                    "Parsed document contains no pages", 
                    file_path
                )
            
            self.logger.info(
                f"Successfully parsed document: {file_path} "
                f"({len(structure.pages)} pages)"
            )
            
            return structure
            
        except Exception as e:
            if isinstance(e, ParsingError):
                self.logger.error(f"Parsing failed for {file_path}: {e.message}")
                raise
            
            error_msg = f"Unexpected error during parsing: {str(e)}"
            self.logger.error(f"Parsing failed for {file_path}: {error_msg}")
            raise ParsingError(error_msg, file_path)
    
    def reconstruct_with_validation(self, structure: DocumentStructure) -> bytes:
        """Reconstruct document with validation.
        
        Args:
            structure: DocumentStructure to reconstruct
            
        Returns:
            Binary content of the reconstructed document
            
        Raises:
            ReconstructionError: If validation or reconstruction fails
        """
        self.logger.info(
            f"Starting to reconstruct {structure.format} document "
            f"({len(structure.pages)} pages)"
        )
        
        try:
            # Validate structure
            if not structure.pages:
                raise ReconstructionError(
                    "Cannot reconstruct document with no pages",
                    structure.format
                )
            
            # Check format compatibility
            if structure.format not in self.get_supported_formats():
                raise ReconstructionError(
                    f"Format {structure.format} not supported by "
                    f"{self.__class__.__name__}",
                    structure.format
                )
            
            # Reconstruct the document
            content = self.reconstruct(structure)
            
            if not content:
                raise ReconstructionError(
                    "Reconstruction produced empty content",
                    structure.format
                )
            
            self.logger.info(
                f"Successfully reconstructed {structure.format} document "
                f"({len(content)} bytes)"
            )
            
            return content
            
        except Exception as e:
            if isinstance(e, ReconstructionError):
                self.logger.error(
                    f"Reconstruction failed for {structure.format}: {e.message}"
                )
                raise
            
            error_msg = f"Unexpected error during reconstruction: {str(e)}"
            self.logger.error(
                f"Reconstruction failed for {structure.format}: {error_msg}"
            )
            raise ReconstructionError(error_msg, structure.format)


class DocumentParserFactory:
    """Factory for creating format-specific document parsers."""
    
    def __init__(self):
        """Initialize the factory."""
        self._parsers: Dict[str, type[DocumentParser]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def register_parser(self, format_ext: str, 
                       parser_class: type[DocumentParser]) -> None:
        """Register a parser for a specific format.
        
        Args:
            format_ext: File extension (e.g., 'pdf', 'docx')
            parser_class: Parser class to handle this format
            
        Raises:
            ValueError: If parser_class is not a DocumentParser subclass
        """
        if not issubclass(parser_class, DocumentParser):
            raise ValueError(
                f"Parser class must be a subclass of DocumentParser, "
                f"got {parser_class.__name__}"
            )
        
        format_key = format_ext.lower().lstrip('.')
        self._parsers[format_key] = parser_class
        
        self.logger.info(
            f"Registered parser {parser_class.__name__} for format '{format_key}'"
        )
    
    def unregister_parser(self, format_ext: str) -> bool:
        """Unregister a parser for a specific format.
        
        Args:
            format_ext: File extension to unregister
            
        Returns:
            True if parser was unregistered, False if not found
        """
        format_key = format_ext.lower().lstrip('.')
        if format_key in self._parsers:
            del self._parsers[format_key]
            self.logger.info(f"Unregistered parser for format '{format_key}'")
            return True
        return False
    
    def create_parser(self, file_format: str) -> DocumentParser:
        """Create a parser for the specified format.
        
        Args:
            file_format: File extension or format identifier
            
        Returns:
            DocumentParser instance for the format
            
        Raises:
            ValueError: If format is not supported
        """
        format_key = file_format.lower().lstrip('.')
        if format_key not in self._parsers:
            supported = ', '.join(self.get_supported_formats())
            raise ValueError(
                f"Unsupported format: {file_format}. "
                f"Supported formats: {supported}"
            )
        
        parser_class = self._parsers[format_key]
        parser = parser_class()
        
        self.logger.debug(
            f"Created parser {parser_class.__name__} for format '{format_key}'"
        )
        
        return parser
    
    def get_supported_formats(self) -> List[str]:
        """Get all supported formats.
        
        Returns:
            List of supported file extensions
        """
        return list(self._parsers.keys())
    
    def is_format_supported(self, file_format: str) -> bool:
        """Check if a format is supported.
        
        Args:
            file_format: File extension or format identifier
            
        Returns:
            True if format is supported
        """
        format_key = file_format.lower().lstrip('.')
        return format_key in self._parsers
    
    def get_parser_for_file(self, file_path: str) -> DocumentParser:
        """Get appropriate parser for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            DocumentParser instance for the file format
            
        Raises:
            ValueError: If file format is not supported
        """
        file_ext = Path(file_path).suffix.lower().lstrip('.')
        return self.create_parser(file_ext)
    
    def parse_document(self, file_path: str) -> DocumentStructure:
        """Parse a document using the appropriate parser.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            DocumentStructure containing parsed content and layout
            
        Raises:
            ValueError: If format is not supported
            ParsingError: If parsing fails
        """
        parser = self.get_parser_for_file(file_path)
        return parser.parse_with_validation(file_path)
    
    def reconstruct_document(self, structure: DocumentStructure) -> bytes:
        """Reconstruct a document using the appropriate parser.
        
        Args:
            structure: DocumentStructure to reconstruct
            
        Returns:
            Binary content of the reconstructed document
            
        Raises:
            ValueError: If format is not supported
            ReconstructionError: If reconstruction fails
        """
        parser = self.create_parser(structure.format)
        return parser.reconstruct_with_validation(structure)


# Global factory instance
_global_factory: Optional[DocumentParserFactory] = None


def get_parser_factory() -> DocumentParserFactory:
    """Get the global parser factory instance.
    
    Returns:
        Global DocumentParserFactory instance
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = DocumentParserFactory()
    return _global_factory


def register_parser(format_ext: str, 
                   parser_class: type[DocumentParser]) -> None:
    """Register a parser in the global factory.
    
    Args:
        format_ext: File extension (e.g., 'pdf', 'docx')
        parser_class: Parser class to handle this format
    """
    factory = get_parser_factory()
    factory.register_parser(format_ext, parser_class)

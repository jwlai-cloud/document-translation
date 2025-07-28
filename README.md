# Multimodal Document Translator

A sophisticated document translation application that preserves the original layout and formatting of rich documents (PDF, DOCX, EPUB) while translating text content. Unlike conventional translation apps that simply extract and translate text via OCR, this application maintains visual elements like icons, images, and formatting while intelligently replacing translated content and adjusting layout when translated text differs in length from the original.

## 🚀 Features

### Core Functionality
- **Multi-format Support**: Upload and translate PDF, DOCX, and EPUB documents
- **Layout Preservation**: Maintains original document structure, images, icons, and formatting
- **Intelligent Text Fitting**: Automatically adjusts layout when translated text is longer or shorter than original
- **Automatic Language Detection**: Identifies the primary language of uploaded documents
- **Side-by-Side Preview**: Compare original and translated documents before download
- **Quality Assessment**: Built-in quality checks with confidence scoring and recommendations

### Advanced Capabilities
- **Context-Aware Translation**: Preserves meaning using surrounding text context
- **Visual Element Handling**: Maintains spatial relationships between text and images/charts
- **Complex Layout Support**: Handles tables, headers, footers, multi-column layouts, and text boxes
- **Format-Specific Processing**: Optimized parsers for each document format
- **Batch Processing**: Efficient handling of large documents

## 🌍 Supported Languages

- **English** (en)
- **French** (fr) 
- **Simplified Chinese** (zh)
- **Japanese** (ja)
- **Spanish** (es)
- **German** (de)
- **Italian** (it)
- **Portuguese** (pt)
- **Russian** (ru)
- **Korean** (ko)

## 📋 Requirements

See [requirements.txt](requirements.txt) for the complete list of dependencies.

### Key Dependencies
- **FastAPI & Gradio**: Web framework and user interface
- **PyMuPDF**: Advanced PDF processing
- **python-docx**: DOCX document handling
- **ebooklib**: EPUB processing
- **Transformers & PyTorch**: Translation models
- **langdetect**: Language detection

## 🛠️ Installation

1. **Clone the repository**:
```bash
git clone https://github.com/jwlai-cloud/document_translator.git
cd document_translator
```

2. **Create a virtual environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

## 🚀 Usage

### Quick Start
```bash
python app.py
```

The application will start a local server accessible in your web browser at `http://localhost:7860`.

### Web Interface
1. Upload a document (PDF, DOCX, or EPUB)
2. Review the automatically detected source language
3. Select your target language
4. Preview the translation with side-by-side comparison
5. Download the translated document in the original format

### API Usage
```python
import requests

# Upload and translate a document
files = {'file': open('document.pdf', 'rb')}
data = {
    'source_lang': 'en',
    'target_lang': 'zh'
}

response = requests.post('http://localhost:8000/translate', files=files, data=data)
result = response.json()
```

## 🏗️ Architecture

The application follows a modular architecture with the following components:

- **Document Parsers**: Format-specific parsers for PDF, DOCX, and EPUB
- **Layout Analysis Engine**: Analyzes spatial relationships and visual elements
- **Translation Service**: Context-aware translation with formatting preservation
- **Layout Reconstruction Engine**: Rebuilds documents with translated content
- **Quality Assessment Service**: Evaluates translation quality and layout preservation

## 📁 Project Structure

```
document_translator/
├── src/
│   ├── parsers/          # Document format parsers
│   ├── layout/           # Layout analysis and reconstruction
│   ├── translation/      # Translation services
│   ├── services/         # Core services (upload, preview, quality)
│   ├── models/           # Data models and structures
│   └── config.py         # Configuration settings
├── tests/                # Comprehensive test suite
├── .kiro/specs/          # Feature specifications and design docs
├── app.py               # Main application entry point
└── requirements.txt     # Project dependencies
```

## 🧪 Testing

Run the test suite:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=src
```

## 📖 Development

### Specification-Driven Development
This project follows a specification-driven approach with detailed documentation in `.kiro/specs/multimodal-document-translator/`:

- **requirements.md**: Detailed feature requirements
- **design.md**: Technical architecture and design decisions
- **tasks.md**: Implementation roadmap and task breakdown

### Contributing
1. Fork the repository
2. Create a feature branch
3. Follow the existing code style and architecture
4. Add tests for new functionality
5. Submit a pull request

## 🔧 Configuration

### Environment Variables
- `MAX_FILE_SIZE`: Maximum upload file size (default: 50MB)
- `TEMP_STORAGE_DURATION`: Temporary file retention time (default: 1 hour)
- `QUALITY_THRESHOLD`: Minimum quality score for translations (default: 0.8)

### Supported File Formats
- **PDF**: Advanced processing with PyMuPDF
- **DOCX**: Microsoft Word documents with full formatting support
- **EPUB**: E-book format with chapter-based processing

## 📊 Performance

- **Processing Speed**: < 30 seconds for typical documents
- **Memory Usage**: < 2GB peak memory per document
- **Translation Quality**: > 0.85 average quality score
- **Layout Preservation**: > 0.90 layout similarity score

## 🐛 Troubleshooting

### Common Issues
- **Large File Processing**: Ensure sufficient memory for large documents
- **Language Detection**: Low confidence may require manual language selection
- **Layout Conflicts**: Complex layouts may need manual review

### Error Handling
The application provides comprehensive error handling with:
- Clear error messages and recovery suggestions
- Automatic retry mechanisms for transient failures
- Detailed logging for debugging

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Support

For issues, questions, or contributions:
- **GitHub Issues**: [Report bugs or request features](https://github.com/jwlai-cloud/document_translator/issues)
- **Documentation**: Check the `.kiro/specs/` directory for detailed specifications

## 🔄 Roadmap

- [ ] Additional language support
- [ ] Real-time collaboration features
- [ ] Cloud deployment options
- [ ] Mobile app support
- [ ] Advanced formatting preservation

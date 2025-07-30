"""Main application entry point for the Multimodal Document Translator."""

import os
import logging
from src.web.gradio_interface import TranslationWebInterface

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_app():
    """Create and configure the application."""
    # Initialize the web interface
    web_interface = TranslationWebInterface()
    
    # Create the Gradio interface
    interface = web_interface.create_interface()
    
    return interface, web_interface

def main():
    """Main entry point."""
    # Get port from environment variable (for cloud deployment)
    port = int(os.environ.get("PORT", 7860))
    
    # Create the application
    interface, web_interface = create_app()
    
    try:
        # Launch the interface
        interface.launch(
            server_name="0.0.0.0",  # Listen on all interfaces
            server_port=port,
            share=False,  # Don't create public link
            debug=False,  # Disable debug mode for production
            show_error=True,
            quiet=False
        )
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        # Cleanup
        web_interface.shutdown()

if __name__ == "__main__":
    main()
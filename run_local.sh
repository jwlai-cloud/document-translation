#!/bin/bash

# Local development script for Multimodal Document Translator

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Multimodal Document Translator locally${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed. Please install it first.${NC}"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${YELLOW}🔧 Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}📥 Installing dependencies...${NC}"
pip install -r requirements.txt

# Set environment variables
export PYTHONPATH=$(pwd)
export PORT=7860

# Create necessary directories
mkdir -p temp uploads downloads cache logs

echo -e "${GREEN}✅ Setup complete!${NC}"
echo -e "${GREEN}🌐 Starting application on http://localhost:7860${NC}"

# Run the application
python app
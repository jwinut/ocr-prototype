#!/bin/bash
# Thai Financial Document OCR - GUI Launcher
# Quick script to start the Streamlit application

echo "🚀 Starting Thai Financial Document OCR Application..."
echo "📁 Working directory: $(pwd)"
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit is not installed"
    echo "📦 Install with: pip install streamlit pandas"
    exit 1
fi

# Check if pandas is installed
python3 -c "import pandas" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Pandas is not installed"
    echo "📦 Install with: pip install pandas"
    exit 1
fi

echo "✅ Dependencies OK"
echo "🌐 Starting application..."
echo ""
echo "The application will open in your browser at http://localhost:8501"
echo "Press Ctrl+C to stop the application"
echo ""

# Run streamlit
streamlit run app/main.py

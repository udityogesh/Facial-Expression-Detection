#!/bin/bash

# Startup script for Face Emotion Detection App
# This script handles environment setup and starts the application

echo "🚀 Starting Face Emotion Detection Application..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/Update dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if model files exist
if [ ! -f "emotiondetector.h5" ] || [ ! -f "emotiondetector.json" ]; then
    echo "❌ Error: Model files not found!"
    echo "Please ensure emotiondetector.h5 and emotiondetector.json are in the project directory."
    exit 1
fi

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update .env file with your configuration!"
fi

# Set environment variables if not already set
export FLASK_ENV=${FLASK_ENV:-development}
export PORT=${PORT:-5000}

# Start the application
echo "✅ Starting application on port $PORT..."
echo "🌐 Access the app at: http://localhost:$PORT"
echo "Press CTRL+C to stop the server"
echo ""

python app.py

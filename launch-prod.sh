#!/bin/bash

# Aelyra Production Launcher
# Starts backend with production settings (HTTPS)

echo "🚀 Starting Aelyra Production Server..."
echo ""

# Check if .env.prod exists
if [ ! -f .env.prod ]; then
    echo "❌ Error: .env.prod file not found!"
    echo "Please create .env.prod with production configuration"
    exit 1
fi

# Check SSL certificates
if [ ! -f certs/localhost+2.pem ] || [ ! -f certs/localhost+2-key.pem ]; then
    echo "❌ Error: SSL certificates not found in certs/ directory!"
    echo "Please generate SSL certificates before running in production mode"
    exit 1
fi

# Check if virtual environment should be activated
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Load production environment
export $(cat .env.prod | grep -v '^#' | xargs)

# Start backend with production settings
echo "🐍 Starting production server with HTTPS..."
echo "📍 Server will be available at: https://127.0.0.1:5988"
echo ""

uvicorn main:app --host 127.0.0.1 --port 5988 --ssl-keyfile=certs/localhost+2-key.pem --ssl-certfile=certs/localhost+2.pem

echo ""
echo "🛑 Production server stopped"

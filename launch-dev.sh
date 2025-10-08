#!/bin/bash

# Aelyra Development Launcher
# Starts both backend and frontend development servers

echo "🚀 Starting Aelyra Development Environment..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure your API keys"
    exit 1
fi

# Check if virtual environment should be activated
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "✅ Servers stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend
echo "🐍 Starting Python backend on http://127.0.0.1:5988..."
python main.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start frontend
echo "⚛️  Starting React frontend on http://localhost:3000..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Development servers started!"
echo ""
echo "📍 Backend:  http://127.0.0.1:5988"
echo "📍 Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID

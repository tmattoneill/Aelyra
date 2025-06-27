  #!/usr/bin/bash

  # Activate virtual environment
  source .venv/bin/activate

  # Function to cleanup background processes
  cleanup() {
      echo "Shutting down servers..."
      jobs -p | xargs -r kill
      exit
  }

  # Set trap to cleanup on script exit
  trap cleanup EXIT INT TERM

  echo "Starting Aelyra backend..."
  python main.py &
  BACKEND_PID=$!

  echo "Waiting for backend to start..."
  sleep 3

  echo "Starting Aelyra frontend..."
  cd frontend
  npm start

  # Keep script running until user stops it
  wait

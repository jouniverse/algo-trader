#!/bin/bash
# Start the Algo-Trader API server

set -e

# Navigate to project root
cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables
if [ -f "config/.env" ]; then
    export $(cat config/.env | grep -v '^#' | xargs)
fi

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Start the server
echo "Starting Algo-Trader API server..."
python -m uvicorn src.python.api.server:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload

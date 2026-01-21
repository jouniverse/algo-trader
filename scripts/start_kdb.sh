#!/bin/bash
# Start kdb+ ticker plant and databases

set -e

# Navigate to project root
cd "$(dirname "$0")/.."

echo "Starting kdb+ infrastructure..."

# Create data directories
mkdir -p data/hdb data/rdb data/tplogs

# Start Ticker Plant (port 5010)
echo "Starting Ticker Plant on port 5010..."
q src/q/tick/tick.q sym data/tplogs -p 5010 &
TP_PID=$!

sleep 2

# Start RDB (port 5011)
echo "Starting RDB on port 5011..."
q src/q/tick/r.q :5010 -p 5011 &
RDB_PID=$!

sleep 2

# Start HDB (port 5012)
echo "Starting HDB on port 5012..."
q data/hdb -p 5012 &
HDB_PID=$!

echo ""
echo "kdb+ infrastructure started:"
echo "  - Ticker Plant: localhost:5010 (PID: $TP_PID)"
echo "  - RDB: localhost:5011 (PID: $RDB_PID)"
echo "  - HDB: localhost:5012 (PID: $HDB_PID)"
echo ""
echo "Press Ctrl+C to stop all processes..."

# Wait for any process to exit
wait

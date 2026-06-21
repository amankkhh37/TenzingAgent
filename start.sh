#!/bin/bash

# Tenzing Growth Agent - Startup Script
# Starts all 3 components in the correct order

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_DIR/venv"

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/screenshots"
mkdir -p "$PROJECT_DIR/exports"

echo "🌍 Tenzing Growth Agent - Startup Script"
echo "========================================="
echo ""
echo "Starting all services..."
echo ""

# Function to start a component
start_component() {
    local name=$1
    local script=$2
    local log=$3
    
    echo "▶️  Starting $name..."
    nohup python "$PROJECT_DIR/$script" > "$PROJECT_DIR/logs/$log" 2>&1 &
    sleep 2
}

# Start Scanner
start_component "Facebook Scanner" "scanner.py" "scanner.log"

# Start Comment Worker
start_component "Comment Worker" "comment_worker.py" "comment_worker.log"

# Start Dashboard
echo "▶️  Starting Streamlit Dashboard..."
streamlit run "$PROJECT_DIR/app.py" --logger.level=info

echo ""
echo "========================================="
echo "✅ All services started!"
echo ""
echo "Dashboard:      http://localhost:8501"
echo "Scanner:        Running in background (logs/scanner.log)"
echo "Comment Worker: Running in background (logs/comment_worker.log)"
echo ""

#!/bin/bash

# Tenzing Growth Agent - Pre-Launch Verification Checklist
# Run this to verify the system is ready to start

set -e  # Exit on error

echo "🌍 Tenzing Growth Agent - Pre-Launch Verification"
echo "=================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_count=0
pass_count=0

# Function to print check result
check() {
    local name=$1
    local cmd=$2
    check_count=$((check_count + 1))
    
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✅${NC} $name"
        pass_count=$((pass_count + 1))
    else
        echo -e "${RED}❌${NC} $name"
    fi
}

# Function to print warning
warn() {
    local name=$1
    echo -e "${YELLOW}⚠️${NC}  $name"
}

# Function to print info
info() {
    local name=$1
    echo -e "${GREEN}ℹ️${NC}  $name"
}

echo "📋 File Structure"
echo "-----------------"
check "config.py exists" "[ -f config.py ]"
check "database.py exists" "[ -f database.py ]"
check "models.py exists" "[ -f models.py ]"
check "lead_scorer.py exists" "[ -f lead_scorer.py ]"
check "comment_generator.py exists" "[ -f comment_generator.py ]"
check "scanner.py exists" "[ -f scanner.py ]"
check "comment_worker.py exists" "[ -f comment_worker.py ]"
check "analytics.py exists" "[ -f analytics.py ]"
check "content_generator.py exists" "[ -f content_generator.py ]"
check "app.py exists" "[ -f app.py ]"
check "logger.py exists" "[ -f logger.py ]"

echo ""
echo "📁 Directory Structure"
echo "---------------------"
check "data/ directory" "[ -d data ]"
check "logs/ directory" "[ -d logs ]"
check "screenshots/ directory" "[ -d screenshots ]"
check "exports/ directory" "[ -d exports ]"
check "venv/ directory" "[ -d venv ]"

echo ""
echo "📦 Python Environment"
echo "---------------------"
check "Python 3.12+" "python3 --version | grep -E 'Python 3\.(12|13|14)'"
check "Virtual environment activated" "[ -n \"\$VIRTUAL_ENV\" ]"
check "Playwright installed" "python3 -c 'import playwright' 2>/dev/null"
check "Streamlit installed" "python3 -c 'import streamlit' 2>/dev/null"
check "SQLAlchemy installed" "python3 -c 'import sqlalchemy' 2>/dev/null"
check "Pandas installed" "python3 -c 'import pandas' 2>/dev/null"
check "Plotly installed" "python3 -c 'import plotly' 2>/dev/null"

echo ""
echo "📄 Documentation"
echo "----------------"
check "QUICKSTART.md exists" "[ -f QUICKSTART.md ]"
check "PRODUCTION_README.md exists" "[ -f PRODUCTION_README.md ]"
check "BUILD_SUMMARY.md exists" "[ -f BUILD_SUMMARY.md ]"
check "requirements.txt exists" "[ -f requirements.txt ]"

echo ""
echo "🚀 Scripts"
echo "----------"
check "start.sh exists" "[ -f start.sh ]"
check "init.py exists" "[ -f init.py ]"

echo ""
echo "🌐 External Services"
echo "--------------------"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC} Ollama server running"
    pass_count=$((pass_count + 1))
else
    echo -e "${YELLOW}⚠️${NC}  Ollama server not running (start with: ollama serve)"
fi
check_count=$((check_count + 1))

echo ""
echo "💾 Database"
echo "-----------"
if [ -f data/travel_crm.db ]; then
    echo -e "${GREEN}✅${NC} Database exists"
    pass_count=$((pass_count + 1))
else
    echo -e "${YELLOW}⚠️${NC}  Database not initialized (will be created on first run)"
fi
check_count=$((check_count + 1))

echo ""
echo "🌍 Browser"
echo "----------"
if [ -f ~/.playwright/browsers ]; then
    echo -e "${GREEN}✅${NC} Playwright browsers installed"
    pass_count=$((pass_count + 1))
else
    echo -e "${YELLOW}⚠️${NC}  Playwright browsers not installed (run: playwright install)"
fi
check_count=$((check_count + 1))

echo ""
echo "=================================================="
echo "Summary: $pass_count / $check_count checks passed"
echo "=================================================="
echo ""

if [ $pass_count -eq $check_count ]; then
    echo -e "${GREEN}✅ System is ready to launch!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Start Ollama: ollama serve"
    echo "2. Run startup script: ./start.sh"
    echo "   OR run manually:"
    echo "   - Terminal 1: python scanner.py"
    echo "   - Terminal 2: python comment_worker.py"
    echo "   - Terminal 3: streamlit run app.py"
    echo ""
    echo "Dashboard: http://localhost:8501"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some checks failed${NC}"
    echo ""
    echo "Common fixes:"
    echo "1. Activate venv: source venv/bin/activate"
    echo "2. Install dependencies: pip install -r requirements.txt"
    echo "3. Setup Ollama: ollama serve"
    echo "4. Install browsers: playwright install"
    echo ""
    echo "See QUICKSTART.md for detailed setup instructions"
    exit 1
fi

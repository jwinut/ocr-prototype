#!/bin/bash
# Thai Financial Document OCR Prototype - Deployment Script
# Automates environment setup, dependency installation, and app startup
# Logs all output to ./logs/deploy_YYYYMMDD_HHMMSS.log

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Setup logging
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOGS_DIR/deploy_${TIMESTAMP}.log"

# Function to log to both console and file
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

# Function to log without colors (for file only)
log_plain() {
    echo "$1" >> "$LOG_FILE"
}

# Redirect all stderr to log file while keeping console output
exec 2> >(tee -a "$LOG_FILE" >&2)

# Log header
log_plain "=============================================="
log_plain "Deployment started at $(date)"
log_plain "Log file: $LOG_FILE"
log_plain "=============================================="

log "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
log "${BLUE}║   Thai Financial Document OCR Prototype - Deploy Script    ║${NC}"
log "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
log ""
log "  Log file: ${GREEN}$LOG_FILE${NC}"
log ""

# Check Python version
check_python() {
    log "${YELLOW}[1/6]${NC} Checking Python version..."

    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log "${RED}Error: Python not found. Please install Python 3.11+${NC}"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log "  Found Python ${GREEN}$PYTHON_VERSION${NC}"

    # Check minimum version (3.9+)
    MIN_VERSION="3.9"
    if [ "$(printf '%s\n' "$MIN_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$MIN_VERSION" ]; then
        log "${RED}Error: Python 3.9+ required, found $PYTHON_VERSION${NC}"
        exit 1
    fi
}

# Create/activate virtual environment
setup_venv() {
    log "${YELLOW}[2/6]${NC} Setting up virtual environment..."

    if [ ! -d "venv" ]; then
        log "  Creating new virtual environment..."
        $PYTHON_CMD -m venv venv 2>&1 | tee -a "$LOG_FILE"
        log "  ${GREEN}Created venv${NC}"
    else
        log "  ${GREEN}Using existing venv${NC}"
    fi

    # Activate venv
    source venv/bin/activate
    log "  ${GREEN}Activated virtual environment${NC}"
}

# Install dependencies
install_deps() {
    log "${YELLOW}[3/6]${NC} Installing dependencies..."

    # Upgrade pip first (log output)
    log_plain "--- pip upgrade output ---"
    pip install --upgrade pip 2>&1 | tee -a "$LOG_FILE"

    # Install from requirements.txt
    if [ -f "requirements.txt" ]; then
        log "  Installing from requirements.txt..."
        log_plain "--- requirements.txt install output ---"
        pip install -r requirements.txt 2>&1 | tee -a "$LOG_FILE"
        log "  ${GREEN}Dependencies installed${NC}"
    else
        log "${RED}Error: requirements.txt not found${NC}"
        exit 1
    fi
}

# Create necessary directories
create_dirs() {
    log "${YELLOW}[4/6]${NC} Creating directories..."

    mkdir -p data/exports
    mkdir -p logs
    mkdir -p uploads

    log "  ${GREEN}Created: data/, logs/, uploads/${NC}"
}

# Initialize database
init_database() {
    log "${YELLOW}[5/6]${NC} Initializing database..."

    if [ -f "scripts/init_database.py" ]; then
        python scripts/init_database.py 2>&1 | tee -a "$LOG_FILE"
        log "  ${GREEN}Database initialized${NC}"
    else
        # Fallback: initialize via Python
        python -c "
from app.database import DatabaseManager
db = DatabaseManager()
db.init_db()
print('  Database tables created')
" 2>&1 | tee -a "$LOG_FILE"
        log "  ${GREEN}Database ready${NC}"
    fi
}

# Verify Y67 folder
verify_data() {
    log "${YELLOW}[6/6]${NC} Verifying data folder..."

    Y67_PATH="../Y67"
    if [ -d "$Y67_PATH" ]; then
        DOC_COUNT=$(find "$Y67_PATH" -name "*.pdf" | wc -l | tr -d ' ')
        log "  ${GREEN}Found $DOC_COUNT PDF documents in Y67${NC}"
    else
        log "  ${YELLOW}Warning: Y67 folder not found at $Y67_PATH${NC}"
        log "  The app will work but no documents to process"
    fi
}

# Start the application
start_app() {
    log ""
    log "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    log "${GREEN}║                    Starting Application                     ║${NC}"
    log "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    log ""
    log "  ${BLUE}URL: http://localhost:8501${NC}"
    log "  ${YELLOW}Press Ctrl+C to stop${NC}"
    log "  ${BLUE}Logs: $LOG_FILE${NC}"
    log ""

    log_plain "--- Streamlit application output ---"

    # Start Streamlit with logging
    streamlit run app/main.py \
        --server.port 8501 \
        --server.address localhost \
        --browser.gatherUsageStats false 2>&1 | tee -a "$LOG_FILE"

    EXIT_CODE=$?
    if [ "$EXIT_CODE" -eq 130 ]; then
        log "${YELLOW}Graceful shutdown requested (SIGINT). Waiting for cleanup...${NC}"
        log_plain "Graceful shutdown requested (SIGINT) at $(date)"
    else
        log "${YELLOW}Streamlit exited with code $EXIT_CODE${NC}"
        log_plain "Streamlit exited with code $EXIT_CODE at $(date)"
    fi
}

# Cleanup old logs (keep last 10)
cleanup_old_logs() {
    log_plain "Cleaning up old log files..."
    cd "$LOGS_DIR"
    ls -t deploy_*.log 2>/dev/null | tail -n +11 | xargs -r rm -f
    cd "$SCRIPT_DIR"
}

# Main execution
main() {
    check_python
    setup_venv
    install_deps
    create_dirs
    init_database
    verify_data
    cleanup_old_logs
    start_app
}

# Run with error handling
trap 'log "\n${RED}Deployment interrupted (signal caught)${NC}"; log_plain "Deployment interrupted (signal) at $(date)"; exit 1' INT TERM

# Log script arguments
log_plain "Script arguments: $@"

main "$@"

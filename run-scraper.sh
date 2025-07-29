#!/bin/bash

# HackTown Scraper Runner Script
# This script runs the Docker container and handles logging

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/scraper-$(date +%Y%m%d).log"
CONTAINER_NAME="hacktown-scraper"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to cleanup old containers
cleanup_container() {
    if docker ps -a --format "table {{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
        log "Removing existing container: $CONTAINER_NAME"
        docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
}

# Function to cleanup old logs (keep last 7 days)
cleanup_logs() {
    find "$LOG_DIR" -name "scraper-*.log" -mtime +7 -delete 2>/dev/null || true
}

# Main execution
main() {
    log "=== Starting HackTown Scraper ==="
    
    cd "$SCRIPT_DIR"
    
    # Cleanup
    cleanup_container
    cleanup_logs
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        log "Warning: .env file not found. Make sure environment variables are set."
    fi
    
    # Run the container
    log "Starting Docker container..."
    
    if docker compose up --build hacktown-scraper 2>&1 | tee -a "$LOG_FILE"; then
        log "Scraper completed successfully"
        exit_code=0
    else
        log "Scraper failed with error"
        exit_code=1
    fi
    
    # Cleanup the container after run
    cleanup_container
    
    log "=== HackTown Scraper Finished ==="
    
    exit $exit_code
}

# Run main function
main "$@"

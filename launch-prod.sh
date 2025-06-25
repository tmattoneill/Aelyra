#!/bin/bash

# PlayMaker Production Launch Script
# Run this to start the PlayMaker application in production mode
# Usage: ./launch-prod.sh [--daemon] [--stop] [--restart] [--status]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="playmaker"
PID_FILE="$HOME/PlayMaker/$APP_NAME.pid"
LOG_FILE="$HOME/PlayMaker/logs/$APP_NAME.log"
ERROR_LOG="$HOME/PlayMaker/logs/$APP_NAME.error.log"
HOST="127.0.0.1"
PORT="5988"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Parse command line arguments
DAEMON_MODE=false
STOP_MODE=false
RESTART_MODE=false
STATUS_MODE=false

for arg in "$@"; do
    case $arg in
        --daemon|-d)
            DAEMON_MODE=true
            shift
            ;;
        --stop)
            STOP_MODE=true
            shift
            ;;
        --restart)
            RESTART_MODE=true
            shift
            ;;
        --status)
            STATUS_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--daemon] [--stop] [--restart] [--status]"
            echo "  --daemon, -d    Run in daemon mode (background)"
            echo "  --stop          Stop the running server"
            echo "  --restart       Restart the server"
            echo "  --status        Show server status"
            echo "  --help, -h      Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown argument: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if we're in the right directory
if [ "$(basename "$PWD")" != "PlayMaker" ]; then
    print_error "Not in PlayMaker directory. Please cd to ~/PlayMaker first."
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to check if server is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0  # Running
        else
            rm -f "$PID_FILE"  # Clean up stale PID file
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Function to get server status
get_status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        print_status "$APP_NAME is running (PID: $pid)"
        
        # Check if port is accessible
        if curl -s "http://$HOST:$PORT/docs" > /dev/null 2>&1; then
            print_status "Server is responding on http://$HOST:$PORT"
        else
            print_warning "Server process running but not responding on port $PORT"
        fi
        
        # Show memory usage
        local mem_usage=$(ps -o pid,ppid,pgid,rss,vsz,comm -p "$pid" | tail -n 1)
        print_info "Memory usage: $mem_usage"
        
        return 0
    else
        print_warning "$APP_NAME is not running"
        return 1
    fi
}

# Function to stop the server
stop_server() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        print_info "Stopping $APP_NAME (PID: $pid)..."
        
        # Send SIGTERM
        kill "$pid"
        
        # Wait for graceful shutdown
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ $count -lt 30 ]; do
            sleep 1
            ((count++))
        done
        
        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            print_warning "Graceful shutdown failed, force killing..."
            kill -9 "$pid"
            sleep 2
        fi
        
        rm -f "$PID_FILE"
        print_status "$APP_NAME stopped successfully"
    else
        print_warning "$APP_NAME is not running"
    fi
}

# Function to validate environment
validate_environment() {
    print_info "Validating environment..."
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Please create it from .env.example"
        exit 1
    fi
    
    # Load environment variables
    set -a
    source .env
    set +a
    
    # Validate required variables
    local required_vars=("SPOTIFY_CLIENT_ID" "SPOTIFY_CLIENT_SECRET" "OPENAI_API_KEY")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            print_error "Required environment variable $var is not set in .env"
            exit 1
        fi
    done
    
    # Check virtual environment
    if [ ! -d ".venv" ]; then
        print_error "Virtual environment not found. Please run deploy-prod.sh first."
        exit 1
    fi
    
    # Check database
    if [ ! -f "playmaker.db" ]; then
        print_error "Database not found. Please run deploy-prod.sh first."
        exit 1
    fi
    
    # Check frontend build
    if [ ! -d "frontend/build" ]; then
        print_error "Frontend build not found. Please run deploy-prod.sh first."
        exit 1
    fi
    
    print_status "Environment validation passed"
}

# Function to start the server
start_server() {
    if is_running; then
        print_warning "$APP_NAME is already running"
        get_status
        exit 0
    fi
    
    validate_environment
    
    print_info "Starting $APP_NAME..."
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Start server
    if [ "$DAEMON_MODE" = true ]; then
        print_info "Starting in daemon mode..."
        nohup uvicorn main:app --host "$HOST" --port "$PORT" --log-level info \
            > "$LOG_FILE" 2> "$ERROR_LOG" &
        echo $! > "$PID_FILE"
        
        # Wait a moment and check if it started successfully
        sleep 3
        if is_running; then
            print_status "$APP_NAME started successfully in daemon mode"
            print_info "Logs: $LOG_FILE"
            print_info "Error logs: $ERROR_LOG"
            print_info "PID file: $PID_FILE"
        else
            print_error "Failed to start $APP_NAME"
            if [ -f "$ERROR_LOG" ]; then
                print_error "Last 10 lines of error log:"
                tail -n 10 "$ERROR_LOG"
            fi
            exit 1
        fi
    else
        print_info "Starting in foreground mode (Ctrl+C to stop)..."
        exec uvicorn main:app --host "$HOST" --port "$PORT" --reload --log-level info
    fi
}

# Function to restart the server
restart_server() {
    print_info "Restarting $APP_NAME..."
    stop_server
    sleep 2
    start_server
}

# Function to show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        print_info "Showing last 50 lines of $LOG_FILE"
        echo "----------------------------------------"
        tail -n 50 "$LOG_FILE"
    else
        print_warning "Log file not found: $LOG_FILE"
    fi
    
    if [ -f "$ERROR_LOG" ]; then
        print_info "Showing last 20 lines of $ERROR_LOG"
        echo "----------------------------------------"
        tail -n 20 "$ERROR_LOG"
    fi
}

# Main execution logic
if [ "$STATUS_MODE" = true ]; then
    get_status
elif [ "$STOP_MODE" = true ]; then
    stop_server
elif [ "$RESTART_MODE" = true ]; then
    restart_server
else
    start_server
fi

# Health check for daemon mode
if [ "$DAEMON_MODE" = true ] && is_running; then
    sleep 5
    if curl -s "http://$HOST:$PORT/docs" > /dev/null 2>&1; then
        print_status "Health check passed - server is responding"
        print_info "Access the application at: http://$HOST:$PORT"
        print_info "API documentation at: http://$HOST:$PORT/docs"
    else
        print_warning "Health check failed - server may still be starting up"
        print_info "Check logs with: tail -f $LOG_FILE"
    fi
fi
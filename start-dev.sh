#!/bin/bash

# Development environment startup script

mkdir -p /workspace/logs

case "$1" in
  frontend)
    cd /workspace/frontend
    echo "Starting frontend development server..."
    npm start
    ;;
  backend)
    cd /workspace
    echo "Starting backend development server..."
    python3 backend/run_backend.py
    ;;
  logs)
    # Create log files
    mkdir -p /workspace/logs
    touch /workspace/logs/frontend.log
    touch /workspace/logs/backend.log
    
    # Check if tmux is installed
    if ! command -v tmux &> /dev/null; then
      echo "tmux not installed, installing..."
      sudo apt-get update && sudo apt-get install -y tmux
    fi
    
    # End existing tmux sessions
    tmux kill-session -t frontend 2>/dev/null || true
    tmux kill-session -t backend 2>/dev/null || true
    
    echo "Starting frontend and backend services in separate sessions..."
    
    # Create frontend tmux session
    cd /workspace/frontend
    tmux new-session -d -s frontend 'npm start | tee /workspace/logs/frontend.log; read'
    echo "Frontend service started in tmux session 'frontend'"
    
    # Create backend tmux session
    cd /workspace
    tmux new-session -d -s backend 'python3 backend/run_backend.py | tee /workspace/logs/backend.log; read'
    echo "Backend service started in tmux session 'backend'"
    
    echo ""
    echo "Use the following commands to connect to service logs:"
    echo "  tmux attach -t frontend  - View frontend logs (press Ctrl+B then D to detach)"
    echo "  tmux attach -t backend   - View backend logs (press Ctrl+B then D to detach)"
    ;;
  stop)
    # Stop all services
    echo "Stopping frontend and backend services..."
    tmux kill-session -t frontend 2>/dev/null || true
    tmux kill-session -t backend 2>/dev/null || true
    echo "All services stopped"
    ;;
  *)
    echo "Usage: ./start-dev.sh [frontend|backend|logs|stop]"
    echo "  frontend - Start frontend development server"
    echo "  backend  - Start backend development server"
    echo "  logs     - Display frontend and backend logs in separate windows"
    echo "  stop     - Stop all started services"
    ;;
esac

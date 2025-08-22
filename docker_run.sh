#!/bin/bash

# Script wrapper per Docker che gestisce meglio Ctrl+C

cleanup() {
    echo ""
    echo "🛑 Force cleanup initiated..."
    
    # Kill all browser processes
    echo "  → Killing browser processes..."
    pkill -9 -f chrome 2>/dev/null
    pkill -9 -f chromium 2>/dev/null
    
    # Remove ALL lock files
    echo "  → Removing lock files..."
    find /var/www/app/browser_sessions -name ".lock" -type f -delete 2>/dev/null
    
    # Also remove stale profile locks
    for dir in /var/www/app/browser_sessions/*/; do
        if [ -f "$dir/.lock" ]; then
            rm -f "$dir/.lock"
            echo "    ✓ Cleaned $(basename $dir)"
        fi
    done
    
    echo "✓ Cleanup complete"
    exit 0
}

# Trap Ctrl+C and other signals
trap cleanup INT TERM EXIT

# Create screenshots directory if it doesn't exist
mkdir -p /var/www/app/screenshots

# Run the program in a loop
while true; do
    echo "Starting Instagram Scraper..."
    python3 /var/www/app/main.py
    EXIT_CODE=$?
    
    # If program exits normally (choice 0), break the loop
    if [ $EXIT_CODE -eq 0 ]; then
        echo "Normal exit."
        break
    fi
    
    echo ""
    echo "Program ended. Restarting in 2 seconds..."
    echo "Press Ctrl+C to exit completely."
    sleep 2
    echo ""
done

# Final cleanup
cleanup
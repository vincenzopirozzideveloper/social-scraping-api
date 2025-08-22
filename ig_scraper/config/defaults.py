"""Default configuration values"""

from pathlib import Path
import os

# Use environment variables if available, otherwise use relative paths
API_RESPONSES_DIR = os.environ.get('IG_API_RESPONSES_DIR', 'api_responses')
SCRAPED_DATA_DIR = os.environ.get('IG_SCRAPED_DATA_DIR', 'scraped_data')
ACTION_LOGS_DIR = os.environ.get('IG_ACTION_LOGS_DIR', 'action_logs')
BROWSER_SESSIONS_DIR = os.environ.get('IG_BROWSER_SESSIONS_DIR', 'browser_sessions')
LOGS_DIR = os.environ.get('IG_LOGS_DIR', 'logs')

DEFAULT_CONFIG = {
    "scraping": {
        "following": {
            "max_count": 200,           # Maximum users per request (Instagram limit)
            "default_count": 12,        # Default count if not specified
            "pagination_delay": 3000,   # Delay between pagination requests (ms)
            "verify_login": True,       # Verify login before scraping
            "save_responses": False,    # Save API responses to file
            "response_dir": f"{API_RESPONSES_DIR}/following"  # Directory for saved responses
        },
        "followers": {
            "max_count": 200,
            "default_count": 12,
            "pagination_delay": 3000,
            "verify_login": True
        },
        "explore": {
            "default_query": "news",
            "save_responses": True,     # Save all responses to files
            "response_dir": SCRAPED_DATA_DIR,
            "pagination_delay": 3000
        }
    },
    "actions": {
        "rate_limiting": {
            "min_delay": 2,             # Minimum seconds between actions
            "max_delay": 5,             # Maximum seconds between actions
            "batch_delay": 3            # Default delay for batch operations
        },
        "follow": {
            "daily_limit": 200,         # Maximum follows per day
            "hourly_limit": 20,         # Maximum follows per hour
            "check_limits": True        # Enable limit checking
        },
        "unfollow": {
            "daily_limit": 200,
            "hourly_limit": 20,
            "check_limits": True,
            "safe_list": [],            # Users to never unfollow (usernames)
            "batch_size": 50,           # Users to unfollow per batch
            "pause_between_batches": 30,  # Seconds to pause between batches
            "stop_on_error": False,     # Stop if unfollow fails
            "auto_confirm": False,      # Skip confirmation prompts
            "aggressive_mode": False,   # Continue even when max_id is null
            "aggressive_retries": 3     # How many times to retry when max_id is null
        },
        "like": {
            "daily_limit": 500,
            "hourly_limit": 50,
            "check_limits": True
        }
    },
    "browser": {
        "headless": False,              # Run browser in headless mode
        "viewport": {
            "width": 1920,
            "height": 1080
        },
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "locale": "en-US",
        "timeout": 30000               # Default timeout for operations (ms)
    },
    "logging": {
        "enabled": True,
        "level": "INFO",               # DEBUG, INFO, WARNING, ERROR
        "save_to_file": True,
        "log_dir": LOGS_DIR,
        "action_logs": True,           # Log all actions
        "response_logs": False         # Log API responses (verbose)
    },
    "session": {
        "auto_save": True,             # Automatically save session after login
        "session_dir": BROWSER_SESSIONS_DIR,
        "max_session_age": 30,         # Days before session is considered expired
        "verify_on_startup": True      # Verify session is still valid on startup
    },
    "safety": {
        "confirm_destructive": True,   # Ask confirmation for unfollow/unlike
        "dry_run": False,              # Simulate actions without executing
        "max_batch_size": 50,          # Maximum items in batch operations
        "stop_on_error": False         # Stop batch operations on first error
    }
}
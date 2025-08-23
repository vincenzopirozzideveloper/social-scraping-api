"""Default configuration values for Instagram Scraper (Docker environment)"""

# Docker paths are fixed - no need for environment variables
API_RESPONSES_DIR = '/app/data/api_responses'
SCRAPED_DATA_DIR = '/app/data/scraped_data'
ACTION_LOGS_DIR = '/app/data/action_logs'
BROWSER_SESSIONS_DIR = '/app/data/browser_sessions'
LOGS_DIR = '/app/data/logs'

DEFAULT_CONFIG = {
    "scraping": {
        "following": {
            "max_count": 200,           # Maximum users per request (Instagram limit)
            "default_count": 200,        # Default count - use maximum supported
            "pagination_delay": 3000,   # Delay between pagination requests (ms)
            "verify_login": True,       # Verify login before scraping
            "save_responses": False,    # Save API responses to file
            "response_dir": f"{API_RESPONSES_DIR}/following",  # Directory for saved responses
            "auto_pagination": True,    # Automatically load pages without prompts
            "max_pages": 50,            # Maximum pages to load automatically
            "page_delay_min": 3,        # Min delay between pages (seconds)
            "page_delay_max": 8         # Max delay between pages (seconds)
        },
        "followers": {
            "max_count": 12,            # Maximum followers per request (Instagram optimal)
            "default_count": 12,         # Default count if not specified  
            "pagination_delay": 3000,    # Delay between pagination requests (ms)
            "verify_login": True,        # Verify login before scraping
            "auto_pagination": True,     # Automatically load pages without prompts
            "max_pages": 9999,           # Maximum pages to load automatically
            "page_delay_min": 3,         # Min delay between pages (seconds)
            "page_delay_max": 8,         # Max delay between pages (seconds)
            "pause_after_pages": 50,     # Pause after this many pages
            "pause_duration_min": 60,    # Min pause duration (seconds)
            "pause_duration_max": 120    # Max pause duration (seconds)
        },
        "explore": {
            "default_query": "news",
            "save_responses": True,     # Save all responses to files
            "response_dir": SCRAPED_DATA_DIR,
            "pagination_delay": 3000,
            "auto_pagination": True,     # Automatically load pages without prompts
            "infinite_pagination": True, # Continue until no more pages
            "max_pages": 999,            # Maximum pages (safety limit)
            "page_delay_min": 15,        # Min delay between pages (seconds)
            "page_delay_max": 30,        # Max delay between pages (seconds)
            "hourly_request_limit": 200, # Max requests per hour
            "pause_on_limit_minutes": 60, # Pause duration when limit reached
            "save_pagination_state": True # Save state to resume later
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
    },
    "automation": {
        "explore": {
            "enabled": True,
            "max_posts": 10,
            "max_posts_per_page": 20,
            "infinite_scroll": True,
            "pause_every_n_posts": 10,
            "pause_duration_min": 30,
            "pause_duration_max": 60,
            "actions": {
                "like": True,
                "comment": True
            }
        },
        "comments": {
            "pool": [
                "Amazing! 🔥",
                "Love this! ❤️",
                "Great content!",
                "👏👏👏",
                "Awesome!",
                "Nice! 💯",
                "Incredible!",
                "Fantastic post!",
                "So cool!",
                "This is great!"
            ],
            "use_random": True,
            "cycle_comments": False
        },
        "delays": {
            "between_posts_min": 8,
            "between_posts_max": 20,
            "between_actions_min": 3,
            "between_actions_max": 8,
            "between_pages_min": 15,
            "between_pages_max": 30,
            "page_load_wait": 7
        },
        "limits": {
            "max_likes_per_session": 500,
            "max_comments_per_session": 300,
            "stop_on_error": False,
            "max_consecutive_errors": 5
        }
    }
}
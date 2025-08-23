"""Environment configuration for Docker deployment only."""
import os
from pathlib import Path

# Docker paths are fixed
BASE_DIR = Path('/app')
CREDENTIALS_PATH = BASE_DIR / 'data' / 'credentials.json'
BROWSER_SESSIONS_DIR = BASE_DIR / 'data' / 'browser_sessions'
ACTION_LOGS_DIR = BASE_DIR / 'data' / 'action_logs'
SCRAPED_DATA_DIR = BASE_DIR / 'data' / 'scraped_data'
API_RESPONSES_DIR = BASE_DIR / 'data' / 'api_responses'
LOGS_DIR = BASE_DIR / 'data' / 'logs'

# Ensure all directories exist
for directory in [BROWSER_SESSIONS_DIR, ACTION_LOGS_DIR, SCRAPED_DATA_DIR, API_RESPONSES_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Display configuration for Playwright in Docker
DISPLAY = os.environ.get('DISPLAY', ':99')

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'instagram-mariadb'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'instagram_root_pwd'),
    'database': os.environ.get('DB_NAME', 'instagram_db')
}

# Always headless in Docker (no X server)
HEADLESS_MODE = True  # Docker requires headless mode
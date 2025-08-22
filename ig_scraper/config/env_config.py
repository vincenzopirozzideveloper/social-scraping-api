"""Environment configuration for Docker deployment."""
import os
from pathlib import Path

# Auto-detect if running in Docker (no env var needed)
def detect_docker():
    """Auto-detect if running inside Docker container"""
    try:
        # Check for Docker-specific files/conditions
        return (
            os.path.exists('/.dockerenv') or  # Docker creates this file
            os.path.exists('/proc/1/cgroup') and 'docker' in open('/proc/1/cgroup').read() or
            os.environ.get('container') is not None  # Some Docker images set this
        )
    except:
        return False

IS_DOCKER = detect_docker()

# ALWAYS use the bound/mounted directories (current working directory relative)
BASE_DIR = Path.cwd()  # Always /var/www/app in your Docker setup
default_credentials = BASE_DIR / 'credentials.json'
default_browser_sessions = BASE_DIR / 'browser_sessions'
default_action_logs = BASE_DIR / 'action_logs'
default_scraped_data = BASE_DIR / 'scraped_data'
default_api_responses = BASE_DIR / 'api_responses'
default_logs = BASE_DIR / 'logs'

# Path configurations from environment variables or intelligent defaults
CREDENTIALS_PATH = Path(os.environ.get('IG_CREDENTIALS_PATH', default_credentials))
BROWSER_SESSIONS_DIR = Path(os.environ.get('IG_BROWSER_SESSIONS_DIR', default_browser_sessions))
ACTION_LOGS_DIR = Path(os.environ.get('IG_ACTION_LOGS_DIR', default_action_logs))
SCRAPED_DATA_DIR = Path(os.environ.get('IG_SCRAPED_DATA_DIR', default_scraped_data))
API_RESPONSES_DIR = Path(os.environ.get('IG_API_RESPONSES_DIR', default_api_responses))
LOGS_DIR = Path(os.environ.get('IG_LOGS_DIR', default_logs))

# Ensure all directories exist
for directory in [BROWSER_SESSIONS_DIR, ACTION_LOGS_DIR, SCRAPED_DATA_DIR, API_RESPONSES_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Display configuration (for non-headless mode in Docker)
DISPLAY = os.environ.get('DISPLAY', ':99')

# Database configuration for MariaDB integration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'instagram-mariadb'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'instagram_user'),
    'password': os.environ.get('DB_PASSWORD', 'instagram_pwd'),
    'database': os.environ.get('DB_NAME', 'instagram_db')
}

# Docker-specific configurations - auto headless in Docker
HEADLESS_MODE = IS_DOCKER  # True in Docker, False locally
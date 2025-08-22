# Instagram Scraper & Automation Tool

A professional Instagram automation tool built with Playwright in Python, featuring multi-profile support, GraphQL interception, and configurable automation actions.

## Features

- 🔐 **Multi-Profile Management** - Manage multiple Instagram accounts
- 🤖 **2FA Support** - Automatic handling with backup codes
- 📊 **Data Scraping** - Following, followers, explore search
- ⚡ **Batch Actions** - Follow/unfollow automation
- ⚙️ **Configurable** - Per-profile configuration system
- 📝 **Logging** - Comprehensive action and response logging

## Installation

```bash
# Clone the repository
git clone https://github.com/vincenzopirozzideveloper/social-scraping-api.git
cd social-scraping-api

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Quick Start

1. Create `credentials.json`:
```json
{
  "email": "your_email@example.com",
  "password": "your_password",
  "backup-code": ["12345678", "87654321"]
}
```

2. Run the main program:
```bash
python main.py
```

## Configuration System

Each profile has its own configuration file stored in `browser_sessions/profiles/{username}/config.json`. You can manage configurations using the CLI tool.

### CLI Configuration Commands

#### View Configuration

```bash
# Show all configuration for a profile
python cli.py config:show

# Show specific section
python cli.py config:show --section scraping

# Show configuration for specific profile
python cli.py config:show --profile username
```

#### Get/Set Values

```bash
# Get a specific value
python cli.py config:get scraping.following.max_count

# Set a value
python cli.py config:set scraping.following.max_count 200

# Set for specific profile
python cli.py config:set scraping.following.max_count 150 --profile username
```

#### Manage Configurations

```bash
# List all available configuration keys
python cli.py config:list

# Reset to default configuration
python cli.py config:reset

# Export configuration
python cli.py config:export --output my_config.json

# Import configuration
python cli.py config:import --file my_config.json
```

### Configuration Options

#### Scraping Settings

| Key | Default | Description |
|-----|---------|-------------|
| `scraping.following.max_count` | 200 | Maximum users per request (Instagram limit) |
| `scraping.following.default_count` | 12 | Default count if not specified |
| `scraping.following.pagination_delay` | 3000 | Delay between pagination requests (ms) |
| `scraping.explore.default_query` | "news" | Default search query |
| `scraping.explore.save_responses` | true | Save all responses to files |

#### Action Settings

| Key | Default | Description |
|-----|---------|-------------|
| `actions.rate_limiting.min_delay` | 2 | Minimum seconds between actions |
| `actions.rate_limiting.max_delay` | 5 | Maximum seconds between actions |
| `actions.unfollow.batch_size` | 50 | Users to unfollow per batch |
| `actions.unfollow.pause_between_batches` | 30 | Seconds between batches |
| `actions.unfollow.safe_list` | [] | Users to never unfollow |
| `actions.unfollow.auto_confirm` | false | Skip confirmation prompts |
| `actions.unfollow.daily_limit` | 200 | Maximum unfollows per day |

#### Browser Settings

| Key | Default | Description |
|-----|---------|-------------|
| `browser.headless` | false | Run browser in headless mode |
| `browser.viewport.width` | 1920 | Browser viewport width |
| `browser.viewport.height` | 1080 | Browser viewport height |
| `browser.timeout` | 30000 | Default timeout (ms) |

#### Safety Settings

| Key | Default | Description |
|-----|---------|-------------|
| `safety.confirm_destructive` | true | Ask confirmation for destructive actions |
| `safety.dry_run` | false | Simulate actions without executing |
| `safety.max_batch_size` | 50 | Maximum items in batch operations |
| `safety.stop_on_error` | false | Stop batch on first error |

### Configuration Examples

#### Set up for aggressive unfollowing
```bash
# Increase batch size
python cli.py config:set actions.unfollow.batch_size 100

# Reduce pause between batches
python cli.py config:set actions.unfollow.pause_between_batches 10

# Skip confirmation
python cli.py config:set actions.unfollow.auto_confirm true

# Use maximum scraping limit
python cli.py config:set scraping.following.max_count 200
```

#### Set up safe list
```bash
# Add users to never unfollow (JSON array format)
python cli.py config:set actions.unfollow.safe_list '["friend1", "friend2", "important_account"]'
```

#### Configure for slower, safer operation
```bash
# Increase delays
python cli.py config:set actions.rate_limiting.min_delay 5
python cli.py config:set actions.rate_limiting.max_delay 10

# Smaller batches
python cli.py config:set actions.unfollow.batch_size 20

# Longer pauses
python cli.py config:set actions.unfollow.pause_between_batches 60
```

## Main Program Options

1. **Login** - Login to Instagram (new or add profile)
2. **Login with saved session** - Use existing session
3. **Clear saved sessions** - Remove saved profiles
4. **First Automation** - Test GraphQL connection
5. **Scrape Following** - Get following list
6. **Explore Search** - Search and scrape explore
7. **Massive Unfollow** - Unfollow all (except safe list)

## Project Structure

```
scraper-3/
├── main.py                 # Main entry point
├── cli.py                  # Configuration CLI tool
├── credentials.json        # Login credentials (gitignored)
├── ig_scraper/            
│   ├── api/               # API endpoints and GraphQL
│   ├── auth/              # Authentication and sessions
│   ├── actions/           # Automation actions (follow/unfollow)
│   ├── config/            # Configuration management
│   └── scrapers/          # Data scrapers
├── browser_sessions/      # Saved sessions and configs
│   └── profiles/          
│       └── {username}/    
│           ├── state.json # Browser state
│           └── config.json # User configuration
└── action_logs/           # Action logs (gitignored)
```

## Security Notes

- Never commit `credentials.json`
- Browser sessions are stored locally
- Action logs contain sensitive data
- Use safe list to protect important accounts
- Configure rate limits to avoid detection

## Development

The project uses:
- **Playwright** for browser automation
- **GraphQL interception** for API calls
- **Cookie-based session persistence**
- **Modular architecture** for extensibility

## License

Private repository - All rights reserved
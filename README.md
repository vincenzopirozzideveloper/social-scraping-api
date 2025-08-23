# Instagram Scraper

Professional Instagram automation tool built with Playwright and Python, designed for Docker deployment with MariaDB integration.

## 🚀 Features

- **Browser Automation**: Full Instagram browser automation using Playwright
- **Database Integration**: Complete MariaDB/MySQL database for session and data persistence
- **Session Management**: Save and reuse browser sessions across restarts
- **API Integration**: Direct GraphQL API calls for efficient data retrieval
- **Automation Suite**:
  - Profile following/unfollowing
  - Explore page automation (like & comment)
  - Following list scraping
  - Rate limiting and safety controls

## 📋 Prerequisites

- Docker & Docker Compose
- MariaDB/MySQL database
- Instagram account credentials

## 🛠️ Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd scraper-3
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

3. Start with Docker Compose:
```bash
docker-compose up -d
```

## 🗄️ Database Setup

Run migrations to set up the database schema:
```bash
docker exec -it instagram_scraper python migrate.py migrate
```

Check migration status:
```bash
docker exec -it instagram_scraper python migrate.py status
```

## 📝 Configuration

All configuration is centralized in `ig_scraper/config/defaults.py`. Key settings include:
- Rate limiting (delays between actions)
- Daily/hourly action limits
- Automation parameters (max posts, comments pool, etc.)

## 🎮 Usage

Access the interactive CLI menu:
```bash
docker exec -it instagram_scraper python main.py
```

### Menu Options:
1. **Login** - Authenticate with Instagram
2. **Login with saved session** - Use existing session
3. **Scrape Following** - Export following list
4. **Explore Automation** - Like & comment on explore posts
5. **Massive Unfollow** - Bulk unfollow users
6. **Browser Status** - Check active browsers

## 🏗️ Project Structure

```
scraper-3/
├── main.py                  # Entry point
├── docker-compose.yml       # Docker configuration
├── ig_scraper/
│   ├── actions/            # Action implementations
│   ├── api/                # API clients and endpoints
│   ├── auth/               # Authentication and sessions
│   ├── automation/         # Automation workflows
│   ├── browser/            # Browser management
│   ├── cli/                # CLI interface
│   ├── config/             # Configuration management
│   ├── database/           # Database layer
│   │   ├── migrations/     # Database migrations
│   │   └── utils/          # Database utilities
│   └── scrapers/           # Data scrapers
└── networks/               # API request/response examples
```

## 🔒 Security

- Credentials stored in database (encrypted cookies)
- Rate limiting to avoid detection
- Configurable delays between actions
- Session persistence for stability

## 🐳 Docker Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Access container shell
docker exec -it instagram_scraper bash

# Run migrations
docker exec -it instagram_scraper python migrate.py migrate
```

## 📊 Database Schema

The application uses MariaDB with the following main tables:
- `profiles` - Instagram account profiles
- `browser_sessions` - Saved browser sessions
- `posts_processed` - Automation tracking
- `following` - Following relationships
- `automation_sessions` - Automation session logs
- `api_requests` - API request/response logging

## ⚙️ Environment Variables

```env
DB_HOST=instagram-mariadb
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=instagram_db
DISPLAY=:99
HEADLESS_MODE=false
TZ=Europe/Rome
```

## 📝 License

Private project - All rights reserved

## 🤝 Contributing

This is a private project. Please contact the maintainers for access.
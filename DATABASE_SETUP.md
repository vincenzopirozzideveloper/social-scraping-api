# Database Setup Guide

## Prerequisites
- MariaDB/MySQL installed and running
- Python packages: `pymysql`, `python-dotenv`

## Configuration

1. **Create `.env` file from template:**
```bash
cp .env.example .env
```

2. **Edit `.env` with your database credentials:**
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=instagram_scraper
```

## Setup Steps

### 1. Test Database Connection
First, verify your database connection is working:
```bash
python test_db_connection.py
```

This will:
- Connect to MariaDB server
- Create the database if it doesn't exist
- Create initial tables
- Insert test data

### 2. Migrate Existing Sessions
If you have existing sessions in `browser_sessions/` directory:
```bash
python migrate_to_database.py
```

This will:
- Import all saved sessions to database
- Preserve cookies and GraphQL metadata
- Keep original files as backup

### 3. Run the Application
The application now automatically uses the database:
```bash
python main.py
```

## Database Schema

### Main Tables:

1. **profiles** - Instagram accounts
   - username, user_id, full_name, bio
   - follower_count, following_count, media_count

2. **browser_sessions** - Authentication sessions
   - session_data (JSON)
   - cookies (JSON)
   - graphql_metadata (JSON)
   - csrf_token, app_id

3. **following** - Following/followers tracking
   - target_user_id, target_username
   - is_following, unfollowed_at

4. **posts_processed** - Automation tracking
   - media_id, media_code
   - is_liked, is_commented

5. **comments_made** - Comments history
   - comment_id, comment_text
   - media_id, comment_url

6. **automation_sessions** - Session logs
   - session_type, total_processed
   - successful, failed

7. **action_logs** - Detailed action logging
   - action_type, target_id
   - success, error_message

## Troubleshooting

### Connection Issues
- Check MariaDB is running: `sudo systemctl status mariadb`
- Verify credentials in `.env`
- Check firewall settings for port 3306

### Docker Users
If using Docker, set in `.env`:
```env
DB_HOST=mariadb  # or your container name
IS_DOCKER=true
```

### Permission Issues
```sql
GRANT ALL PRIVILEGES ON instagram_scraper.* TO 'your_user'@'localhost';
FLUSH PRIVILEGES;
```

## Benefits of Database Storage

✅ **Persistent Sessions** - Never lose login sessions
✅ **Multi-Profile Support** - Manage multiple accounts
✅ **Action History** - Track all automation actions
✅ **Analytics Ready** - SQL queries for insights
✅ **Scalable** - Handle large data volumes
✅ **Backup Friendly** - Easy database backups

## Useful Queries

### View all profiles:
```sql
SELECT * FROM profiles;
```

### Check active sessions:
```sql
SELECT p.username, bs.last_used, bs.is_active 
FROM browser_sessions bs 
JOIN profiles p ON bs.profile_id = p.id 
WHERE bs.is_active = TRUE;
```

### Recent actions:
```sql
SELECT * FROM action_logs 
ORDER BY created_at DESC 
LIMIT 20;
```

### Automation statistics:
```sql
SELECT 
    session_type,
    COUNT(*) as sessions,
    SUM(successful) as total_success,
    SUM(failed) as total_failed
FROM automation_sessions
GROUP BY session_type;
```
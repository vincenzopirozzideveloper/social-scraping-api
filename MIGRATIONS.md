# Database Migrations System

## Overview
Professional database migration system for managing schema changes with version control, rollback support, and detailed tracking.

## Quick Start

### 1. Run All Migrations
```bash
python migrate.py migrate
```

### 2. Check Migration Status
```bash
python migrate.py status
```

### 3. Create New Migration
```bash
python migrate.py create --name "add_user_preferences"
```

### 4. Rollback to Version
```bash
python migrate.py rollback --version 002
```

## Directory Structure
```
migrations/
├── __init__.py
├── migration.py                    # Base migration class
├── 001_initial_schema.py          # Initial database schema
├── 002_add_missing_columns.py     # Add profile_id to action_logs
├── 003_add_request_tracking.py    # Add request tracking tables
└── ...                            # Your custom migrations
```

## Migration File Format

Each migration file follows the pattern: `XXX_description.py` where XXX is a 3-digit version number.

### Example Migration
```python
from migration import Migration

class AddUserPreferences(Migration):
    def get_version(self) -> str:
        return "004"
    
    def get_description(self) -> str:
        return "Add user preferences table"
    
    def up(self, cursor) -> None:
        """Apply migration"""
        cursor.execute("""
            CREATE TABLE user_preferences (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT NOT NULL,
                setting_name VARCHAR(100),
                setting_value TEXT,
                FOREIGN KEY (profile_id) REFERENCES profiles(id)
            )
        """)
    
    def down(self, cursor) -> None:
        """Rollback migration"""
        cursor.execute("DROP TABLE IF EXISTS user_preferences")
```

## Features

### ✅ Version Control
- Sequential version numbers (001, 002, 003...)
- Automatic version tracking in `schema_migrations` table
- Checksum validation to detect changes

### ✅ Safe Operations
- Transactional migrations (all or nothing)
- Rollback support for every migration
- Detailed error reporting

### ✅ Migration Tracking
```sql
-- View applied migrations
SELECT * FROM schema_migrations ORDER BY version;

-- Check migration history
SELECT version, description, applied_at, execution_time_ms 
FROM schema_migrations 
ORDER BY applied_at DESC;
```

### ✅ Professional Features
- **Idempotent**: Safe to run multiple times
- **Atomic**: Each migration in a transaction
- **Reversible**: Every `up()` has a `down()`
- **Tracked**: Execution time and checksum stored

## Common Commands

### Apply Specific Version
```bash
# Migrate up to version 002
python migrate.py migrate --version 002
```

### Force Migration (ignore checksum)
```bash
python migrate.py migrate --force
```

### Create Custom Migration
```bash
# Creates next version automatically
python migrate.py create --name "add_analytics_tables"
```

## Migration Status Output
```
================================================================================
MIGRATION STATUS
================================================================================
Database: instagram_scraper
Applied migrations: 3
================================================================================

APPLIED MIGRATIONS:
  ✅ 001: Create initial database schema
     Applied: 2024-01-15 10:30:00 (245ms)
  ✅ 002: Add missing columns to action_logs
     Applied: 2024-01-15 10:30:01 (125ms)
  ✅ 003: Add request/response tracking tables
     Applied: 2024-01-15 10:30:02 (189ms)

⏳ PENDING MIGRATIONS (1):
  ⏸  004: Add user preferences table
================================================================================
```

## Best Practices

### 1. Always Test Rollbacks
```python
def down(self, cursor):
    # Make sure this actually reverses the up() method
    cursor.execute("DROP TABLE IF EXISTS new_table")
```

### 2. Use IF NOT EXISTS
```python
def up(self, cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS new_table (...)
    """)
```

### 3. Check Before Altering
```python
def up(self, cursor):
    # Check if column exists before adding
    cursor.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'table_name' 
        AND COLUMN_NAME = 'new_column'
    """)
    if cursor.fetchone()[0] == 0:
        cursor.execute("ALTER TABLE table_name ADD COLUMN new_column VARCHAR(255)")
```

### 4. Provide Feedback
```python
def up(self, cursor):
    cursor.execute("CREATE TABLE new_table (...)")
    print("  ✓ Created new_table")
```

## Troubleshooting

### Migration Failed
1. Check error message for SQL syntax
2. Fix the migration file
3. Run again (migrations are transactional)

### Checksum Mismatch
```bash
# Force if you're sure the change is safe
python migrate.py migrate --force
```

### Stuck Migration
```sql
-- Manually remove from tracking
DELETE FROM schema_migrations WHERE version = '003';
```

### Reset Everything
```sql
-- BE CAREFUL: This removes migration tracking
DROP TABLE schema_migrations;
-- Then run migrations again
```

## Integration with Application

The migration system is automatically used by:
- `apply_schema.py` - Now deprecated, use `migrate.py` instead
- Application startup can check migration status
- CI/CD can run migrations automatically

## Database Compatibility

Works with:
- MariaDB 10.3+
- MySQL 5.7+
- Percona Server

## Security Notes

- Migrations run with full database privileges
- Store sensitive data in `.env`, not in migrations
- Review migrations before applying in production
- Keep backups before major schema changes
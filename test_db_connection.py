#!/usr/bin/env python3
"""Test MariaDB connection and create database if needed"""

import os
import sys
import pymysql
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path('.env')
if not env_path.exists():
    print("❌ .env file not found!")
    print("Please create a .env file with database credentials")
    print("You can copy .env.example as a template:")
    print("  cp .env.example .env")
    sys.exit(1)

load_dotenv()

# Database configuration from environment
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
}

DB_NAME = os.getenv('DB_NAME', 'instagram_scraper')

def test_connection():
    """Test connection to MariaDB server"""
    print("="*50)
    print("TESTING MARIADB CONNECTION")
    print("="*50)
    print(f"Host: {DB_CONFIG['host']}")
    print(f"Port: {DB_CONFIG['port']}")
    print(f"User: {DB_CONFIG['user']}")
    print(f"Password: {'*' * len(DB_CONFIG['password']) if DB_CONFIG['password'] else '(empty)'}")
    print("="*50)
    
    try:
        # Connect without database first
        print("\n1. Connecting to MariaDB server...")
        connection = pymysql.connect(**DB_CONFIG)
        print("✅ Successfully connected to MariaDB server!")
        
        # Get server info
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            print(f"   Server version: {version}")
            
            cursor.execute("SELECT USER()")
            current_user = cursor.fetchone()[0]
            print(f"   Connected as: {current_user}")
        
        return connection
        
    except pymysql.err.OperationalError as e:
        print(f"❌ Failed to connect to MariaDB server!")
        print(f"   Error: {e}")
        print("\nPossible issues:")
        print("1. MariaDB server is not running")
        print("2. Wrong host/port in .env file")
        print("3. Wrong username/password")
        print("4. Network connectivity issues")
        if 'docker' in DB_CONFIG['host'].lower() or DB_CONFIG['host'] == 'mariadb':
            print("5. Docker container name might be different")
            print("   Try: docker ps | grep mariadb")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

def create_database(connection):
    """Create database if it doesn't exist"""
    print(f"\n2. Checking database '{DB_NAME}'...")
    
    try:
        with connection.cursor() as cursor:
            # Check if database exists
            cursor.execute("SHOW DATABASES")
            databases = [db[0] for db in cursor.fetchall()]
            
            if DB_NAME in databases:
                print(f"✅ Database '{DB_NAME}' already exists")
            else:
                print(f"   Database '{DB_NAME}' not found, creating...")
                cursor.execute(f"CREATE DATABASE `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                print(f"✅ Database '{DB_NAME}' created successfully!")
                connection.commit()
            
            # Switch to the database
            cursor.execute(f"USE `{DB_NAME}`")
            print(f"✅ Switched to database '{DB_NAME}'")
            
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False

def create_tables(connection):
    """Create tables for Instagram scraper"""
    print("\n3. Creating tables...")
    
    tables = {
        'profiles': """
            CREATE TABLE IF NOT EXISTS profiles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                user_id VARCHAR(50),
                full_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_username (username),
                INDEX idx_user_id (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        'posts_processed': """
            CREATE TABLE IF NOT EXISTS posts_processed (
                id INT AUTO_INCREMENT PRIMARY KEY,
                media_id VARCHAR(100) UNIQUE NOT NULL,
                media_code VARCHAR(50),
                owner_username VARCHAR(100),
                action_type ENUM('like', 'comment', 'both') NOT NULL,
                success BOOLEAN DEFAULT TRUE,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                profile_id INT,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                INDEX idx_media_id (media_id),
                INDEX idx_processed_at (processed_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        'comments_made': """
            CREATE TABLE IF NOT EXISTS comments_made (
                id INT AUTO_INCREMENT PRIMARY KEY,
                comment_id VARCHAR(100) UNIQUE,
                media_id VARCHAR(100) NOT NULL,
                media_code VARCHAR(50),
                comment_text TEXT NOT NULL,
                comment_url VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                profile_id INT,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                INDEX idx_comment_id (comment_id),
                INDEX idx_media_id (media_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        'automation_sessions': """
            CREATE TABLE IF NOT EXISTS automation_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT,
                search_query VARCHAR(255),
                posts_processed INT DEFAULT 0,
                likes_count INT DEFAULT 0,
                comments_count INT DEFAULT 0,
                errors_count INT DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP NULL,
                status ENUM('running', 'completed', 'error', 'stopped') DEFAULT 'running',
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                INDEX idx_started_at (started_at),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        'action_logs': """
            CREATE TABLE IF NOT EXISTS action_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id INT,
                action_type VARCHAR(50) NOT NULL,
                target_id VARCHAR(100),
                target_username VARCHAR(100),
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                response_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES automation_sessions(id) ON DELETE CASCADE,
                INDEX idx_session_id (session_id),
                INDEX idx_action_type (action_type),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    }
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"USE `{DB_NAME}`")
            
            for table_name, create_sql in tables.items():
                print(f"   Creating table '{table_name}'...")
                cursor.execute(create_sql)
                print(f"   ✅ Table '{table_name}' ready")
            
            connection.commit()
            print("\n✅ All tables created successfully!")
            
            # Show created tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"\nTables in database '{DB_NAME}':")
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM `{table[0]}`")
                count = cursor.fetchone()[0]
                print(f"   - {table[0]}: {count} records")
            
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

def test_insert_sample_data(connection):
    """Test inserting sample data"""
    print("\n4. Testing data insertion...")
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"USE `{DB_NAME}`")
            
            # Insert a test profile
            cursor.execute("""
                INSERT INTO profiles (username, user_id, full_name)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP
            """, ('test_user', '123456789', 'Test User'))
            
            profile_id = cursor.lastrowid or 1
            
            # Insert a test session
            cursor.execute("""
                INSERT INTO automation_sessions (profile_id, search_query, posts_processed, likes_count, comments_count)
                VALUES (%s, %s, %s, %s, %s)
            """, (profile_id, 'test_query', 5, 3, 2))
            
            connection.commit()
            print("✅ Sample data inserted successfully!")
            
            # Query the data back
            cursor.execute("SELECT * FROM profiles WHERE username = 'test_user'")
            profile = cursor.fetchone()
            print(f"   Test profile: {profile}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error inserting sample data: {e}")
        return False

def main():
    """Main test function"""
    print("\n🔧 MARIADB CONNECTION TEST SCRIPT")
    print("="*50)
    
    # Test connection
    connection = test_connection()
    if not connection:
        print("\n❌ Connection test failed. Please check your configuration.")
        sys.exit(1)
    
    # Create database
    if not create_database(connection):
        connection.close()
        print("\n❌ Database creation failed.")
        sys.exit(1)
    
    # Create tables
    if not create_tables(connection):
        connection.close()
        print("\n❌ Table creation failed.")
        sys.exit(1)
    
    # Test data insertion
    test_insert_sample_data(connection)
    
    # Close connection
    connection.close()
    
    print("\n="*50)
    print("✅ ALL TESTS PASSED!")
    print("="*50)
    print("\nDatabase is ready for use!")
    print(f"Connection string: mysql://{DB_CONFIG['user']}:****@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_NAME}")
    print("\nYou can now integrate this database with your Instagram scraper.")

if __name__ == "__main__":
    main()
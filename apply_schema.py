#!/usr/bin/env python3
"""Apply complete database schema - creates all required tables"""

import os
import sys
import pymysql
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path('.env')
if not env_path.exists():
    print("❌ .env file not found!")
    print("Please create a .env file with database credentials")
    print("You can copy .env.example as a template:")
    print("  cp .env.example .env")
    sys.exit(1)

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
}

DB_NAME = os.getenv('DB_NAME', 'instagram_scraper')

# Complete table definitions
TABLES = {
    'profiles': """
        CREATE TABLE IF NOT EXISTS profiles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            user_id VARCHAR(50),
            full_name VARCHAR(255),
            bio TEXT,
            follower_count INT DEFAULT 0,
            following_count INT DEFAULT 0,
            media_count INT DEFAULT 0,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_username (username),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    'browser_sessions': """
        CREATE TABLE IF NOT EXISTS browser_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            profile_id INT NOT NULL,
            session_data JSON NOT NULL,
            cookies JSON,
            graphql_metadata JSON,
            user_agent VARCHAR(500),
            csrf_token VARCHAR(100),
            app_id VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE,
            last_used TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            INDEX idx_profile_id (profile_id),
            INDEX idx_is_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    'following': """
        CREATE TABLE IF NOT EXISTS following (
            id INT AUTO_INCREMENT PRIMARY KEY,
            profile_id INT NOT NULL,
            target_user_id VARCHAR(50) NOT NULL,
            target_username VARCHAR(50) NOT NULL,
            target_full_name VARCHAR(255),
            is_verified BOOLEAN DEFAULT FALSE,
            is_following BOOLEAN DEFAULT TRUE,
            unfollowed_at TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            UNIQUE KEY unique_following (profile_id, target_user_id),
            INDEX idx_profile_following (profile_id, is_following),
            INDEX idx_target_username (target_username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    'posts_processed': """
        CREATE TABLE IF NOT EXISTS posts_processed (
            id INT AUTO_INCREMENT PRIMARY KEY,
            profile_id INT NOT NULL,
            media_id VARCHAR(100) NOT NULL,
            media_code VARCHAR(50),
            owner_username VARCHAR(50),
            caption TEXT,
            like_count INT DEFAULT 0,
            comment_count INT DEFAULT 0,
            is_liked BOOLEAN DEFAULT FALSE,
            is_commented BOOLEAN DEFAULT FALSE,
            action_type ENUM('like', 'comment', 'both'),
            success BOOLEAN DEFAULT TRUE,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            UNIQUE KEY unique_post (profile_id, media_id),
            INDEX idx_profile_posts (profile_id),
            INDEX idx_media_id (media_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    'comments_made': """
        CREATE TABLE IF NOT EXISTS comments_made (
            id INT AUTO_INCREMENT PRIMARY KEY,
            profile_id INT NOT NULL,
            media_id VARCHAR(100) NOT NULL,
            media_code VARCHAR(50),
            comment_id VARCHAR(100),
            comment_text TEXT NOT NULL,
            comment_url VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            INDEX idx_profile_comments (profile_id),
            INDEX idx_media_comments (media_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    'automation_sessions': """
        CREATE TABLE IF NOT EXISTS automation_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            profile_id INT NOT NULL,
            session_type VARCHAR(50) NOT NULL,
            search_query VARCHAR(255),
            total_processed INT DEFAULT 0,
            successful INT DEFAULT 0,
            failed INT DEFAULT 0,
            posts_processed INT DEFAULT 0,
            likes_count INT DEFAULT 0,
            comments_count INT DEFAULT 0,
            errors_count INT DEFAULT 0,
            metadata JSON,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP NULL,
            status ENUM('running', 'completed', 'error', 'stopped') DEFAULT 'running',
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            INDEX idx_profile_sessions (profile_id),
            INDEX idx_session_type (session_type),
            INDEX idx_started_at (started_at),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    'action_logs': """
        CREATE TABLE IF NOT EXISTS action_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            profile_id INT NOT NULL,
            session_id INT,
            action_type VARCHAR(50) NOT NULL,
            target_id VARCHAR(100),
            target_username VARCHAR(100),
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT,
            response_data JSON,
            metadata JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES automation_sessions(id) ON DELETE SET NULL,
            INDEX idx_profile_actions (profile_id),
            INDEX idx_session_actions (session_id),
            INDEX idx_action_type (action_type),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    'graphql_endpoints': """
        CREATE TABLE IF NOT EXISTS graphql_endpoints (
            id INT AUTO_INCREMENT PRIMARY KEY,
            profile_id INT NOT NULL,
            endpoint_name VARCHAR(100) NOT NULL,
            doc_id VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            UNIQUE KEY unique_endpoint (profile_id, endpoint_name),
            INDEX idx_profile_endpoints (profile_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
}

# Optional/Additional tables that might be needed
OPTIONAL_TABLES = {
    'following_fetches': """
        CREATE TABLE IF NOT EXISTS following_fetches (
            id INT AUTO_INCREMENT PRIMARY KEY,
            profile_id INT NOT NULL,
            fetch_type VARCHAR(50) NOT NULL,
            total_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            INDEX idx_profile_fetches (profile_id),
            INDEX idx_fetch_type (fetch_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    'following_data': """
        CREATE TABLE IF NOT EXISTS following_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            fetch_id INT NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            username VARCHAR(50) NOT NULL,
            full_name VARCHAR(255),
            is_private BOOLEAN DEFAULT FALSE,
            is_verified BOOLEAN DEFAULT FALSE,
            profile_pic_url VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (fetch_id) REFERENCES following_fetches(id) ON DELETE CASCADE,
            INDEX idx_fetch_id (fetch_id),
            INDEX idx_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
}

def apply_schema():
    """Apply the complete database schema"""
    print("="*60)
    print("APPLYING COMPLETE DATABASE SCHEMA")
    print("="*60)
    print(f"Server: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"Database: {DB_NAME}")
    print("="*60)
    
    conn = None
    try:
        # Connect to server
        conn = pymysql.connect(**DB_CONFIG)
        print(f"✓ Connected to MariaDB server")
        
        with conn.cursor() as cursor:
            # Create database if not exists
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute(f"USE `{DB_NAME}`")
            conn.commit()
            print(f"✓ Using database: {DB_NAME}")
            
            # Check existing tables
            cursor.execute("SHOW TABLES")
            existing_tables = [t[0] for t in cursor.fetchall()]
            
            if existing_tables:
                print(f"\nExisting tables found: {', '.join(existing_tables)}")
            else:
                print("\nNo existing tables found - creating fresh schema")
            
            # Create main tables
            print("\n" + "-"*60)
            print("Creating/Verifying Main Tables")
            print("-"*60)
            
            created_count = 0
            updated_count = 0
            
            for table_name, create_sql in TABLES.items():
                if table_name not in existing_tables:
                    print(f"  Creating table '{table_name}'...")
                    try:
                        cursor.execute(create_sql)
                        conn.commit()
                        print(f"  ✓ Table '{table_name}' created")
                        created_count += 1
                    except pymysql.err.OperationalError as e:
                        if 'already exists' in str(e).lower():
                            print(f"  ℹ Table '{table_name}' already exists")
                            updated_count += 1
                        else:
                            print(f"  ✗ Error creating '{table_name}': {e}")
                    except Exception as e:
                        print(f"  ✗ Error creating '{table_name}': {e}")
                else:
                    print(f"  ✓ Table '{table_name}' already exists")
                    updated_count += 1
            
            # Create optional tables
            print("\n" + "-"*60)
            print("Creating/Verifying Optional Tables")
            print("-"*60)
            
            for table_name, create_sql in OPTIONAL_TABLES.items():
                if table_name not in existing_tables:
                    print(f"  Creating optional table '{table_name}'...")
                    try:
                        cursor.execute(create_sql)
                        conn.commit()
                        print(f"  ✓ Optional table '{table_name}' created")
                        created_count += 1
                    except Exception as e:
                        print(f"  ℹ Optional table '{table_name}' skipped: {str(e)[:50]}")
                else:
                    print(f"  ✓ Optional table '{table_name}' already exists")
            
            # Final verification
            print("\n" + "="*60)
            print("VERIFICATION")
            print("="*60)
            
            cursor.execute("SHOW TABLES")
            all_tables = cursor.fetchall()
            
            print(f"\nAll tables in database '{DB_NAME}':")
            for table in all_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table[0]}`")
                    count = cursor.fetchone()[0]
                    
                    # Check table structure for key tables
                    if table[0] in ['profiles', 'browser_sessions', 'graphql_endpoints']:
                        cursor.execute(f"SHOW COLUMNS FROM `{table[0]}`")
                        columns = cursor.fetchall()
                        col_names = [col[0] for col in columns]
                        print(f"  - {table[0]}: {count} records ({len(columns)} columns)")
                    else:
                        print(f"  - {table[0]}: {count} records")
                except Exception as e:
                    print(f"  - {table[0]}: Error reading table")
            
            # Check if all required tables exist
            required_tables = [
                'profiles', 'browser_sessions', 'following',
                'posts_processed', 'comments_made', 
                'automation_sessions', 'action_logs', 'graphql_endpoints'
            ]
            
            existing_now = [t[0] for t in all_tables]
            missing_now = [t for t in required_tables if t not in existing_now]
            
            print("\n" + "="*60)
            if missing_now:
                print(f"⚠ WARNING: Missing required tables: {', '.join(missing_now)}")
                print("\nPlease check the error messages above.")
                return False
            else:
                print(f"✅ SUCCESS! All required tables exist")
                print(f"   Created: {created_count} new tables")
                print(f"   Existing: {updated_count} tables")
                print(f"   Total: {len(existing_now)} tables")
                return True
        
    except pymysql.err.OperationalError as e:
        print(f"\n❌ Database connection failed!")
        print(f"   Error: {e}")
        print("\nPossible issues:")
        print("1. MariaDB/MySQL server is not running")
        print("2. Wrong credentials in .env file")
        print("3. Database server not accessible")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False
    finally:
        if conn:
            conn.close()

def main():
    """Main entry point"""
    print("\n🔧 DATABASE SCHEMA APPLICATION")
    print("="*60)
    
    # Show configuration
    print("Configuration from .env:")
    print(f"  DB_HOST: {DB_CONFIG['host']}")
    print(f"  DB_PORT: {DB_CONFIG['port']}")
    print(f"  DB_USER: {DB_CONFIG['user']}")
    print(f"  DB_NAME: {DB_NAME}")
    print("="*60)
    
    if apply_schema():
        print("\n" + "="*60)
        print("✅ DATABASE READY!")
        print("="*60)
        print("\nNext steps:")
        print("1. Run: python migrate_to_database.py")
        print("   (if you have existing sessions to migrate)")
        print("\n2. Run: python main.py")
        print("   (to start using the application)")
    else:
        print("\n" + "="*60)
        print("❌ SCHEMA APPLICATION INCOMPLETE")
        print("="*60)
        print("\nPlease fix any errors and run this script again.")
        sys.exit(1)

if __name__ == "__main__":
    main()
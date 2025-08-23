#!/usr/bin/env python3
"""
Migration script to move browser_sessions files to MariaDB database
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

# Load environment variables (same as test_db_connection.py)
env_path = Path('.env')
if not env_path.exists():
    print("❌ .env file not found!")
    print("Please create a .env file with database credentials")
    print("You can copy .env.example as a template:")
    print("  cp .env.example .env")
    sys.exit(1)

load_dotenv()

# Database configuration from environment (same as test_db_connection.py)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'charset': 'utf8mb4',
    'cursorclass': DictCursor,
    'autocommit': False
}

DB_NAME = os.getenv('DB_NAME', 'instagram_scraper')

class SessionMigrator:
    def __init__(self):
        self.connection = None
        self.browser_sessions_dir = Path('browser_sessions')
        self.migrated_count = 0
        self.failed_count = 0
    
    def connect(self):
        """Connect to database"""
        try:
            # First connect without database (like test_db_connection.py)
            self.connection = pymysql.connect(**DB_CONFIG)
            print(f"✓ Connected to MariaDB server")
            
            # Create database if not exists
            with self.connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                cursor.execute(f"USE `{DB_NAME}`")
                self.connection.commit()
            
            print(f"✓ Using database: {DB_NAME}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to database: {e}")
            return False
    
    def create_schema(self):
        """Create database schema if not exists"""
        schema_file = Path('ig_scraper/database/schema.sql')
        if not schema_file.exists():
            print("✗ Schema file not found")
            return False
        
        try:
            with self.connection.cursor() as cursor:
                # Read and execute schema
                with open(schema_file, 'r') as f:
                    sql_commands = f.read().split(';')
                    for command in sql_commands:
                        if command.strip():
                            cursor.execute(command)
                self.connection.commit()
                print("✓ Database schema created/verified")
                return True
        except Exception as e:
            print(f"✗ Failed to create schema: {e}")
            self.connection.rollback()
            return False
    
    def get_or_create_profile(self, username: str) -> int:
        """Get or create profile and return its ID"""
        try:
            with self.connection.cursor() as cursor:
                # Check if profile exists
                cursor.execute("SELECT id FROM profiles WHERE username = %s", (username,))
                result = cursor.fetchone()
                
                if result:
                    return result['id']
                
                # Create new profile
                cursor.execute(
                    "INSERT INTO profiles (username) VALUES (%s)",
                    (username,)
                )
                self.connection.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"✗ Failed to get/create profile for {username}: {e}")
            self.connection.rollback()
            return None
    
    def migrate_session(self, session_file: Path) -> bool:
        """Migrate a single session to database"""
        try:
            # Read session info file
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            username = session_data.get('username')
            if not username:
                print(f"⚠ No username found in {session_file}")
                return False
            
            print(f"\nMigrating session for @{username}...")
            
            # Get or create profile
            profile_id = self.get_or_create_profile(username)
            if not profile_id:
                return False
            
            # Read state file if it exists
            state_file = session_data.get('state_file')
            cookies = None
            if state_file:
                # Convert Windows path to Unix path
                state_file = state_file.replace('\\', '/')
                state_path = Path(state_file)
                if state_path.exists():
                    with open(state_path, 'r') as f:
                        state_data = json.load(f)
                        cookies = state_data.get('cookies', [])
            
            # Prepare GraphQL metadata
            graphql_data = session_data.get('graphql', {})
            doc_ids = graphql_data.get('doc_ids', {})
            
            # Check if session already exists
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM browser_sessions WHERE profile_id = %s",
                    (profile_id,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing session
                    cursor.execute("""
                        UPDATE browser_sessions 
                        SET session_data = %s, 
                            cookies = %s,
                            graphql_metadata = %s,
                            user_agent = %s,
                            csrf_token = %s,
                            app_id = %s,
                            last_used = %s,
                            updated_at = NOW()
                        WHERE profile_id = %s
                    """, (
                        json.dumps(session_data),
                        json.dumps(cookies) if cookies else None,
                        json.dumps(doc_ids) if doc_ids else None,
                        graphql_data.get('user_agent'),
                        graphql_data.get('csrf_token'),
                        graphql_data.get('app_id'),
                        datetime.fromisoformat(session_data.get('last_saved', datetime.now().isoformat())),
                        profile_id
                    ))
                    print(f"  ✓ Updated existing session for @{username}")
                else:
                    # Insert new session
                    cursor.execute("""
                        INSERT INTO browser_sessions 
                        (profile_id, session_data, cookies, graphql_metadata, 
                         user_agent, csrf_token, app_id, last_used)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        profile_id,
                        json.dumps(session_data),
                        json.dumps(cookies) if cookies else None,
                        json.dumps(doc_ids) if doc_ids else None,
                        graphql_data.get('user_agent'),
                        graphql_data.get('csrf_token'),
                        graphql_data.get('app_id'),
                        datetime.fromisoformat(session_data.get('last_saved', datetime.now().isoformat()))
                    ))
                    print(f"  ✓ Created new session for @{username}")
                
                # Also save GraphQL endpoints separately
                if doc_ids:
                    for endpoint_name, doc_id in doc_ids.items():
                        cursor.execute("""
                            INSERT INTO graphql_endpoints (profile_id, endpoint_name, doc_id)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE doc_id = VALUES(doc_id)
                        """, (profile_id, endpoint_name, doc_id))
                    print(f"  ✓ Saved {len(doc_ids)} GraphQL endpoints")
                
                self.connection.commit()
                self.migrated_count += 1
                return True
                
        except Exception as e:
            print(f"✗ Failed to migrate {session_file}: {e}")
            self.connection.rollback()
            self.failed_count += 1
            return False
    
    def find_session_files(self) -> list:
        """Find all session info files"""
        session_files = []
        
        # Look for *_info.json files
        for file in self.browser_sessions_dir.glob('*_info.json'):
            session_files.append(file)
        
        # Also check profiles directory
        profiles_dir = self.browser_sessions_dir / 'profiles'
        if profiles_dir.exists():
            for profile_dir in profiles_dir.iterdir():
                if profile_dir.is_dir():
                    info_file = profile_dir / 'info.json'
                    if info_file.exists():
                        session_files.append(info_file)
        
        return session_files
    
    def run_migration(self):
        """Run the complete migration"""
        print("="*60)
        print("BROWSER SESSIONS TO DATABASE MIGRATION")
        print("="*60)
        
        # Connect to database
        if not self.connect():
            print("\n✗ Migration failed: Could not connect to database")
            print("\nPlease check your .env file has correct database credentials:")
            print("  DB_HOST=localhost")
            print("  DB_PORT=3306")
            print("  DB_USER=your_user")
            print("  DB_PASSWORD=your_password")
            print("  DB_NAME=instagram_scraper")
            return False
        
        # Create schema
        if not self.create_schema():
            print("\n✗ Migration failed: Could not create database schema")
            return False
        
        # Find session files
        session_files = self.find_session_files()
        
        if not session_files:
            print("\n⚠ No session files found to migrate")
            return True
        
        print(f"\nFound {len(session_files)} session(s) to migrate")
        print("-"*60)
        
        # Migrate each session
        for session_file in session_files:
            self.migrate_session(session_file)
        
        # Summary
        print("\n" + "="*60)
        print("MIGRATION COMPLETE")
        print("="*60)
        print(f"✓ Successfully migrated: {self.migrated_count}")
        if self.failed_count > 0:
            print(f"✗ Failed: {self.failed_count}")
        print("="*60)
        
        # Close connection
        if self.connection:
            self.connection.close()
        
        return self.failed_count == 0
    
    def verify_migration(self):
        """Verify migration was successful"""
        if not self.connection or not self.connection.open:
            self.connect()
        
        try:
            with self.connection.cursor() as cursor:
                # Use database
                cursor.execute(f"USE `{DB_NAME}`")
                
                # Count profiles
                cursor.execute("SELECT COUNT(*) as count FROM profiles")
                profiles = cursor.fetchone()['count']
                
                # Count sessions
                cursor.execute("SELECT COUNT(*) as count FROM browser_sessions")
                sessions = cursor.fetchone()['count']
                
                # Count GraphQL endpoints
                cursor.execute("SELECT COUNT(*) as count FROM graphql_endpoints")
                endpoints = cursor.fetchone()['count']
                
                print("\n" + "="*60)
                print("DATABASE STATUS")
                print("="*60)
                print(f"Profiles: {profiles}")
                print(f"Browser Sessions: {sessions}")
                print(f"GraphQL Endpoints: {endpoints}")
                print("="*60)
                
                # List profiles
                cursor.execute("SELECT username, created_at FROM profiles")
                profiles_list = cursor.fetchall()
                if profiles_list:
                    print("\nProfiles in database:")
                    for profile in profiles_list:
                        print(f"  - @{profile['username']} (added: {profile['created_at']})")
                
        except Exception as e:
            print(f"✗ Failed to verify migration: {e}")


def main():
    """Main entry point"""
    migrator = SessionMigrator()
    
    # Check if database is accessible first
    print("Checking database connection...")
    if not migrator.connect():
        sys.exit(1)
    migrator.connection.close()
    
    # Ask for confirmation
    print("\n" + "⚠"*30)
    print("WARNING: This will migrate browser sessions to database")
    print("⚠"*30)
    
    choice = input("\nDo you want to continue? (yes/no): ")
    if choice.lower() != 'yes':
        print("Migration cancelled")
        return
    
    # Run migration
    success = migrator.run_migration()
    
    # Verify
    if success:
        migrator.verify_migration()
        print("\n✓ Migration successful!")
        print("\nYour sessions are now stored in the database.")
        print("The original files are still in browser_sessions/ as backup.")
    else:
        print("\n✗ Migration had errors. Please check the output above.")
    
    # Cleanup
    if migrator.connection:
        migrator.connection.close()


if __name__ == '__main__':
    main()
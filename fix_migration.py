#!/usr/bin/env python3
"""Fix migration issue with action_logs table"""

import os
import sys
import pymysql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'instagram_scraper')
}

def fix_database():
    """Fix the action_logs table issue"""
    conn = None
    try:
        # Connect to database
        conn = pymysql.connect(**DB_CONFIG)
        print(f"✓ Connected to database: {DB_CONFIG['database']}")
        
        with conn.cursor() as cursor:
            # Check current state
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'action_logs' 
                AND COLUMN_NAME = 'profile_id'
                AND TABLE_SCHEMA = DATABASE()
            """)
            has_profile_id = cursor.fetchone()[0] > 0
            
            if has_profile_id:
                print("✓ profile_id column exists in action_logs")
                
                # Check if it's nullable
                cursor.execute("""
                    SELECT IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'action_logs' 
                    AND COLUMN_NAME = 'profile_id'
                    AND TABLE_SCHEMA = DATABASE()
                """)
                is_nullable = cursor.fetchone()[0] == 'YES'
                
                if is_nullable:
                    print("  → profile_id is nullable, fixing data...")
                    
                    # Count NULL values
                    cursor.execute("SELECT COUNT(*) FROM action_logs WHERE profile_id IS NULL")
                    null_count = cursor.fetchone()[0]
                    
                    if null_count > 0:
                        print(f"  → Found {null_count} rows with NULL profile_id")
                        
                        # Try to fix from sessions
                        cursor.execute("""
                            UPDATE action_logs al
                            JOIN automation_sessions s ON al.session_id = s.id
                            SET al.profile_id = s.profile_id
                            WHERE al.profile_id IS NULL AND al.session_id IS NOT NULL
                        """)
                        fixed_from_sessions = cursor.rowcount
                        print(f"  ✓ Fixed {fixed_from_sessions} rows using session data")
                        
                        # Check again for NULL values
                        cursor.execute("SELECT COUNT(*) FROM action_logs WHERE profile_id IS NULL")
                        null_count = cursor.fetchone()[0]
                        
                        if null_count > 0:
                            # Get or create a default profile
                            cursor.execute("SELECT id FROM profiles LIMIT 1")
                            profile = cursor.fetchone()
                            
                            if profile:
                                cursor.execute("""
                                    UPDATE action_logs 
                                    SET profile_id = %s
                                    WHERE profile_id IS NULL
                                """, (profile[0],))
                                print(f"  ✓ Set default profile for {cursor.rowcount} orphan rows")
                            else:
                                # Delete orphan rows
                                cursor.execute("DELETE FROM action_logs WHERE profile_id IS NULL")
                                print(f"  ⚠ Deleted {cursor.rowcount} orphan rows (no profiles exist)")
                    
                    # Now make it NOT NULL
                    cursor.execute("""
                        ALTER TABLE action_logs 
                        MODIFY COLUMN profile_id INT NOT NULL
                    """)
                    print("  ✓ Made profile_id NOT NULL")
                    
                    conn.commit()
                    print("\n✅ Database fixed successfully!")
                else:
                    print("  ✓ profile_id is already NOT NULL")
            else:
                print("⚠ profile_id column doesn't exist yet")
                print("  This is expected if migration 002 hasn't run yet")
            
            # Update migration status
            cursor.execute("""
                UPDATE schema_migrations 
                SET checksum = NULL
                WHERE version = '002'
            """)
            if cursor.rowcount > 0:
                print("\n✓ Reset migration 002 checksum")
                conn.commit()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def main():
    print("="*60)
    print("FIX MIGRATION ISSUE")
    print("="*60)
    
    fix_database()
    
    print("\n" + "="*60)
    print("Next steps:")
    print("1. Run: python migrate.py migrate")
    print("2. This should complete migration 002 successfully")
    print("="*60)

if __name__ == "__main__":
    main()
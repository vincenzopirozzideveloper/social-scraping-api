"""Add browser locks and rate limiting tables"""

from .base import Migration


class AddBrowserLocksAndRateLimiting(Migration):
    """Add tables for browser lock management and request rate limiting"""
    
    def get_version(self) -> str:
        return "010"
    
    def get_description(self) -> str:
        return "Add browser locks and hourly request tracking"
    
    def up(self, cursor) -> None:
        """Create browser locks and rate limiting tables"""
        
        # 1. Create browser_locks table
        print("    → Creating browser_locks table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS browser_locks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT NOT NULL,
                locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pid INT COMMENT 'Process ID if available',
                browser_info VARCHAR(255) COMMENT 'Additional browser info',
                
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                UNIQUE KEY unique_profile_lock (profile_id),
                INDEX idx_locked_at (locked_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("    ✓ Created browser_locks table")
        
        # 2. Create hourly_request_tracker table
        print("    → Creating hourly_request_tracker table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hourly_request_tracker (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT NOT NULL,
                hour_slot DATETIME NOT NULL COMMENT 'Start of the current hour',
                request_count INT DEFAULT 0,
                last_request_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                UNIQUE KEY unique_profile_hour (profile_id, hour_slot),
                INDEX idx_hour_slot (hour_slot)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("    ✓ Created hourly_request_tracker table")
        
        # 3. Add target_profile_id to following_scraping_sessions if not exists
        print("    → Checking following_scraping_sessions table...")
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'following_scraping_sessions' 
            AND COLUMN_NAME = 'target_profile_id'
        """)
        
        if not cursor.fetchone():
            print("    → Adding target_profile_id column to following_scraping_sessions...")
            cursor.execute("""
                ALTER TABLE following_scraping_sessions 
                ADD COLUMN target_profile_id INT COMMENT 'Profile whose following is being scraped' AFTER profile_id
            """)
            
            cursor.execute("""
                ALTER TABLE following_scraping_sessions
                ADD CONSTRAINT fk_following_target_profile 
                FOREIGN KEY (target_profile_id) REFERENCES profiles(id) ON DELETE SET NULL
            """)
            
            cursor.execute("""
                ALTER TABLE following_scraping_sessions
                ADD INDEX idx_target_profile (target_profile_id)
            """)
            print("    ✓ Added target_profile_id column")
        else:
            print("    ✓ target_profile_id column already exists")
    
    def down(self, cursor) -> None:
        """Remove browser locks and rate limiting tables"""
        # Drop tables
        cursor.execute("DROP TABLE IF EXISTS browser_locks")
        cursor.execute("DROP TABLE IF EXISTS hourly_request_tracker")
        
        # Remove column from following_scraping_sessions
        try:
            cursor.execute("""
                ALTER TABLE following_scraping_sessions 
                DROP FOREIGN KEY fk_following_target_profile
            """)
            cursor.execute("""
                ALTER TABLE following_scraping_sessions 
                DROP COLUMN target_profile_id
            """)
        except:
            pass  # Column might not exist
        
        print("    ✓ Rolled back browser locks and rate limiting tables")
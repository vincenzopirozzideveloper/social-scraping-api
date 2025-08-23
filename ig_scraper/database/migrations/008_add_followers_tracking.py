"""Add followers scraping with session tracking"""

from .base import Migration


class AddFollowersTracking(Migration):
    """Add tables for tracking followers scraping sessions"""
    
    def get_version(self) -> str:
        return "008"
    
    def get_description(self) -> str:
        return "Add followers scraping session tracking"
    
    def up(self, cursor) -> None:
        """Create followers tracking tables"""
        
        # 1. Create followers_scraping_sessions table
        print("    → Creating followers_scraping_sessions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS followers_scraping_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT NOT NULL COMMENT 'Profile doing the scraping',
                target_profile_id INT NOT NULL COMMENT 'Profile being scraped',
                target_username VARCHAR(100) NOT NULL,
                session_number INT DEFAULT 1,
                total_followers INT DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP NULL,
                
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (target_profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                
                INDEX idx_profile_sessions (profile_id),
                INDEX idx_target_sessions (target_profile_id),
                INDEX idx_target_username (target_username),
                INDEX idx_started_at (started_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("    ✓ Created followers_scraping_sessions table")
        
        # 2. Create scraped_followers table
        print("    → Creating scraped_followers table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraped_followers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id INT NOT NULL,
                follower_profile_id INT,
                follower_username VARCHAR(100) NOT NULL,
                follower_user_id VARCHAR(50),
                follower_full_name VARCHAR(255),
                is_verified BOOLEAN DEFAULT FALSE,
                is_private BOOLEAN DEFAULT FALSE,
                profile_pic_url TEXT,
                position_in_list INT COMMENT 'Order in the followers list',
                page_number INT DEFAULT 1,
                raw_data JSON,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (session_id) REFERENCES followers_scraping_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (follower_profile_id) REFERENCES profiles(id) ON DELETE SET NULL,
                
                INDEX idx_session (session_id),
                INDEX idx_follower_username (follower_username),
                INDEX idx_position (position_in_list),
                INDEX idx_scraped_at (scraped_at),
                
                UNIQUE KEY unique_session_follower (session_id, follower_username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("    ✓ Created scraped_followers table")
        
        # 3. Create trigger to auto-increment session_number
        print("    → Creating session number trigger...")
        cursor.execute("""
            CREATE TRIGGER before_insert_followers_session
            BEFORE INSERT ON followers_scraping_sessions
            FOR EACH ROW
            BEGIN
                DECLARE max_session INT;
                SELECT COALESCE(MAX(session_number), 0) INTO max_session
                FROM followers_scraping_sessions
                WHERE target_username = NEW.target_username;
                SET NEW.session_number = max_session + 1;
            END
        """)
        print("    ✓ Created session number trigger")
        
        # 4. Add user_id column to profiles if not exists
        print("    → Checking profiles table for user_id column...")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'profiles' 
            AND column_name = 'user_id'
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE profiles 
                ADD COLUMN user_id VARCHAR(50) NULL AFTER username,
                ADD INDEX idx_user_id (user_id)
            """)
            print("    ✓ Added user_id to profiles table")
        
        # 5. Add full_name column to profiles if not exists
        print("    → Checking profiles table for full_name column...")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'profiles' 
            AND column_name = 'full_name'
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE profiles 
                ADD COLUMN full_name VARCHAR(255) NULL AFTER user_id
            """)
            print("    ✓ Added full_name to profiles table")
    
    def down(self, cursor) -> None:
        """Remove followers tracking tables"""
        # Drop trigger first
        cursor.execute("DROP TRIGGER IF EXISTS before_insert_followers_session")
        
        # Drop tables
        cursor.execute("DROP TABLE IF EXISTS scraped_followers")
        cursor.execute("DROP TABLE IF EXISTS followers_scraping_sessions")
        
        # Remove columns from profiles (optional, as they might be used elsewhere)
        # cursor.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS user_id")
        # cursor.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS full_name")
        
        print("    ✓ Rolled back followers tracking tables")
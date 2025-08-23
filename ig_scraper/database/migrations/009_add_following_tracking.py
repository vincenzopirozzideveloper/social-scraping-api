"""Add following scraping with session tracking"""

from .base import Migration


class AddFollowingTracking(Migration):
    """Add tables for tracking following scraping sessions"""
    
    def get_version(self) -> str:
        return "009"
    
    def get_description(self) -> str:
        return "Add following scraping session tracking"
    
    def up(self, cursor) -> None:
        """Create following tracking tables"""
        
        # 1. Create following_scraping_sessions table
        print("    → Creating following_scraping_sessions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS following_scraping_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT NOT NULL COMMENT 'Profile doing the scraping',
                target_profile_id INT COMMENT 'Profile whose following is being scraped',
                session_number INT DEFAULT 1,
                total_following INT DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP NULL,
                
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (target_profile_id) REFERENCES profiles(id) ON DELETE SET NULL,
                
                INDEX idx_profile_sessions (profile_id),
                INDEX idx_target_profile (target_profile_id),
                INDEX idx_started_at (started_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("    ✓ Created following_scraping_sessions table")
        
        # 2. Create scraped_following table
        print("    → Creating scraped_following table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraped_following (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id INT NOT NULL,
                following_profile_id INT,
                following_username VARCHAR(100) NOT NULL,
                following_user_id VARCHAR(50),
                following_full_name VARCHAR(255),
                is_verified BOOLEAN DEFAULT FALSE,
                is_private BOOLEAN DEFAULT FALSE,
                profile_pic_url TEXT,
                position_in_list INT COMMENT 'Order in the following list',
                page_number INT DEFAULT 1,
                raw_data JSON,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (session_id) REFERENCES following_scraping_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (following_profile_id) REFERENCES profiles(id) ON DELETE SET NULL,
                
                INDEX idx_session (session_id),
                INDEX idx_following_username (following_username),
                INDEX idx_position (position_in_list),
                INDEX idx_scraped_at (scraped_at),
                
                UNIQUE KEY unique_session_following (session_id, following_username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("    ✓ Created scraped_following table")
        
        # 3. Create trigger to auto-increment session_number
        print("    → Creating session number trigger...")
        cursor.execute("""
            CREATE TRIGGER before_insert_following_session
            BEFORE INSERT ON following_scraping_sessions
            FOR EACH ROW
            BEGIN
                DECLARE max_session INT;
                SELECT COALESCE(MAX(session_number), 0) INTO max_session
                FROM following_scraping_sessions
                WHERE profile_id = NEW.profile_id;
                SET NEW.session_number = max_session + 1;
            END
        """)
        print("    ✓ Created session number trigger")
    
    def down(self, cursor) -> None:
        """Remove following tracking tables"""
        # Drop trigger first
        cursor.execute("DROP TRIGGER IF EXISTS before_insert_following_session")
        
        # Drop tables
        cursor.execute("DROP TABLE IF EXISTS scraped_following")
        cursor.execute("DROP TABLE IF EXISTS following_scraping_sessions")
        
        print("    ✓ Rolled back following tracking tables")
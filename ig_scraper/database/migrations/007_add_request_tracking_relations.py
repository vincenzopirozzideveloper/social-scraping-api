"""Add complete request-response-posts tracking with relationships"""

from .base import Migration


class AddRequestTrackingRelations(Migration):
    """Add relationship tracking between API requests and discovered posts"""
    
    def get_version(self) -> str:
        return "007"
    
    def get_description(self) -> str:
        return "Add relationship tracking for API requests and posts"
    
    def up(self, cursor) -> None:
        """Create new tables and relationships for complete tracking"""
        
        # 1. Create explore_posts table for all posts found via explore
        print("    → Creating explore_posts table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS explore_posts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                api_request_id INT NOT NULL,
                profile_id INT NOT NULL,
                media_id VARCHAR(100) NOT NULL,
                media_code VARCHAR(50),
                media_type INT,  -- 1=photo, 2=video, 8=carousel
                owner_id VARCHAR(50),
                owner_username VARCHAR(100),
                owner_full_name VARCHAR(255),
                caption TEXT,
                like_count INT DEFAULT 0,
                comment_count INT DEFAULT 0,
                has_liked BOOLEAN DEFAULT FALSE,
                is_verified BOOLEAN DEFAULT FALSE,
                taken_at TIMESTAMP NULL,
                position_in_response INT,  -- Order in the response
                raw_data JSON,  -- Complete post data from API
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (api_request_id) REFERENCES api_requests(id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                
                INDEX idx_api_request (api_request_id),
                INDEX idx_profile (profile_id),
                INDEX idx_media_id (media_id),
                INDEX idx_media_code (media_code),
                INDEX idx_owner_username (owner_username),
                INDEX idx_discovered_at (discovered_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("    ✓ Created explore_posts table")
        
        # 2. Add api_request_id to posts_processed for tracking which request led to processing
        print("    → Adding api_request_id to posts_processed...")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'posts_processed' 
            AND column_name = 'api_request_id'
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE posts_processed 
                ADD COLUMN api_request_id INT NULL AFTER profile_id,
                ADD FOREIGN KEY (api_request_id) REFERENCES api_requests(id) ON DELETE SET NULL,
                ADD INDEX idx_api_request_id (api_request_id)
            """)
            print("    ✓ Added api_request_id to posts_processed")
        
        # 3. Create explore_search_sessions to track search sequences
        print("    → Creating explore_search_sessions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS explore_search_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT NOT NULL,
                automation_session_id INT,
                search_query VARCHAR(255),
                search_type ENUM('general', 'search', 'hashtag', 'location'),
                total_pages INT DEFAULT 0,
                total_posts INT DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP NULL,
                
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (automation_session_id) REFERENCES automation_sessions(id) ON DELETE SET NULL,
                
                INDEX idx_profile_sessions (profile_id),
                INDEX idx_search_query (search_query),
                INDEX idx_started_at (started_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("    ✓ Created explore_search_sessions table")
        
        # 4. Update api_requests to include search_session_id
        print("    → Adding search_session_id to api_requests...")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'api_requests' 
            AND column_name = 'search_session_id'
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE api_requests 
                ADD COLUMN search_session_id INT NULL AFTER session_id,
                ADD FOREIGN KEY (search_session_id) REFERENCES explore_search_sessions(id) ON DELETE SET NULL,
                ADD INDEX idx_search_session (search_session_id)
            """)
            print("    ✓ Added search_session_id to api_requests")
        
        # 5. Add page_number to api_requests for pagination tracking
        print("    → Adding page_number to api_requests...")
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'api_requests' 
            AND column_name = 'page_number'
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE api_requests 
                ADD COLUMN page_number INT DEFAULT 1 AFTER request_type
            """)
            print("    ✓ Added page_number to api_requests")
    
    def down(self, cursor) -> None:
        """Remove the tables and columns"""
        # Drop new tables
        cursor.execute("DROP TABLE IF EXISTS explore_posts")
        cursor.execute("DROP TABLE IF EXISTS explore_search_sessions")
        
        # Remove columns from existing tables
        try:
            cursor.execute("ALTER TABLE posts_processed DROP COLUMN api_request_id")
        except:
            pass
        
        try:
            cursor.execute("ALTER TABLE api_requests DROP COLUMN search_session_id")
        except:
            pass
        
        try:
            cursor.execute("ALTER TABLE api_requests DROP COLUMN page_number")
        except:
            pass
        
        print("    ✓ Rolled back request tracking relations")
"""Initial database schema migration"""

from migration import Migration


class InitialSchema(Migration):
    """Create initial database tables"""
    
    def get_version(self) -> str:
        return "001"
    
    def get_description(self) -> str:
        return "Create initial database schema"
    
    def up(self, cursor) -> None:
        """Create all initial tables"""
        
        # Profiles table
        cursor.execute("""
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
        """)
        
        # Browser sessions table
        cursor.execute("""
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
        """)
        
        # Following table
        cursor.execute("""
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
        """)
        
        # Posts processed table
        cursor.execute("""
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
        """)
        
        # Comments made table
        cursor.execute("""
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
        """)
        
        # Automation sessions table
        cursor.execute("""
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
        """)
        
        # Action logs table (FIXED: includes profile_id)
        cursor.execute("""
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
        """)
        
        # GraphQL endpoints table
        cursor.execute("""
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
        """)
        
        print("  ✓ Created profiles table")
        print("  ✓ Created browser_sessions table")
        print("  ✓ Created following table")
        print("  ✓ Created posts_processed table")
        print("  ✓ Created comments_made table")
        print("  ✓ Created automation_sessions table")
        print("  ✓ Created action_logs table (with profile_id)")
        print("  ✓ Created graphql_endpoints table")
    
    def down(self, cursor) -> None:
        """Drop all tables in reverse order"""
        tables = [
            'graphql_endpoints',
            'action_logs',
            'automation_sessions',
            'comments_made',
            'posts_processed',
            'following',
            'browser_sessions',
            'profiles'
        ]
        
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"  ✓ Dropped {table} table")
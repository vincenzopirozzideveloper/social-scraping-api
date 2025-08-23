-- Instagram Scraper Database Schema
-- MariaDB/MySQL compatible
-- Note: Database name is taken from .env file (DB_NAME)
-- The CREATE DATABASE and USE statements are handled by the migration script

-- Profiles table (Instagram accounts)
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Browser Sessions table (for authentication)
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Following/Followers tracking
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Posts processed (for automation)
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
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    UNIQUE KEY unique_post (profile_id, media_id),
    INDEX idx_profile_posts (profile_id),
    INDEX idx_media_id (media_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Comments made
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Automation sessions
CREATE TABLE IF NOT EXISTS automation_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    profile_id INT NOT NULL,
    session_type VARCHAR(50) NOT NULL, -- 'unfollow', 'explore', 'following_scrape'
    total_processed INT DEFAULT 0,
    successful INT DEFAULT 0,
    failed INT DEFAULT 0,
    metadata JSON,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    INDEX idx_profile_sessions (profile_id),
    INDEX idx_session_type (session_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Action logs (detailed logging)
CREATE TABLE IF NOT EXISTS action_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    profile_id INT NOT NULL,
    session_id INT,
    action_type VARCHAR(50) NOT NULL, -- 'follow', 'unfollow', 'like', 'comment'
    target_id VARCHAR(100),
    target_username VARCHAR(50),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES automation_sessions(id) ON DELETE SET NULL,
    INDEX idx_profile_actions (profile_id),
    INDEX idx_session_actions (session_id),
    INDEX idx_action_type (action_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- GraphQL endpoints cache
CREATE TABLE IF NOT EXISTS graphql_endpoints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    profile_id INT NOT NULL,
    endpoint_name VARCHAR(100) NOT NULL,
    doc_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    UNIQUE KEY unique_endpoint (profile_id, endpoint_name),
    INDEX idx_profile_endpoints (profile_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""Database manager for Instagram scraper"""

import os
import json
import pymysql
from pymysql.cursors import DictCursor
from typing import Optional, Dict, Any, List
from datetime import datetime
from contextlib import contextmanager
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Singleton database manager for all database operations"""
    
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance
    
    def initialize(self):
        """Initialize database connection parameters"""
        self.config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'instagram_scraper'),
            'charset': 'utf8mb4',
            'cursorclass': DictCursor,
            'autocommit': False
        }
        self.ensure_connection()
    
    def ensure_connection(self):
        """Ensure database connection is active"""
        try:
            if self._connection is None or not self._connection.open:
                self._connection = pymysql.connect(**self.config)
                logger.info(f"Connected to database: {self.config['database']}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    @contextmanager
    def get_cursor(self, commit=True):
        """Context manager for database cursor"""
        self.ensure_connection()
        cursor = self._connection.cursor()
        try:
            yield cursor
            if commit:
                self._connection.commit()
        except Exception as e:
            self._connection.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            cursor.close()
    
    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    # Profile operations
    def get_or_create_profile(self, username: str, user_id: Optional[str] = None, 
                              full_name: Optional[str] = None) -> int:
        """Get or create a profile and return its ID"""
        with self.get_cursor() as cursor:
            # Try to get existing profile
            cursor.execute(
                "SELECT id FROM profiles WHERE username = %s",
                (username,)
            )
            result = cursor.fetchone()
            
            if result:
                # Update if we have new info
                if user_id or full_name:
                    updates = []
                    params = []
                    if user_id:
                        updates.append("user_id = %s")
                        params.append(user_id)
                    if full_name:
                        updates.append("full_name = %s")
                        params.append(full_name)
                    params.append(username)
                    
                    cursor.execute(
                        f"UPDATE profiles SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE username = %s",
                        params
                    )
                return result['id']
            else:
                # Create new profile
                cursor.execute(
                    "INSERT INTO profiles (username, user_id, full_name) VALUES (%s, %s, %s)",
                    (username, user_id, full_name)
                )
                return cursor.lastrowid
    
    # Session operations
    def create_session(self, profile_id: int, search_query: Optional[str] = None) -> int:
        """Create a new automation session"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO automation_sessions 
                   (profile_id, search_query, status) 
                   VALUES (%s, %s, 'running')""",
                (profile_id, search_query)
            )
            return cursor.lastrowid
    
    def update_session(self, session_id: int, **kwargs):
        """Update session statistics"""
        with self.get_cursor() as cursor:
            updates = []
            params = []
            
            for key, value in kwargs.items():
                if key in ['posts_processed', 'likes_count', 'comments_count', 'errors_count', 'status']:
                    updates.append(f"{key} = %s")
                    params.append(value)
            
            if updates:
                params.append(session_id)
                cursor.execute(
                    f"UPDATE automation_sessions SET {', '.join(updates)} WHERE id = %s",
                    params
                )
    
    def end_session(self, session_id: int, status: str = 'completed'):
        """End an automation session"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """UPDATE automation_sessions 
                   SET ended_at = CURRENT_TIMESTAMP, status = %s 
                   WHERE id = %s""",
                (status, session_id)
            )
    
    # Action logging
    def log_action(self, session_id: int, action_type: str, target_id: str,
                   target_username: Optional[str] = None, success: bool = True,
                   error_message: Optional[str] = None, response_data: Optional[Dict] = None):
        """Log an action to the database"""
        with self.get_cursor() as cursor:
            response_json = json.dumps(response_data) if response_data else None
            cursor.execute(
                """INSERT INTO action_logs 
                   (session_id, action_type, target_id, target_username, success, error_message, response_data)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (session_id, action_type, target_id, target_username, success, error_message, response_json)
            )
            return cursor.lastrowid
    
    # Post operations
    def is_post_processed(self, media_id: str, profile_id: int) -> bool:
        """Check if a post has been processed by this profile"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """SELECT id FROM posts_processed 
                   WHERE media_id = %s AND profile_id = %s""",
                (media_id, profile_id)
            )
            return cursor.fetchone() is not None
    
    def mark_post_processed(self, media_id: str, media_code: Optional[str], 
                           owner_username: Optional[str], action_type: str,
                           profile_id: int, success: bool = True):
        """Mark a post as processed"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO posts_processed 
                   (media_id, media_code, owner_username, action_type, success, profile_id)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE 
                   action_type = VALUES(action_type),
                   success = VALUES(success),
                   processed_at = CURRENT_TIMESTAMP""",
                (media_id, media_code, owner_username, action_type, success, profile_id)
            )
    
    # Comment operations
    def save_comment(self, comment_id: Optional[str], media_id: str, media_code: Optional[str],
                     comment_text: str, comment_url: Optional[str], profile_id: int):
        """Save a comment to the database"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO comments_made 
                   (comment_id, media_id, media_code, comment_text, comment_url, profile_id)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE 
                   comment_url = VALUES(comment_url)""",
                (comment_id, media_id, media_code, comment_text, comment_url, profile_id)
            )
    
    # Statistics
    def get_session_stats(self, session_id: int) -> Dict[str, Any]:
        """Get statistics for a session"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """SELECT * FROM automation_sessions WHERE id = %s""",
                (session_id,)
            )
            return cursor.fetchone()
    
    def get_profile_stats(self, profile_id: int) -> Dict[str, Any]:
        """Get statistics for a profile"""
        with self.get_cursor() as cursor:
            # Get profile info
            cursor.execute("SELECT * FROM profiles WHERE id = %s", (profile_id,))
            profile = cursor.fetchone()
            
            # Get total stats
            cursor.execute(
                """SELECT 
                   COUNT(DISTINCT media_id) as total_posts,
                   SUM(CASE WHEN action_type IN ('like', 'both') THEN 1 ELSE 0 END) as total_likes,
                   COUNT(DISTINCT comment_id) as total_comments
                   FROM posts_processed 
                   LEFT JOIN comments_made ON posts_processed.media_id = comments_made.media_id
                   WHERE posts_processed.profile_id = %s""",
                (profile_id,)
            )
            stats = cursor.fetchone()
            
            # Get recent sessions
            cursor.execute(
                """SELECT * FROM automation_sessions 
                   WHERE profile_id = %s 
                   ORDER BY started_at DESC 
                   LIMIT 5""",
                (profile_id,)
            )
            recent_sessions = cursor.fetchall()
            
            return {
                'profile': profile,
                'stats': stats,
                'recent_sessions': recent_sessions
            }
    
    def get_recent_actions(self, session_id: int, limit: int = 10) -> List[Dict]:
        """Get recent actions for a session"""
        with self.get_cursor() as cursor:
            cursor.execute(
                """SELECT * FROM action_logs 
                   WHERE session_id = %s 
                   ORDER BY created_at DESC 
                   LIMIT %s""",
                (session_id, limit)
            )
            return cursor.fetchall()
    
    # Following/Followers operations
    def save_following_batch(self, profile_id: int, users: List[Dict], fetch_type: str = 'following'):
        """Save a batch of following/followers data"""
        with self.get_cursor() as cursor:
            # Create a following fetch record
            cursor.execute(
                """INSERT INTO following_fetches 
                   (profile_id, fetch_type, total_count) 
                   VALUES (%s, %s, %s)""",
                (profile_id, fetch_type, len(users))
            )
            fetch_id = cursor.lastrowid
            
            # Save each user
            for user in users:
                cursor.execute(
                    """INSERT INTO following_data 
                       (fetch_id, user_id, username, full_name, is_private, is_verified, profile_pic_url)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                       full_name = VALUES(full_name),
                       is_private = VALUES(is_private),
                       is_verified = VALUES(is_verified),
                       profile_pic_url = VALUES(profile_pic_url)""",
                    (fetch_id, user.get('pk') or user.get('id'), user.get('username'),
                     user.get('full_name'), user.get('is_private', False),
                     user.get('is_verified', False), user.get('profile_pic_url'))
                )
            
            return fetch_id
    
    # Explore search operations
    def save_explore_search(self, profile_id: int, query: str, results: Dict):
        """Save explore search results"""
        with self.get_cursor() as cursor:
            # Save search query
            cursor.execute(
                """INSERT INTO explore_searches 
                   (profile_id, search_query, results_count)
                   VALUES (%s, %s, %s)""",
                (profile_id, query, len(results.get('list', [])))
            )
            search_id = cursor.lastrowid
            
            # Save search results
            for item in results.get('list', []):
                if 'user' in item:
                    user = item['user']
                    cursor.execute(
                        """INSERT INTO explore_results 
                           (search_id, result_type, user_id, username, full_name)
                           VALUES (%s, 'user', %s, %s, %s)""",
                        (search_id, user.get('pk'), user.get('username'), user.get('full_name'))
                    )
            
            return search_id


# Create singleton instance
db_manager = DatabaseManager()
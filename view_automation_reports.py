#!/usr/bin/env python3
"""View detailed automation reports from database"""

import os
import sys
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'instagram_scraper'),
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}

class AutomationReporter:
    def __init__(self):
        self.conn = None
    
    def connect(self):
        """Connect to database"""
        try:
            self.conn = pymysql.connect(**DB_CONFIG)
            return True
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False
    
    def list_sessions(self, profile_username: str = None, limit: int = 10):
        """List recent automation sessions"""
        try:
            with self.conn.cursor() as cursor:
                if profile_username:
                    cursor.execute("""
                        SELECT s.*, p.username 
                        FROM automation_sessions s
                        JOIN profiles p ON s.profile_id = p.id
                        WHERE p.username = %s
                        ORDER BY s.started_at DESC
                        LIMIT %s
                    """, (profile_username, limit))
                else:
                    cursor.execute("""
                        SELECT s.*, p.username 
                        FROM automation_sessions s
                        JOIN profiles p ON s.profile_id = p.id
                        ORDER BY s.started_at DESC
                        LIMIT %s
                    """, (limit,))
                
                sessions = cursor.fetchall()
                
                print("\n" + "="*80)
                print("RECENT AUTOMATION SESSIONS")
                print("="*80)
                
                for session in sessions:
                    duration = "N/A"
                    if session['ended_at'] and session['started_at']:
                        duration = f"{(session['ended_at'] - session['started_at']).total_seconds():.0f}s"
                    
                    print(f"\n#{session['id']} - @{session['username']}")
                    print(f"  Type: {session['session_type']}")
                    print(f"  Status: {session['status']}")
                    print(f"  Started: {session['started_at']}")
                    print(f"  Duration: {duration}")
                    if session['search_query']:
                        print(f"  Query: {session['search_query']}")
                    print(f"  Posts: {session.get('posts_processed', 0)}")
                    print(f"  Likes: {session.get('likes_count', 0)}")
                    print(f"  Comments: {session.get('comments_count', 0)}")
                    print(f"  Errors: {session.get('errors_count', 0)}")
                
                print("="*80)
                return sessions
                
        except Exception as e:
            print(f"Error listing sessions: {e}")
            return []
    
    def session_detail(self, session_id: int):
        """Show detailed report for a specific session"""
        try:
            with self.conn.cursor() as cursor:
                # Get session info
                cursor.execute("""
                    SELECT s.*, p.username 
                    FROM automation_sessions s
                    JOIN profiles p ON s.profile_id = p.id
                    WHERE s.id = %s
                """, (session_id,))
                session = cursor.fetchone()
                
                if not session:
                    print(f"❌ Session #{session_id} not found")
                    return
                
                print("\n" + "="*80)
                print(f"SESSION #{session_id} DETAILED REPORT")
                print("="*80)
                print(f"Profile: @{session['username']}")
                print(f"Type: {session['session_type']}")
                print(f"Status: {session['status']}")
                print(f"Started: {session['started_at']}")
                print(f"Ended: {session['ended_at']}")
                if session['ended_at'] and session['started_at']:
                    duration = (session['ended_at'] - session['started_at']).total_seconds()
                    print(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
                if session['search_query']:
                    print(f"Search Query: {session['search_query']}")
                
                # Get action statistics
                cursor.execute("""
                    SELECT action_type, 
                           COUNT(*) as total,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                           SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
                    FROM action_logs
                    WHERE session_id = %s
                    GROUP BY action_type
                    ORDER BY total DESC
                """, (session_id,))
                actions = cursor.fetchall()
                
                print("\n" + "-"*80)
                print("ACTION STATISTICS")
                print("-"*80)
                for action in actions:
                    success_rate = (action['successful'] / action['total'] * 100) if action['total'] > 0 else 0
                    print(f"{action['action_type']:20} Total: {action['total']:5} | Success: {action['successful']:5} | Failed: {action['failed']:5} | Rate: {success_rate:.1f}%")
                
                # Get posts processed
                cursor.execute("""
                    SELECT COUNT(DISTINCT pp.media_id) as total_posts,
                           SUM(CASE WHEN pp.is_liked = 1 THEN 1 ELSE 0 END) as liked,
                           SUM(CASE WHEN pp.is_commented = 1 THEN 1 ELSE 0 END) as commented
                    FROM posts_processed pp
                    WHERE pp.profile_id = %s
                    AND pp.processed_at >= %s
                    AND pp.processed_at <= IFNULL(%s, NOW())
                """, (session['profile_id'], session['started_at'], session['ended_at']))
                post_stats = cursor.fetchone()
                
                if post_stats and post_stats['total_posts'] > 0:
                    print("\n" + "-"*80)
                    print("POSTS INTERACTION")
                    print("-"*80)
                    print(f"Total unique posts: {post_stats['total_posts']}")
                    print(f"Posts liked: {post_stats['liked']}")
                    print(f"Posts commented: {post_stats['commented']}")
                
                # Get recent posts from this session
                cursor.execute("""
                    SELECT pp.*, cm.comment_text
                    FROM posts_processed pp
                    LEFT JOIN comments_made cm ON pp.media_id = cm.media_id AND pp.profile_id = cm.profile_id
                    WHERE pp.profile_id = %s
                    AND pp.processed_at >= %s
                    AND pp.processed_at <= IFNULL(%s, NOW())
                    ORDER BY pp.processed_at DESC
                    LIMIT 10
                """, (session['profile_id'], session['started_at'], session['ended_at']))
                recent_posts = cursor.fetchall()
                
                if recent_posts:
                    print("\n" + "-"*80)
                    print("RECENT POSTS (Last 10)")
                    print("-"*80)
                    for post in recent_posts:
                        actions = []
                        if post['is_liked']:
                            actions.append("Liked")
                        if post['is_commented']:
                            actions.append("Commented")
                        
                        print(f"\n• {post['media_code'] or post['media_id'][:20]}")
                        print(f"  Owner: @{post['owner_username'] or 'unknown'}")
                        print(f"  Actions: {', '.join(actions) if actions else 'None'}")
                        if post['comment_text']:
                            print(f"  Comment: \"{post['comment_text']}\"")
                        if post['caption']:
                            print(f"  Caption: {post['caption'][:100]}...")
                
                # Get errors if any
                cursor.execute("""
                    SELECT * FROM action_logs
                    WHERE session_id = %s
                    AND success = 0
                    ORDER BY created_at DESC
                    LIMIT 5
                """, (session_id,))
                errors = cursor.fetchall()
                
                if errors:
                    print("\n" + "-"*80)
                    print("RECENT ERRORS (Last 5)")
                    print("-"*80)
                    for error in errors:
                        print(f"\n• {error['action_type']} at {error['created_at']}")
                        if error['target_username']:
                            print(f"  Target: @{error['target_username']}")
                        if error['error_message']:
                            print(f"  Error: {error['error_message'][:200]}")
                
                print("\n" + "="*80)
                
        except Exception as e:
            print(f"Error getting session detail: {e}")
    
    def profile_statistics(self, username: str):
        """Show overall statistics for a profile"""
        try:
            with self.conn.cursor() as cursor:
                # Get profile
                cursor.execute("SELECT * FROM profiles WHERE username = %s", (username,))
                profile = cursor.fetchone()
                
                if not profile:
                    print(f"❌ Profile @{username} not found")
                    return
                
                print("\n" + "="*80)
                print(f"PROFILE STATISTICS: @{username}")
                print("="*80)
                
                # Overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT s.id) as total_sessions,
                        SUM(s.posts_processed) as total_posts,
                        SUM(s.likes_count) as total_likes,
                        SUM(s.comments_count) as total_comments,
                        SUM(s.errors_count) as total_errors
                    FROM automation_sessions s
                    WHERE s.profile_id = %s
                """, (profile['id'],))
                stats = cursor.fetchone()
                
                print(f"Total Sessions: {stats['total_sessions']}")
                print(f"Total Posts Processed: {stats['total_posts'] or 0}")
                print(f"Total Likes: {stats['total_likes'] or 0}")
                print(f"Total Comments: {stats['total_comments'] or 0}")
                print(f"Total Errors: {stats['total_errors'] or 0}")
                
                # Success rates
                cursor.execute("""
                    SELECT 
                        action_type,
                        COUNT(*) as total,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                    FROM action_logs
                    WHERE profile_id = %s
                    GROUP BY action_type
                """, (profile['id'],))
                action_stats = cursor.fetchall()
                
                print("\n" + "-"*80)
                print("ACTION SUCCESS RATES")
                print("-"*80)
                for action in action_stats:
                    rate = (action['successful'] / action['total'] * 100) if action['total'] > 0 else 0
                    print(f"{action['action_type']:20} {rate:.1f}% ({action['successful']}/{action['total']})")
                
                # Most interacted users
                cursor.execute("""
                    SELECT owner_username, COUNT(*) as interactions
                    FROM posts_processed
                    WHERE profile_id = %s
                    AND owner_username IS NOT NULL
                    GROUP BY owner_username
                    ORDER BY interactions DESC
                    LIMIT 10
                """, (profile['id'],))
                top_users = cursor.fetchall()
                
                if top_users:
                    print("\n" + "-"*80)
                    print("TOP INTERACTED USERS")
                    print("-"*80)
                    for user in top_users:
                        print(f"@{user['owner_username']:30} {user['interactions']} interactions")
                
                # Comment analysis
                cursor.execute("""
                    SELECT comment_text, COUNT(*) as used_count
                    FROM comments_made
                    WHERE profile_id = %s
                    GROUP BY comment_text
                    ORDER BY used_count DESC
                    LIMIT 10
                """, (profile['id'],))
                top_comments = cursor.fetchall()
                
                if top_comments:
                    print("\n" + "-"*80)
                    print("MOST USED COMMENTS")
                    print("-"*80)
                    for comment in top_comments:
                        print(f"{comment['used_count']:3}x \"{comment['comment_text']}\"")
                
                print("="*80)
                
        except Exception as e:
            print(f"Error getting profile statistics: {e}")
    
    def run(self):
        """Main interactive loop"""
        if not self.connect():
            return
        
        while True:
            print("\n" + "="*80)
            print("AUTOMATION REPORTS")
            print("="*80)
            print("1. List recent sessions")
            print("2. View session details")
            print("3. Profile statistics")
            print("4. Search sessions by query")
            print("0. Exit")
            print("="*80)
            
            choice = input("\nSelect option: ")
            
            if choice == '0':
                break
            elif choice == '1':
                username = input("Username (leave empty for all): ").strip()
                self.list_sessions(username if username else None)
            elif choice == '2':
                try:
                    session_id = int(input("Session ID: "))
                    self.session_detail(session_id)
                except ValueError:
                    print("❌ Invalid session ID")
            elif choice == '3':
                username = input("Username: @").strip()
                if username:
                    self.profile_statistics(username)
            elif choice == '4':
                query = input("Search query: ").strip()
                if query:
                    with self.conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT s.*, p.username 
                            FROM automation_sessions s
                            JOIN profiles p ON s.profile_id = p.id
                            WHERE s.search_query LIKE %s
                            ORDER BY s.started_at DESC
                            LIMIT 20
                        """, (f"%{query}%",))
                        sessions = cursor.fetchall()
                        
                        print(f"\n✓ Found {len(sessions)} sessions with query '{query}'")
                        for s in sessions:
                            print(f"  #{s['id']} - @{s['username']} - {s['started_at']}")
        
        if self.conn:
            self.conn.close()

if __name__ == "__main__":
    reporter = AutomationReporter()
    reporter.run()
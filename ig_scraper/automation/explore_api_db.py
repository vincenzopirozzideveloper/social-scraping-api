"""Explore automation with complete database tracking"""

import json
import random
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
from ..api import Endpoints, GraphQLClient
from ..actions import ActionManager
from ..actions.interaction_graphql import LikeActionGraphQL, CommentActionGraphQL
from ..scrapers.explore import ExploreScraper
from ..database import DatabaseManager
from ..config.defaults import DEFAULT_CONFIG


class ExploreAPIAutomationDB:
    """API-based Explore Automation with complete database tracking"""
    
    def __init__(self, page, session_manager, username: str):
        self.page = page
        self.session_manager = session_manager
        self.username = username
        self.config = self._load_config()
        
        # Database manager
        self.db = DatabaseManager()
        
        # Get profile ID from database
        self.profile = self.db.get_profile_by_username(username)
        if not self.profile:
            self.profile = self.db.get_or_create_profile(username)
        self.profile_id = self.profile['id']
        
        # Create automation session in database
        self.session_id = None
        self.create_session()
        
        # Initialize components
        self.explore_scraper = ExploreScraper(page, session_manager, username)
        self.action_manager = ActionManager(page, session_manager, username)
        self.like_action = LikeActionGraphQL(page, session_manager, username)
        self.comment_action = CommentActionGraphQL(page, session_manager, username)
        
        # Statistics (also tracked in DB)
        self.stats = {
            "likes": 0,
            "comments": 0,
            "errors": 0,
            "posts_processed": 0,
            "like_errors": [],
            "comment_errors": []
        }
        self.comment_index = 0
        self.processed_posts = set()
        
    def create_session(self, search_query: Optional[str] = None):
        """Create automation session in database"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO automation_sessions 
                    (profile_id, session_type, search_query, status)
                    VALUES (%s, %s, %s, 'running')
                """, (self.profile_id, 'explore_automation', search_query))
                self.session_id = cursor.lastrowid
                print(f"✓ Created automation session #{self.session_id}")
        except Exception as e:
            print(f"Error creating session: {e}")
    
    def log_api_request(self, endpoint: str, params: Dict, response: Dict, success: bool = True):
        """Log API request and response to database"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO action_logs 
                    (profile_id, session_id, action_type, target_id, metadata, success, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (
                    self.profile_id,
                    self.session_id,
                    'api_request',
                    endpoint,
                    json.dumps({
                        'endpoint': endpoint,
                        'params': params,
                        'response': response[:1000] if isinstance(response, str) else response,
                        'timestamp': datetime.now().isoformat()
                    }),
                    success
                ))
        except Exception as e:
            print(f"Error logging API request: {e}")
    
    def save_api_request_response(self, endpoint: str, url: str, params: Dict, response_data: Dict):
        """Save complete API request and response to database for debugging"""
        try:
            with self.db.get_cursor() as cursor:
                # Save to api_requests table for complete tracking
                cursor.execute("""
                    INSERT INTO api_requests 
                    (profile_id, session_id, request_type, endpoint, method, params, body, 
                     response_status, response_body, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    self.profile_id,
                    self.session_id,
                    'explore_search' if params.get('query') else 'explore_general',
                    url,
                    'GET',
                    json.dumps(params),
                    None,  # No body for GET requests
                    200 if response_data else 0,
                    json.dumps(response_data) if response_data else None
                ))
                print(f"  ✓ Request/Response saved to database (api_requests table)")
        except Exception as e:
            print(f"Error saving API request/response: {e}")
    
    def save_post_to_db(self, post: Dict[str, Any], action_taken: str = None):
        """Save post data to database"""
        try:
            media_id = post.get('id') or post.get('pk')
            media_code = post.get('code') or post.get('media_code')
            owner = post.get('owner', {})
            owner_username = owner.get('username') if isinstance(owner, dict) else post.get('owner_username')
            
            # Extract post details
            caption = None
            if post.get('caption'):
                if isinstance(post['caption'], dict):
                    caption = post['caption'].get('text', '')
                else:
                    caption = str(post['caption'])
            
            like_count = post.get('like_count', 0) or post.get('edge_liked_by', {}).get('count', 0)
            comment_count = post.get('comment_count', 0) or post.get('edge_media_to_comment', {}).get('count', 0)
            
            with self.db.get_cursor() as cursor:
                # Check if post already exists
                cursor.execute("""
                    SELECT id, is_liked, is_commented 
                    FROM posts_processed 
                    WHERE profile_id = %s AND media_id = %s
                """, (self.profile_id, media_id))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing post
                    updates = []
                    params = []
                    
                    if action_taken == 'like':
                        updates.append("is_liked = TRUE")
                    elif action_taken == 'comment':
                        updates.append("is_commented = TRUE")
                    elif action_taken == 'both':
                        updates.append("is_liked = TRUE")
                        updates.append("is_commented = TRUE")
                    
                    if updates:
                        params.extend([existing['id']])
                        cursor.execute(f"""
                            UPDATE posts_processed 
                            SET {', '.join(updates)}, processed_at = NOW()
                            WHERE id = %s
                        """, params)
                else:
                    # Insert new post
                    cursor.execute("""
                        INSERT INTO posts_processed 
                        (profile_id, media_id, media_code, owner_username, caption, 
                         like_count, comment_count, is_liked, is_commented, processed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        self.profile_id,
                        media_id,
                        media_code,
                        owner_username,
                        caption[:1000] if caption else None,  # Limit caption length
                        like_count,
                        comment_count,
                        action_taken == 'like' or action_taken == 'both',
                        action_taken == 'comment' or action_taken == 'both'
                    ))
                
                # Log detailed post data
                cursor.execute("""
                    INSERT INTO action_logs
                    (profile_id, session_id, action_type, target_id, target_username, metadata, success)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                """, (
                    self.profile_id,
                    self.session_id,
                    'post_discovered',
                    media_id,
                    owner_username,
                    json.dumps({
                        'media_code': media_code,
                        'caption': caption[:500] if caption else None,
                        'like_count': like_count,
                        'comment_count': comment_count,
                        'post_type': post.get('media_type', 'unknown'),
                        'is_video': post.get('is_video', False),
                        'timestamp': datetime.now().isoformat()
                    })
                ))
                
        except Exception as e:
            print(f"Error saving post to DB: {e}")
    
    def log_action(self, action_type: str, target_id: str, target_username: str, 
                   success: bool, error_message: str = None, response_data: Dict = None):
        """Log action to database"""
        try:
            self.db.log_action(
                session_id=self.session_id,
                action_type=action_type,
                target_id=target_id,
                target_username=target_username,
                success=success,
                error_message=error_message,
                response_data=response_data
            )
            
            # Also log to action_logs with more detail
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO action_logs
                    (profile_id, session_id, action_type, target_id, target_username, 
                     success, error_message, response_data, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    self.profile_id,
                    self.session_id,
                    action_type,
                    target_id,
                    target_username,
                    success,
                    error_message,
                    json.dumps(response_data) if response_data else None
                ))
        except Exception as e:
            print(f"Error logging action: {e}")
    
    def save_comment_to_db(self, media_id: str, media_code: str, comment_text: str, 
                          comment_id: str = None, success: bool = True):
        """Save comment to database"""
        try:
            if success:
                self.db.save_comment(
                    comment_id=comment_id,
                    media_id=media_id,
                    media_code=media_code,
                    comment_text=comment_text,
                    comment_url=f"https://www.instagram.com/p/{media_code}/" if media_code else None,
                    profile_id=self.profile_id
                )
            
            # Log the comment action
            self.log_action(
                action_type='comment',
                target_id=media_id,
                target_username=None,
                success=success,
                response_data={'comment_text': comment_text, 'comment_id': comment_id}
            )
        except Exception as e:
            print(f"Error saving comment to DB: {e}")
    
    def update_session_stats(self):
        """Update session statistics in database"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE automation_sessions
                    SET posts_processed = %s,
                        likes_count = %s,
                        comments_count = %s,
                        errors_count = %s,
                        metadata = %s
                    WHERE id = %s
                """, (
                    self.stats['posts_processed'],
                    self.stats['likes'],
                    self.stats['comments'],
                    self.stats['errors'],
                    json.dumps({
                        'like_errors': self.stats['like_errors'],
                        'comment_errors': self.stats['comment_errors'],
                        'processed_posts': list(self.processed_posts)
                    }),
                    self.session_id
                ))
        except Exception as e:
            print(f"Error updating session stats: {e}")
    
    def _load_config(self) -> Dict:
        """Load configuration from centralized defaults"""
        # Extract automation config from DEFAULT_CONFIG
        config = {
            "explore": DEFAULT_CONFIG.get("automation", {}).get("explore", {}),
            "comments": DEFAULT_CONFIG.get("automation", {}).get("comments", {}),
            "delays": DEFAULT_CONFIG.get("automation", {}).get("delays", {}),
            "limits": DEFAULT_CONFIG.get("automation", {}).get("limits", {})
        }
        # Save config to database for tracking
        self._save_config_to_db(config)
        return config
    
    def _save_config_to_db(self, config: Dict):
        """Save automation config to database"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO action_logs
                    (profile_id, session_id, action_type, metadata, success)
                    VALUES (%s, %s, 'config_loaded', %s, TRUE)
                """, (
                    self.profile_id,
                    self.session_id,
                    json.dumps(config)
                ))
        except:
            pass  # Config saving is optional
    
    
    def _get_next_comment(self) -> str:
        """Get next comment from the pool"""
        comments = self.config["comments"]["pool"]
        if not comments:
            return "Nice!"
            
        if self.config["comments"]["use_random"]:
            return random.choice(comments)
        else:
            comment = comments[self.comment_index % len(comments)]
            if self.config["comments"].get("cycle_comments", False):
                self.comment_index = (self.comment_index + 1) % len(comments)
            return comment
    
    def _random_delay(self, min_sec: int, max_sec: int):
        """Random delay between actions"""
        delay = random.uniform(min_sec, max_sec)
        print(f"⏸ Waiting {delay:.1f} seconds...")
        
        # Log delay to database
        self.log_action(
            action_type='delay',
            target_id=f"{delay:.1f}s",
            target_username=None,
            success=True,
            response_data={'min': min_sec, 'max': max_sec, 'actual': delay}
        )
        
        self.page.wait_for_timeout(int(delay * 1000))
    
    def verify_login(self) -> bool:
        """Verify we're still logged in"""
        print("\nVerifying login status...")
        result = self.explore_scraper.verify_login_with_graphql()
        
        # Log verification to database
        self.log_action(
            action_type='verify_login',
            target_id=self.username,
            target_username=self.username,
            success=result
        )
        
        return result
    
    def get_explore_posts_via_api(
        self,
        query: Optional[str] = None,
        next_max_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """Get explore posts using API/GraphQL (safe structure)."""
        print("\n" + "=" * 50)
        print("FETCHING EXPLORE POSTS VIA API")
        print("=" * 50)

        api_params = {
            "query": query,
            "next_max_id": next_max_id[:20] if next_max_id else None,
        }

        if query:
            print(f"Search query: {query}")
            if next_max_id:
                print(f"Pagination: next_max_id = {next_max_id[:20]}...")
            explore_data = self.explore_scraper.search_explore(query, next_max_id=next_max_id)
        else:
            print("General explore (no specific query)")
            explore_data = self.explore_scraper.get_general_explore(max_id=next_max_id)

        # Log sintesi risposta
        if explore_data:
            has_media_grid = "media_grid" in explore_data
            items_count = len(explore_data.get("items", []))
            self.log_api_request(
                endpoint="explore_search" if query else "explore_general",
                params=api_params,
                response={
                    "success": True,
                    "has_media_grid": has_media_grid,
                    "items_count": items_count,
                    "has_next_page_root": bool(explore_data.get("next_max_id")),
                },
                success=True,
            )
        else:
            self.log_api_request(
                endpoint="explore_search" if query else "explore_general",
                params=api_params,
                response={"success": False, "error": "No data returned"},
                success=False,
            )

        if not explore_data:
            print("✗ Failed to get explore data")
            return [], None, False

        # Persist request/response completa
        self.save_api_request_response(
            endpoint="explore_search" if query else "explore_general",
            url="/web/search/topsearch/" if query else "/api/v1/discover/web/explore_grid/",
            params=api_params,
            response_data=explore_data,
        )

        posts: List[Dict[str, Any]] = []

        # 1) Vecchio formato (items[*].media)
        items = explore_data.get("items", [])
        if items:
            print(f"✓ Found {len(items)} items (old format)")
            for item in items:
                media = item.get("media")
                if media:
                    posts.append(media)
                    self.save_post_to_db(media, action_taken=None)

        # 2) Nuovo formato (media_grid.sections[*].layout_content.medias[*].media)
        elif "media_grid" in explore_data:
            media_grid = explore_data["media_grid"]
            sections = media_grid.get("sections", [])
            print(f"✓ Found {len(sections)} sections (new format)")
            for section in sections:
                layout = section.get("layout_content") or {}
                medias = layout.get("medias") or []
                for media_item in medias:
                    media = media_item.get("media", media_item)
                    if media:
                        posts.append(media)
                        self.save_post_to_db(media, action_taken=None)
            print(f"✓ Extracted {len(posts)} posts from sections")

        # Paginazione (preferisci i campi dentro media_grid)
        next_id = None
        has_more = False
        if "media_grid" in explore_data:
            next_id = explore_data["media_grid"].get("next_max_id")
            has_more = bool(explore_data["media_grid"].get("has_more"))
        else:
            next_id = explore_data.get("next_max_id")
            has_more = bool(next_id)

        print(f"✓ Total posts extracted: {len(posts)}")
        if has_more and next_id:
            print(f"✓ More pages available (next_max_id: {str(next_id)[:20]}...)")

        return posts, next_id, has_more

    def process_post(self, post: Dict[str, Any]) -> bool:
        """Process a single post with like/comment - with complete DB tracking"""
        media_id = post.get('id') or post.get('pk')
        media_code = post.get('code') or post.get('media_code')
        owner = post.get('owner', {})
        owner_username = owner.get('username') if isinstance(owner, dict) else post.get('owner_username')
        
        if not media_id:
            print("⚠ No media ID found, skipping")
            return False
        
        if media_id in self.processed_posts:
            print(f"⚠ Already processed {media_id}, skipping")
            return False
        
        print(f"\n{'='*50}")
        print(f"Processing post: {media_code or media_id}")
        if owner_username:
            print(f"Owner: @{owner_username}")
        print(f"{'='*50}")
        
        self.stats['posts_processed'] += 1
        self.processed_posts.add(media_id)
        actions_taken = []
        
        # Check if already liked
        has_liked = post.get('has_liked', False)
        if has_liked:
            print(f"→ Post already liked, skipping like action")
        
        # Like the post
        if self.config["explore"]["actions"]["like"] and not has_liked:
            if self.stats['likes'] < self.config["limits"]["max_likes_per_session"]:
                print(f"→ Liking post {media_code}...")
                
                # Use GraphQL like action
                self.action_manager.add_action(
                    self.like_action,
                    target_id=media_id,
                    target_username=owner_username
                )
                
                results = self.action_manager.execute_queue(delay_between=False)
                
                if results and results[0].success:
                    print(f"  ✓ Liked successfully")
                    self.stats['likes'] += 1
                    actions_taken.append('like')
                    
                    # Log successful like
                    self.log_action(
                        action_type='like',
                        target_id=media_id,
                        target_username=owner_username,
                        success=True,
                        response_data=results[0].response_data
                    )
                else:
                    error_msg = results[0].error_message if results else "Unknown error"
                    print(f"  ✗ Like failed: {error_msg}")
                    self.stats['like_errors'].append({
                        'media_id': media_id,
                        'error': error_msg
                    })
                    
                    # Log failed like
                    self.log_action(
                        action_type='like',
                        target_id=media_id,
                        target_username=owner_username,
                        success=False,
                        error_message=error_msg
                    )
                
                # Small delay between actions
                self._random_delay(
                    self.config["delays"]["between_actions_min"],
                    self.config["delays"]["between_actions_max"]
                )
        
        # Comment on the post
        if self.config["explore"]["actions"]["comment"]:
            if self.stats['comments'] < self.config["limits"]["max_comments_per_session"]:
                comment_text = self._get_next_comment()
                print(f"→ Commenting on post {media_code}: '{comment_text}'")
                
                # Use GraphQL comment action - pass media_code in extra params
                self.action_manager.add_action(
                    self.comment_action,
                    target_id=media_id,
                    target_username=owner_username,
                    comment_text=comment_text,
                    media_code=media_code  # Pass the actual media code
                )
                
                results = self.action_manager.execute_queue(delay_between=False)
                
                if results and results[0].success:
                    print(f"  ✓ Commented successfully")
                    self.stats['comments'] += 1
                    actions_taken.append('comment')
                    
                    # Save comment to database
                    comment_id = results[0].response_data.get('comment_id') if results[0].response_data else None
                    self.save_comment_to_db(
                        media_id=media_id,
                        media_code=media_code,
                        comment_text=comment_text,
                        comment_id=comment_id,
                        success=True
                    )
                else:
                    error_msg = results[0].error_message if results else "Unknown error"
                    print(f"  ✗ Comment failed: {error_msg}")
                    self.stats['comment_errors'].append({
                        'media_id': media_id,
                        'error': error_msg
                    })
                    
                    # Log failed comment
                    self.save_comment_to_db(
                        media_id=media_id,
                        media_code=media_code,
                        comment_text=comment_text,
                        success=False
                    )
        
        # Update post in database with actions taken
        if actions_taken:
            action_str = 'both' if len(actions_taken) == 2 else actions_taken[0]
            self.save_post_to_db(post, action_taken=action_str)
        
        # Update session statistics in database
        self.update_session_stats()
        
        print(f"✓ Post processed: {len(actions_taken)} action(s)")
        return len(actions_taken) > 0
    
    def run_automation(self, search_query: Optional[str] = None) -> Dict[str, Any]:
        """Run the explore automation - with complete database tracking"""
        print("\n" + "="*60)
        print("STARTING EXPLORE AUTOMATION (API MODE)")
        print("="*60)
        print(f"Profile: @{self.username}")
        print(f"Session ID: #{self.session_id}")
        if search_query:
            print(f"Search: {search_query}")
        print(f"Max posts: {self.config['explore']['max_posts']}")
        print(f"Max likes: {self.config['limits']['max_likes_per_session']}")
        print(f"Max comments: {self.config['limits']['max_comments_per_session']}")
        print("="*60)
        
        # Update session with search query
        if search_query and self.session_id:
            with self.db.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE automation_sessions SET search_query = %s WHERE id = %s",
                    (search_query, self.session_id)
                )
        
        try:
            # Verify login
            if not self.verify_login():
                print("✗ Not logged in!")
                self.end_session('error')
                return self.stats
            
            # Main automation loop
            next_max_id = None
            total_posts_to_process = self.config['explore']['max_posts']
            posts_processed_count = 0
            
            while posts_processed_count < total_posts_to_process:
                # Get posts from API
                posts, next_max_id, has_more = self.get_explore_posts_via_api(search_query, next_max_id)
                
                if not posts:
                    print("✗ No posts retrieved")
                    break
                
                # Process each post
                for post in posts:
                    if posts_processed_count >= total_posts_to_process:
                        break
                    
                    try:
                        success = self.process_post(post)
                        if success:
                            posts_processed_count += 1
                        
                        # Delay between posts
                        if posts_processed_count < total_posts_to_process:
                            self._random_delay(
                                self.config["delays"]["between_posts_min"],
                                self.config["delays"]["between_posts_max"]
                            )
                        
                    except Exception as e:
                        print(f"✗ Error processing post: {e}")
                        self.stats['errors'] += 1
                        
                        # Log error to database
                        self.log_action(
                            action_type='error',
                            target_id=post.get('id', 'unknown'),
                            target_username=None,
                            success=False,
                            error_message=str(e)
                        )
                        
                        if self.config["limits"]["stop_on_error"]:
                            print("✗ Stopping due to error (stop_on_error is enabled)")
                            break
                
                # Check if we need more posts
                if posts_processed_count >= total_posts_to_process:
                    print(f"\n✓ Reached target of {total_posts_to_process} posts")
                    break
                
                if not has_more:
                    print("\n✓ No more posts available")
                    break
            
            # Final statistics
            print("\n" + "="*60)
            print("AUTOMATION COMPLETE")
            print("="*60)
            print(f"Posts processed: {self.stats['posts_processed']}")
            print(f"Likes: {self.stats['likes']}")
            print(f"Comments: {self.stats['comments']}")
            print(f"Errors: {self.stats['errors']}")
            
            if self.stats['like_errors']:
                print(f"Like errors: {len(self.stats['like_errors'])}")
            if self.stats['comment_errors']:
                print(f"Comment errors: {len(self.stats['comment_errors'])}")
            
            print("="*60)
            
            # End session successfully
            self.end_session('completed')
            
        except KeyboardInterrupt:
            print("\n⚠ Automation stopped by user")
            self.end_session('stopped')
        except Exception as e:
            print(f"\n✗ Automation error: {e}")
            self.end_session('error')
        
        return self.stats
    
    def end_session(self, status: str = 'completed'):
        """End the automation session"""
        try:
            # Update final stats
            self.update_session_stats()
            
            # Mark session as ended
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE automation_sessions
                    SET ended_at = NOW(),
                        status = %s
                    WHERE id = %s
                """, (status, self.session_id))
            
            print(f"✓ Session #{self.session_id} ended with status: {status}")
            
            # Generate session report
            self.generate_session_report()
            
        except Exception as e:
            print(f"Error ending session: {e}")
    
    def generate_session_report(self):
        """Generate detailed session report from database"""
        try:
            with self.db.get_cursor() as cursor:
                # Get session summary
                cursor.execute("""
                    SELECT * FROM automation_sessions WHERE id = %s
                """, (self.session_id,))
                session = cursor.fetchone()
                
                # Get action counts
                cursor.execute("""
                    SELECT action_type, COUNT(*) as count, 
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                    FROM action_logs
                    WHERE session_id = %s
                    GROUP BY action_type
                """, (self.session_id,))
                actions = cursor.fetchall()
                
                # Get posts interacted with
                cursor.execute("""
                    SELECT COUNT(DISTINCT media_id) as unique_posts,
                           SUM(CASE WHEN is_liked = 1 THEN 1 ELSE 0 END) as liked,
                           SUM(CASE WHEN is_commented = 1 THEN 1 ELSE 0 END) as commented
                    FROM posts_processed
                    WHERE profile_id = %s 
                    AND processed_at >= (SELECT started_at FROM automation_sessions WHERE id = %s)
                """, (self.profile_id, self.session_id))
                post_stats = cursor.fetchone()
                
                print("\n" + "="*60)
                print("SESSION REPORT")
                print("="*60)
                print(f"Session ID: #{self.session_id}")
                print(f"Profile: @{self.username}")
                if session:
                    print(f"Started: {session['started_at']}")
                    print(f"Ended: {session['ended_at']}")
                    print(f"Duration: {(session['ended_at'] - session['started_at']).total_seconds():.1f}s")
                    print(f"Status: {session['status']}")
                    if session['search_query']:
                        print(f"Search Query: {session['search_query']}")
                
                print("\nActions Summary:")
                for action in actions:
                    print(f"  {action['action_type']}: {action['successful']}/{action['count']} successful")
                
                if post_stats:
                    print(f"\nPosts Interaction:")
                    print(f"  Unique posts: {post_stats['unique_posts']}")
                    print(f"  Liked: {post_stats['liked']}")
                    print(f"  Commented: {post_stats['commented']}")
                
                print("="*60)
                
        except Exception as e:
            print(f"Error generating report: {e}")
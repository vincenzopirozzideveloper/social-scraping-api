"""Explore automation using only API calls (no visual interaction)"""

import json
import random
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from ..api import Endpoints, GraphQLClient
from ..actions import ActionManager
from ..actions.interaction_graphql import LikeActionGraphQL, CommentActionGraphQL
from ..scrapers.explore import ExploreScraper


class ExploreAPIAutomation:
    """API-based Explore Automation for Instagram"""
    
    def __init__(self, page, session_manager, username: str, config_path: str = "automation_config.json"):
        self.page = page
        self.session_manager = session_manager
        self.username = username
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.explore_scraper = ExploreScraper(page, session_manager, username)
        self.action_manager = ActionManager(page, session_manager, username)
        self.like_action = LikeActionGraphQL(page, session_manager, username)
        self.comment_action = CommentActionGraphQL(page, session_manager, username)
        
        # Statistics
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
        
        # Create debug directory
        from pathlib import Path
        from datetime import datetime
        self.debug_dir = Path("debug_automation") / username / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        print(f"Debug directory: {self.debug_dir}")
        
    def _load_config(self, config_path: str) -> Dict:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Configuration file {config_path} not found. Using defaults.")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        return {
            "explore": {"enabled": True, "max_posts": 10, "actions": {"like": True, "comment": True}},
            "comments": {"pool": ["Nice!", "Great!"], "use_random": True},
            "delays": {"between_posts_min": 3, "between_posts_max": 8, 
                      "between_actions_min": 1, "between_actions_max": 3},
            "limits": {"max_likes_per_session": 50, "max_comments_per_session": 30, "stop_on_error": True}
        }
    
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
        self.page.wait_for_timeout(int(delay * 1000))
    
    def verify_login(self) -> bool:
        """Verify we're still logged in"""
        print("\nVerifying login status...")
        return self.explore_scraper.verify_login_with_graphql()
    
    def get_explore_posts_via_api(self, query: Optional[str] = None, next_max_id: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """Get explore posts using GraphQL API"""
        print("\n" + "="*50)
        print("FETCHING EXPLORE POSTS VIA API")
        print("="*50)
        
        if query:
            print(f"Search query: {query}")
            if next_max_id:
                print(f"Pagination: next_max_id = {next_max_id[:20]}...")
            # Use search explore with pagination
            explore_data = self.explore_scraper.search_explore(query, next_max_id=next_max_id)
        else:
            # For general explore, we need to make the GraphQL request
            # This would require implementing the explore timeline GraphQL query
            # For now, use a default search query
            print("Using default explore search: 'trending'")
            explore_data = self.explore_scraper.search_explore("trending", next_max_id=next_max_id)
        
        if not explore_data:
            print("✗ Failed to get explore data")
            return [], None, False
        
        # Extract pagination info
        next_max_id = explore_data.get('next_max_id')
        has_more = explore_data.get('has_more', False) or bool(next_max_id)
        
        posts = []
        
        # The ACTUAL structure from search_explore response is:
        # explore_data.media_grid.sections[].layout_content.medias[].media
        
        # Check if we have media_grid with sections (this is the actual format!)
        if 'media_grid' in explore_data and 'sections' in explore_data.get('media_grid', {}):
            sections = explore_data['media_grid']['sections']
            print(f"Found {len(sections)} sections in media_grid")
            
            for section_idx, section in enumerate(sections):
                if 'layout_content' in section and 'medias' in section['layout_content']:
                    medias = section['layout_content']['medias']
                    print(f"  Section {section_idx}: {len(medias)} posts")
                    
                    for media_item in medias:
                        if len(posts) >= self.config["explore"]["max_posts_per_page"]:
                            break
                            
                        if 'media' in media_item:
                            media = media_item['media']
                            media_id = media.get('id') or media.get('pk')
                            media_code = media.get('code')
                            
                            if media_id and str(media_id) not in self.processed_posts:
                                # Extract owner info
                                owner = media.get('user', {})
                                if not owner:
                                    owner = media.get('owner', {})
                                
                                post_data = {
                                    'media_id': str(media_id),
                                    'media_code': media_code,
                                    'media_type': media.get('media_type'),
                                    'owner': owner,
                                    'has_liked': media.get('has_liked', False),
                                    'like_count': media.get('like_count', 0),
                                    'comment_count': media.get('comment_count', 0),
                                    'caption': media.get('caption', {}).get('text', '') if media.get('caption') else ''
                                }
                                posts.append(post_data)
                                self.processed_posts.add(str(media_id))
                
                if len(posts) >= self.config["explore"]["max_posts_per_page"]:
                    break
        
        # Fallback: if no sections, check for direct media structure
        elif 'media' in explore_data and 'medias' in explore_data['media']:
            medias = explore_data['media']['medias']
            print(f"Found direct media structure with {len(medias)} posts")
            
            for media_item in medias[:self.config["explore"]["max_posts_per_page"]]:
                media = media_item.get('media', {})
                media_id = media.get('id') or media.get('pk')
                media_code = media.get('code')
                
                if media_id and str(media_id) not in self.processed_posts:
                    owner = media.get('user', media.get('owner', {}))
                    
                    post_data = {
                        'media_id': str(media_id),
                        'media_code': media_code,
                        'media_type': media.get('media_type'),
                        'owner': owner,
                        'has_liked': media.get('has_liked', False),
                        'like_count': media.get('like_count', 0),
                        'comment_count': media.get('comment_count', 0)
                    }
                    posts.append(post_data)
                    self.processed_posts.add(str(media_id))
        
        print(f"✓ Found {len(posts)} posts to process")
        print(f"  Has more pages: {has_more}")
        if next_max_id:
            print(f"  Next page ID: {next_max_id[:20]}...")
        
        for i, post in enumerate(posts[:5]):  # Show first 5 posts
            print(f"  {i+1}. {post['media_code']} by @{post['owner'].get('username', 'unknown')}")
        
        return posts, next_max_id, has_more
    
    def process_post(self, post_data: Dict[str, Any]) -> bool:
        """Process a single post with like and comment actions"""
        try:
            media_id = post_data['media_id']
            media_code = post_data.get('media_code', '')
            
            print(f"\n{'='*50}")
            print(f"PROCESSING POST")
            print(f"{'='*50}")
            print(f"Media ID: {media_id}")
            print(f"Media Code: {media_code}")
            print(f"Owner: @{post_data['owner'].get('username', 'unknown')}")
            print(f"Already liked: {post_data.get('has_liked', False)}")
            
            # Save post data for debug
            import json
            debug_file = self.debug_dir / f"post_{media_code}.json"
            with open(debug_file, 'w') as f:
                json.dump(post_data, f, indent=2, default=str)
            
            overall_success = True
            post_processed = False
            
            # Like action if enabled and not already liked
            if self.config["explore"]["actions"]["like"] and not post_data.get('has_liked', False):
                if self.stats["likes"] < self.config["limits"]["max_likes_per_session"]:
                    self._random_delay(
                        self.config["delays"]["between_actions_min"],
                        self.config["delays"]["between_actions_max"]
                    )
                    
                    try:
                        like_result = self.like_action.execute(media_id, media_code)
                        if like_result.success:
                            self.stats["likes"] += 1
                            post_processed = True
                            # Update session stats in DB
                            if self.db and self.session_id:
                                try:
                                    self.db.update_session(self.session_id, likes_count=self.stats["likes"])
                                except:
                                    pass
                        else:
                            self.stats["errors"] += 1
                            self.stats["like_errors"].append({
                                'media_code': media_code,
                                'error': like_result.error_message
                            })
                            overall_success = False
                    except Exception as e:
                        print(f"✗ Exception during like: {e}")
                        self.stats["errors"] += 1
                        self.stats["like_errors"].append({
                            'media_code': media_code,
                            'error': str(e)
                        })
                        overall_success = False
                else:
                    print("⚠ Like limit reached for this session")
            
            # Comment action if enabled
            if self.config["explore"]["actions"]["comment"]:
                if self.stats["comments"] < self.config["limits"]["max_comments_per_session"]:
                    self._random_delay(
                        self.config["delays"]["between_actions_min"],
                        self.config["delays"]["between_actions_max"]
                    )
                    
                    try:
                        comment_text = self._get_next_comment()
                        comment_result = self.comment_action.execute(media_id, comment_text, media_code)
                        if comment_result.success:
                            self.stats["comments"] += 1
                            post_processed = True
                            # Update session stats in DB
                            if self.db and self.session_id:
                                try:
                                    self.db.update_session(self.session_id, comments_count=self.stats["comments"])
                                except:
                                    pass
                        else:
                            self.stats["errors"] += 1
                            self.stats["comment_errors"].append({
                                'media_code': media_code,
                                'error': comment_result.error_message
                            })
                            overall_success = False
                    except Exception as e:
                        print(f"✗ Exception during comment: {e}")
                        self.stats["errors"] += 1
                        self.stats["comment_errors"].append({
                            'media_code': media_code,
                            'error': str(e)
                        })
                        overall_success = False
                else:
                    print("⚠ Comment limit reached for this session")
            
            # Count as processed if at least one action was attempted
            if post_processed:
                self.stats["posts_processed"] += 1
            
            if not overall_success and self.config["limits"]["stop_on_error"]:
                print("⚠ Stopping due to error (stop_on_error is enabled)")
                return False
            
            return True
            
        except Exception as e:
            print(f"✗ Error processing post: {e}")
            self.stats["errors"] += 1
            
            # Save error for debug
            import json
            error_file = self.debug_dir / f"error_{media_code}.json"
            with open(error_file, 'w') as f:
                json.dump({
                    'media_code': media_code,
                    'error': str(e),
                    'post_data': post_data
                }, f, indent=2, default=str)
            
            return False
    
    def run_automation(self, search_query: Optional[str] = None) -> Dict[str, int]:
        """Run the explore automation with infinite scrolling"""
        try:
            print("\n" + "="*50)
            print("EXPLORE API AUTOMATION (INFINITE MODE)")
            print("="*50)
            print(f"Profile: @{self.username}")
            print(f"Infinite scroll: {self.config['explore'].get('infinite_scroll', True)}")
            print(f"Posts per page: {self.config['explore']['max_posts_per_page']}")
            print(f"Pause every {self.config['explore']['pause_every_n_posts']} posts")
            print(f"Actions: Like={self.config['explore']['actions']['like']}, "
                  f"Comment={self.config['explore']['actions']['comment']}")
            print(f"Comment pool: {len(self.config['comments']['pool'])} messages")
            print(f"Limits: {self.config['limits']['max_likes_per_session']} likes, "
                  f"{self.config['limits']['max_comments_per_session']} comments")
            print("="*50)
            
            # Verify login
            if not self.verify_login():
                print("✗ Login verification failed")
                return self.stats
            
            # Main pagination loop
            next_max_id = None
            page_number = 0
            total_posts_processed = 0
            consecutive_errors = 0
            
            while True:
                page_number += 1
                
                print(f"\n{'='*70}")
                print(f"PAGE {page_number}")
                print(f"{'='*70}")
                
                # Get posts from explore API with pagination
                posts, next_max_id, has_more = self.get_explore_posts_via_api(search_query, next_max_id)
                
                if not posts:
                    print("✗ No posts found on this page")
                    if not has_more:
                        print("✓ No more pages available")
                        break
                    # Try next page even if this one was empty
                    continue
                
                # Process each post on this page
                for i, post_data in enumerate(posts):
                    total_posts_processed += 1
                    
                    print(f"\n{'='*50}")
                    print(f"POST {i+1}/{len(posts)} (Total: {total_posts_processed})")
                    print(f"{'='*50}")
                    
                    success = self.process_post(post_data)
                    
                    if not success:
                        consecutive_errors += 1
                        if consecutive_errors >= self.config["limits"].get("max_consecutive_errors", 5):
                            print(f"\n⚠ Too many consecutive errors ({consecutive_errors}), stopping")
                            return self.stats
                    else:
                        consecutive_errors = 0  # Reset on success
                    
                    # Check if we should take a pause
                    if total_posts_processed % self.config["explore"]["pause_every_n_posts"] == 0:
                        pause_duration = random.uniform(
                            self.config["explore"]["pause_duration_min"],
                            self.config["explore"]["pause_duration_max"]
                        )
                        print(f"\n{'='*50}")
                        print(f"⏸ PAUSE after {total_posts_processed} posts")
                        print(f"  Pausing for {pause_duration:.0f} seconds...")
                        print(f"  Stats so far: {self.stats['likes']} likes, {self.stats['comments']} comments")
                        print(f"{'='*50}")
                        self.page.wait_for_timeout(int(pause_duration * 1000))
                    
                    # Delay between posts
                    if i < len(posts) - 1:
                        self._random_delay(
                            self.config["delays"]["between_posts_min"],
                            self.config["delays"]["between_posts_max"]
                        )
                    
                    # Check session limits
                    if (self.stats["likes"] >= self.config["limits"]["max_likes_per_session"] and
                        self.stats["comments"] >= self.config["limits"]["max_comments_per_session"]):
                        print("\n⚠ Session limits reached for both likes and comments")
                        return self.stats
                
                # Check if we should continue to next page
                if not self.config['explore'].get('infinite_scroll', True):
                    print("\n✓ Infinite scroll disabled, stopping after first page")
                    break
                
                if not has_more or not next_max_id:
                    print("\n✓ No more pages available")
                    break
                
                # Delay between pages
                print(f"\nMoving to next page...")
                self._random_delay(
                    self.config["delays"]["between_pages_min"],
                    self.config["delays"]["between_pages_max"]
                )
            
            # Print final statistics
            print("\n" + "="*50)
            print("AUTOMATION COMPLETE")
            print("="*50)
            print(f"✓ Total pages processed: {page_number}")
            print(f"✓ Posts processed: {self.stats['posts_processed']}")
            print(f"✓ Likes: {self.stats['likes']}")
            print(f"✓ Comments: {self.stats['comments']}")
            if self.stats['errors'] > 0:
                print(f"⚠ Errors: {self.stats['errors']}")
            
            success_actions = self.stats['likes'] + self.stats['comments']
            attempted_actions = self.stats['posts_processed'] * 2
            if attempted_actions > 0:
                success_rate = (success_actions / attempted_actions) * 100
                print(f"Success rate: {success_rate:.1f}%")
            
            print("="*50)
            
            return self.stats
            
        except KeyboardInterrupt:
            print("\n\n⚠ Automation interrupted by user")
            print(f"Processed {self.stats['posts_processed']} posts before stopping")
            return self.stats
        except Exception as e:
            print(f"✗ Automation error: {e}")
            self.stats["errors"] += 1
            return self.stats
    
    def reset_stats(self):
        """Reset all statistics"""
        self.stats = {
            "likes": 0,
            "comments": 0,
            "errors": 0,
            "posts_processed": 0
        }
        self.processed_posts.clear()
        self.comment_index = 0
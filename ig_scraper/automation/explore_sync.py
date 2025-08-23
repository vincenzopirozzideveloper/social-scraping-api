import json
import random
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
from ..api.endpoints import Endpoints


class ExploreAutomation:
    """Synchronous version of Explore Automation for Instagram"""
    
    def __init__(self, page, config_path: str = "automation_config.json"):
        self.page = page
        self.endpoints = Endpoints()
        self.config = self._load_config(config_path)
        self.stats = {
            "likes": 0,
            "comments": 0,
            "errors": 0,
            "posts_processed": 0
        }
        self.comment_index = 0
        self.processed_posts = set()
        
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
                      "between_actions_min": 1, "between_actions_max": 3, "page_load_wait": 5},
            "limits": {"max_likes_per_session": 50, "max_comments_per_session": 30, "stop_on_error": True}
        }
    
    def _get_next_comment(self) -> str:
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
        delay = random.uniform(min_sec, max_sec)
        print(f"Waiting {delay:.1f} seconds...")
        self.page.wait_for_timeout(int(delay * 1000))
    
    def navigate_to_explore(self) -> bool:
        try:
            print("Navigating to Explore page...")
            
            # Navigate to explore
            self.page.goto("https://www.instagram.com/explore/", wait_until='networkidle')
            self.page.wait_for_timeout(self.config["delays"]["page_load_wait"] * 1000)
            
            print("Explore page loaded successfully")
            return True
            
        except Exception as e:
            print(f"Error navigating to explore: {e}")
            self.stats["errors"] += 1
            return False
    
    def get_explore_posts(self) -> List[Dict[str, str]]:
        try:
            print("Getting explore posts...")
            
            # Wait for posts to load
            self.page.wait_for_selector('article a[href*="/p/"]', timeout=10000)
            
            # Get all post links
            posts = self.page.query_selector_all('article a[href*="/p/"]')
            
            if not posts:
                print("No posts found in explore feed")
                return []
            
            post_data = []
            for post in posts[:self.config["explore"]["max_posts"]]:
                href = post.get_attribute('href')
                if href:
                    # Extract post ID from URL
                    post_id = href.split('/p/')[1].strip('/')
                    if post_id not in self.processed_posts:
                        post_data.append({
                            'url': f"https://www.instagram.com{href}",
                            'post_id': post_id
                        })
                        self.processed_posts.add(post_id)
            
            print(f"Found {len(post_data)} new posts to process")
            return post_data
            
        except Exception as e:
            print(f"Error getting explore posts: {e}")
            self.stats["errors"] += 1
            return []
    
    def like_post(self, post_id: str) -> bool:
        try:
            if self.stats["likes"] >= self.config["limits"]["max_likes_per_session"]:
                print("Like limit reached for this session")
                return False
            
            print(f"Liking post {post_id}...")
            
            # Look for like button (not liked state)
            like_button = self.page.query_selector('svg[aria-label="Like"]')
            if not like_button:
                print("Post might already be liked or like button not found")
                return False
            
            # Set up response listener for like action
            with self.page.expect_response(
                lambda response: f"/web/likes/{post_id}/like/" in response.url or 
                                f"/web/likes/{post_id}/unlike/" in response.url,
                timeout=10000
            ) as response_info:
                # Click the like button
                like_button.click()
            
            # Check response
            like_response = response_info.value
            
            if like_response.status == 200:
                print(f"✓ Post liked successfully")
                self.stats["likes"] += 1
                return True
            else:
                print(f"Like failed with status: {like_response.status}")
                self.stats["errors"] += 1
                return False
                
        except Exception as e:
            print(f"Error liking post: {e}")
            self.stats["errors"] += 1
            return False
    
    def comment_post(self, post_id: str) -> bool:
        try:
            if self.stats["comments"] >= self.config["limits"]["max_comments_per_session"]:
                print("Comment limit reached for this session")
                return False
            
            comment_text = self._get_next_comment()
            print(f"Commenting on post {post_id}: '{comment_text}'")
            
            # Click comment button to open comment box
            comment_button = self.page.query_selector('svg[aria-label="Comment"]')
            if comment_button:
                comment_button.click()
                self.page.wait_for_timeout(1000)
            
            # Find comment textarea
            comment_textarea = self.page.query_selector('textarea[aria-label*="comment" i], textarea[placeholder*="comment" i]')
            if not comment_textarea:
                # Try alternative selector
                comment_textarea = self.page.query_selector('form textarea')
            
            if not comment_textarea:
                print("Comment textarea not found")
                return False
            
            # Type the comment
            comment_textarea.fill(comment_text)
            self.page.wait_for_timeout(500)
            
            # Set up response listener for comment action
            with self.page.expect_response(
                lambda response: f"/web/comments/{post_id}/add/" in response.url,
                timeout=10000
            ) as response_info:
                # Find and click Post button
                post_button = self.page.query_selector('button[type="submit"]:has-text("Post")')
                if not post_button:
                    post_button = self.page.query_selector('div[role="button"]:has-text("Post")')
                
                if post_button:
                    post_button.click()
                else:
                    # Fallback to Enter key
                    self.page.keyboard.press("Enter")
            
            # Check response
            comment_response = response_info.value
            
            if comment_response.status == 200:
                print(f"✓ Comment posted successfully")
                self.stats["comments"] += 1
                return True
            else:
                print(f"Comment failed with status: {comment_response.status}")
                self.stats["errors"] += 1
                return False
                
        except Exception as e:
            print(f"Error commenting on post: {e}")
            self.stats["errors"] += 1
            return False
    
    def process_post(self, post_data: Dict[str, Any]) -> bool:
        try:
            print(f"\nProcessing post: {post_data['post_id']}")
            
            # Navigate to post
            self.page.goto(post_data['url'], wait_until='networkidle')
            self.page.wait_for_timeout(2000)
            
            success = True
            
            # Perform like action if enabled
            if self.config["explore"]["actions"]["like"]:
                self._random_delay(
                    self.config["delays"]["between_actions_min"],
                    self.config["delays"]["between_actions_max"]
                )
                like_success = self.like_post(post_data['post_id'])
                success = success and like_success
            
            # Perform comment action if enabled
            if self.config["explore"]["actions"]["comment"]:
                self._random_delay(
                    self.config["delays"]["between_actions_min"],
                    self.config["delays"]["between_actions_max"]
                )
                comment_success = self.comment_post(post_data['post_id'])
                success = success and comment_success
            
            self.stats["posts_processed"] += 1
            
            if not success and self.config["limits"]["stop_on_error"]:
                print("Stopping due to error (stop_on_error is enabled)")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error processing post: {e}")
            self.stats["errors"] += 1
            return False
    
    def run_automation(self) -> Dict[str, int]:
        try:
            print("\n" + "="*50)
            print("STARTING EXPLORE AUTOMATION")
            print("="*50)
            print(f"Max posts: {self.config['explore']['max_posts']}")
            print(f"Actions: Like={self.config['explore']['actions']['like']}, "
                  f"Comment={self.config['explore']['actions']['comment']}")
            print(f"Comment pool: {len(self.config['comments']['pool'])} messages")
            print("="*50)
            
            # Navigate to explore page
            if not self.navigate_to_explore():
                print("Failed to navigate to explore page")
                return self.stats
            
            # Get posts from explore page
            posts = self.get_explore_posts()
            
            if not posts:
                print("No posts found to process")
                return self.stats
            
            # Process each post
            for i, post_data in enumerate(posts):
                print(f"\n{'='*50}")
                print(f"POST {i+1}/{len(posts)}")
                print(f"{'='*50}")
                
                success = self.process_post(post_data)
                
                if not success and self.config["limits"]["stop_on_error"]:
                    print("Automation stopped due to error")
                    break
                
                # Delay between posts (except for last one)
                if i < len(posts) - 1:
                    self._random_delay(
                        self.config["delays"]["between_posts_min"],
                        self.config["delays"]["between_posts_max"]
                    )
                
                # Go back to explore page
                print("Returning to explore page...")
                self.page.goto("https://www.instagram.com/explore/", wait_until='domcontentloaded')
                self.page.wait_for_timeout(2000)
            
            # Print final statistics
            print("\n" + "="*50)
            print("AUTOMATION COMPLETE")
            print("="*50)
            print(f"Posts processed: {self.stats['posts_processed']}")
            print(f"Likes: {self.stats['likes']}")
            print(f"Comments: {self.stats['comments']}")
            print(f"Errors: {self.stats['errors']}")
            print("="*50)
            
            return self.stats
            
        except Exception as e:
            print(f"Automation error: {e}")
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
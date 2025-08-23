import json
import random
import asyncio
from typing import Dict, List, Optional, Any
from playwright.async_api import Page, Response
from ig_scraper.api.endpoints import Endpoints


class ExploreAutomation:
    def __init__(self, page: Page, config_path: str = "automation_config.json"):
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
            "delays": {"between_posts_min": 3, "between_posts_max": 8, "between_actions_min": 1, "between_actions_max": 3, "page_load_wait": 5},
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
    
    async def _random_delay(self, min_sec: int, max_sec: int):
        delay = random.uniform(min_sec, max_sec)
        print(f"Waiting {delay:.1f} seconds...")
        await asyncio.sleep(delay)
    
    async def navigate_to_explore(self) -> bool:
        try:
            print("Navigating to Explore page...")
            
            explore_response_promise = self.page.wait_for_response(
                lambda response: "/graphql/query" in response.url and 
                "PolarisFeedTimelineRootV2Query" in response.url,
                timeout=30000
            )
            
            await self.page.goto("https://www.instagram.com/explore/", wait_until='networkidle')
            
            try:
                explore_response = await explore_response_promise
                print(f"Explore feed loaded: {explore_response.status}")
            except:
                print("Explore feed response not captured, but continuing...")
            
            await asyncio.sleep(self.config["delays"]["page_load_wait"])
            
            print("Explore page loaded successfully")
            return True
            
        except Exception as e:
            print(f"Error navigating to explore: {e}")
            self.stats["errors"] += 1
            return False
    
    async def get_explore_posts(self) -> List[Dict[str, str]]:
        try:
            print("Getting explore posts...")
            
            posts = await self.page.query_selector_all('article a[href*="/p/"]')
            
            if not posts:
                print("No posts found in explore feed")
                return []
            
            post_data = []
            for post in posts[:self.config["explore"]["max_posts"]]:
                href = await post.get_attribute('href')
                if href:
                    post_id = href.split('/p/')[1].strip('/')
                    if post_id not in self.processed_posts:
                        post_data.append({
                            'url': f"https://www.instagram.com{href}",
                            'post_id': post_id,
                            'element': post
                        })
                        self.processed_posts.add(post_id)
            
            print(f"Found {len(post_data)} new posts to process")
            return post_data
            
        except Exception as e:
            print(f"Error getting explore posts: {e}")
            self.stats["errors"] += 1
            return []
    
    async def like_post(self, post_id: str) -> bool:
        try:
            if self.stats["likes"] >= self.config["limits"]["max_likes_per_session"]:
                print("Like limit reached for this session")
                return False
            
            print(f"Liking post {post_id}...")
            
            like_button = await self.page.query_selector('svg[aria-label="Like"]')
            if not like_button:
                print("Post might already be liked or like button not found")
                return False
            
            like_response_promise = self.page.wait_for_response(
                lambda response: f"/web/likes/{post_id}/like/" in response.url,
                timeout=10000
            )
            
            await like_button.click()
            
            try:
                like_response = await like_response_promise
                response_data = await like_response.json()
                
                if like_response.status == 200:
                    print(f"✓ Post liked successfully")
                    self.stats["likes"] += 1
                    return True
                else:
                    print(f"Like failed: {response_data}")
                    self.stats["errors"] += 1
                    return False
            except Exception as e:
                print(f"Like response error: {e}")
                self.stats["errors"] += 1
                return False
                
        except Exception as e:
            print(f"Error liking post: {e}")
            self.stats["errors"] += 1
            return False
    
    async def comment_post(self, post_id: str) -> bool:
        try:
            if self.stats["comments"] >= self.config["limits"]["max_comments_per_session"]:
                print("Comment limit reached for this session")
                return False
            
            comment_text = self._get_next_comment()
            print(f"Commenting on post {post_id}: '{comment_text}'")
            
            comment_button = await self.page.query_selector('svg[aria-label="Comment"]')
            if comment_button:
                await comment_button.click()
                await asyncio.sleep(1)
            
            comment_textarea = await self.page.query_selector('textarea[aria-label*="comment"]')
            if not comment_textarea:
                print("Comment textarea not found")
                return False
            
            await comment_textarea.fill(comment_text)
            await asyncio.sleep(0.5)
            
            comment_response_promise = self.page.wait_for_response(
                lambda response: f"/web/comments/{post_id}/add/" in response.url,
                timeout=10000
            )
            
            post_button = await self.page.query_selector('button[type="submit"]:has-text("Post")')
            if not post_button:
                post_button = await self.page.query_selector('div[role="button"]:has-text("Post")')
            
            if post_button:
                await post_button.click()
            else:
                await self.page.keyboard.press("Enter")
            
            try:
                comment_response = await comment_response_promise
                response_data = await comment_response.json()
                
                if comment_response.status == 200:
                    print(f"✓ Comment posted successfully")
                    self.stats["comments"] += 1
                    return True
                else:
                    print(f"Comment failed: {response_data}")
                    self.stats["errors"] += 1
                    return False
            except Exception as e:
                print(f"Comment response error: {e}")
                self.stats["errors"] += 1
                return False
                
        except Exception as e:
            print(f"Error commenting on post: {e}")
            self.stats["errors"] += 1
            return False
    
    async def process_post(self, post_data: Dict[str, Any]) -> bool:
        try:
            print(f"\nProcessing post: {post_data['post_id']}")
            
            await self.page.goto(post_data['url'], wait_until='networkidle')
            await asyncio.sleep(2)
            
            success = True
            
            if self.config["explore"]["actions"]["like"]:
                await self._random_delay(
                    self.config["delays"]["between_actions_min"],
                    self.config["delays"]["between_actions_max"]
                )
                like_success = await self.like_post(post_data['post_id'])
                success = success and like_success
            
            if self.config["explore"]["actions"]["comment"]:
                await self._random_delay(
                    self.config["delays"]["between_actions_min"],
                    self.config["delays"]["between_actions_max"]
                )
                comment_success = await self.comment_post(post_data['post_id'])
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
    
    async def run_automation(self) -> Dict[str, int]:
        try:
            print("\n=== Starting Explore Automation ===")
            print(f"Configuration: Max posts: {self.config['explore']['max_posts']}")
            print(f"Actions: Like={self.config['explore']['actions']['like']}, Comment={self.config['explore']['actions']['comment']}")
            
            if not await self.navigate_to_explore():
                print("Failed to navigate to explore page")
                return self.stats
            
            posts = await self.get_explore_posts()
            
            if not posts:
                print("No posts found to process")
                return self.stats
            
            for i, post_data in enumerate(posts):
                print(f"\n--- Processing post {i+1}/{len(posts)} ---")
                
                success = await self.process_post(post_data)
                
                if not success and self.config["limits"]["stop_on_error"]:
                    print("Automation stopped due to error")
                    break
                
                if i < len(posts) - 1:
                    await self._random_delay(
                        self.config["delays"]["between_posts_min"],
                        self.config["delays"]["between_posts_max"]
                    )
                
                await self.page.goto("https://www.instagram.com/explore/", wait_until='domcontentloaded')
                await asyncio.sleep(2)
            
            print("\n=== Automation Complete ===")
            print(f"Stats: {self.stats}")
            
            return self.stats
            
        except Exception as e:
            print(f"Automation error: {e}")
            self.stats["errors"] += 1
            return self.stats
    
    def reset_stats(self):
        self.stats = {
            "likes": 0,
            "comments": 0,
            "errors": 0,
            "posts_processed": 0
        }
        self.processed_posts.clear()
        self.comment_index = 0
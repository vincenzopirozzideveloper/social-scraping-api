"""Followers scraper for Instagram with session tracking"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from ..api import Endpoints, GraphQLClient
from ..config import ConfigManager
from ..database import DatabaseManager


class FollowersScraper:
    """Scrape followers from Instagram profiles with session tracking"""
    
    def __init__(self, page, session_manager, username: str):
        self.page = page
        self.session_manager = session_manager
        self.username = username
        
        # Database connection
        self.db = DatabaseManager()
        self.profile = self.db.get_profile_by_username(username)
        if not self.profile:
            self.profile = self.db.get_or_create_profile(username)
        self.profile_id = self.profile['id']
        
        # Track scraping session
        self.scraping_session_id = None
        
        # Load configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config(username)
        
        # Get specific settings
        followers_config = self.config.get('scraping', {}).get('followers', {})
        self.max_count = followers_config.get('max_count', 200)
        self.default_count = followers_config.get('default_count', 12)
        self.pagination_delay = followers_config.get('pagination_delay', 3000)
        self.verify_login = followers_config.get('verify_login', True)
    
    def create_scraping_session(self, target_username: str, target_user_id: str) -> int:
        """Create a new followers scraping session in database"""
        try:
            with self.db.get_cursor() as cursor:
                # Get or create target profile
                cursor.execute("""
                    SELECT id FROM profiles WHERE username = %s
                """, (target_username,))
                target_profile = cursor.fetchone()
                
                if not target_profile:
                    cursor.execute("""
                        INSERT INTO profiles (username, user_id, created_at)
                        VALUES (%s, %s, NOW())
                    """, (target_username, target_user_id))
                    target_profile_id = cursor.lastrowid
                else:
                    target_profile_id = target_profile['id']
                
                # Create scraping session
                cursor.execute("""
                    INSERT INTO followers_scraping_sessions 
                    (profile_id, target_profile_id, target_username, total_followers, started_at)
                    VALUES (%s, %s, %s, 0, NOW())
                """, (self.profile_id, target_profile_id, target_username))
                self.scraping_session_id = cursor.lastrowid
                
                print(f"✓ Created followers scraping session #{self.scraping_session_id}")
                return self.scraping_session_id
        except Exception as e:
            print(f"Error creating scraping session: {e}")
            return None
    
    def save_followers(self, followers: List[Dict], page_number: int = 1) -> int:
        """Save followers to database with session tracking"""
        saved_count = 0
        skipped_count = 0
        try:
            with self.db.get_cursor() as cursor:
                for position, follower in enumerate(followers):
                    user_id = follower.get('id') or follower.get('pk')
                    username = follower.get('username')
                    full_name = follower.get('full_name')
                    
                    if not user_id or not username:
                        continue
                    
                    # Save follower profile if not exists
                    cursor.execute("""
                        INSERT INTO profiles (username, user_id, full_name, created_at)
                        VALUES (%s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE 
                        full_name = VALUES(full_name),
                        updated_at = NOW()
                    """, (username, user_id, full_name))
                    
                    # Get follower profile ID
                    cursor.execute("""
                        SELECT id FROM profiles WHERE username = %s
                    """, (username,))
                    follower_profile = cursor.fetchone()
                    follower_profile_id = follower_profile['id'] if follower_profile else None
                    
                    if follower_profile_id:
                        # Save follower relationship (use INSERT IGNORE to skip duplicates)
                        cursor.execute("""
                            INSERT IGNORE INTO scraped_followers 
                            (session_id, follower_profile_id, follower_username, follower_user_id,
                             follower_full_name, is_verified, is_private, profile_pic_url,
                             position_in_list, page_number, raw_data)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            self.scraping_session_id,
                            follower_profile_id,
                            username,
                            user_id,
                            full_name,
                            follower.get('is_verified', False),
                            follower.get('is_private', False),
                            follower.get('profile_pic_url'),
                            position + ((page_number - 1) * self.max_count),
                            page_number,
                            json.dumps(follower)
                        ))
                        # Check if actually inserted (not duplicate)
                        if cursor.rowcount > 0:
                            saved_count += 1
                        else:
                            skipped_count += 1
                
                # Update session totals
                if saved_count > 0:
                    cursor.execute("""
                        UPDATE followers_scraping_sessions 
                        SET total_followers = total_followers + %s
                        WHERE id = %s
                    """, (saved_count, self.scraping_session_id))
                    
        except Exception as e:
            print(f"Error saving followers: {e}")
        
        if skipped_count > 0:
            print(f"  → Skipped {skipped_count} duplicates in this session")
        
        return saved_count
    
    def close_scraping_session(self):
        """Close the current scraping session"""
        if self.scraping_session_id:
            try:
                with self.db.get_cursor() as cursor:
                    cursor.execute("""
                        UPDATE followers_scraping_sessions 
                        SET ended_at = NOW()
                        WHERE id = %s
                    """, (self.scraping_session_id,))
                    print(f"  → Scraping session #{self.scraping_session_id} closed")
            except Exception as e:
                print(f"Error closing scraping session: {e}")
    
    def verify_login_with_graphql(self) -> bool:
        """Verify we're still logged in using GraphQL test"""
        try:
            print("\n" + "="*50)
            print("VERIFYING LOGIN STATUS")
            print("="*50)
            
            # Get user ID from cookies
            cookies = self.page.context.cookies()
            user_id = None
            for cookie in cookies:
                if cookie['name'] == 'ds_user_id':
                    user_id = cookie['value']
                    break
            
            if not user_id:
                print("✗ No user ID found in cookies")
                return False
            
            print(f"User ID: {user_id}")
            
            # Load saved GraphQL metadata
            saved_info = self.session_manager.load_session_info(self.username)
            graphql_metadata = None
            if saved_info and 'graphql' in saved_info:
                graphql_metadata = saved_info['graphql']
                print(f"Using saved GraphQL metadata")
            
            # Create GraphQL client and test
            graphql_client = GraphQLClient(self.page, graphql_metadata)
            response_data = graphql_client.get_profile_info(user_id)
            
            if response_data:
                username_from_api = graphql_client.extract_username(response_data)
                if username_from_api:
                    print(f"✓ Login verified! Username: {username_from_api}")
                    return True
            
            print("✗ Could not verify login status")
            return False
            
        except Exception as e:
            print(f"✗ Error verifying login: {e}")
            return False
    
    def get_followers(self, target_user_id: str, count: int = 12, max_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get followers for a specific user"""
        try:
            # Get csrf token from cookies
            cookies = self.page.context.cookies()
            csrf_token = None
            
            for cookie in cookies:
                if cookie['name'] == 'csrftoken':
                    csrf_token = cookie['value']
                    break
            
            # Build URL
            url = f"https://www.instagram.com/api/v1/friendships/{target_user_id}/followers/"
            params = [
                f"count={count}",
                "search_surface=follow_list_page"
            ]
            
            if max_id:
                params.append(f"max_id={max_id}")
            
            full_url = url + "?" + "&".join(params)
            
            print(f"\n→ Fetching {count} followers...")
            if max_id:
                print(f"  Pagination: max_id={max_id[:20]}...")
            
            # Get saved metadata for headers
            saved_info = self.session_manager.load_session_info(self.username)
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            app_id = "936619743392459"
            
            if saved_info and 'graphql' in saved_info:
                graphql_data = saved_info['graphql']
                if graphql_data.get('user_agent'):
                    user_agent = graphql_data['user_agent']
                if graphql_data.get('app_id'):
                    app_id = graphql_data['app_id']
            
            # Build headers
            headers = {
                "accept": "*/*",
                "accept-language": "en-GB,en;q=0.9,it-IT;q=0.8,it;q=0.7,en-US;q=0.6",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "sec-ch-prefers-color-scheme": "light",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                "sec-ch-ua-full-version-list": '"Not;A=Brand";v="99.0.0.0", "Google Chrome";v="139.0.7258.128", "Chromium";v="139.0.7258.128"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-model": '""',
                "sec-ch-ua-platform": '"Windows"',
                "sec-ch-ua-platform-version": '"19.0.0"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": user_agent,
                "x-asbd-id": "359341",
                "x-csrftoken": csrf_token,
                "x-ig-app-id": app_id,
                "x-requested-with": "XMLHttpRequest"
            }
            
            # Make request using browser's fetch
            response = self.page.evaluate(f"""
                (async () => {{
                    const response = await fetch("{full_url}", {{
                        method: 'GET',
                        headers: {json.dumps(headers)},
                        credentials: 'include'
                    }});
                    
                    const data = await response.json();
                    return {{
                        status: response.status,
                        data: data
                    }};
                }})()
            """)
            
            if response['status'] == 200:
                print(f"  ✓ Request successful!")
                return response['data']
            else:
                print(f"  ✗ Request failed with status: {response['status']}")
                return None
                
        except Exception as e:
            print(f"✗ Error getting followers: {e}")
            return None
    
    def display_followers(self, data: Dict[str, Any], page_number: int = 1):
        """Display followers from response"""
        if not data or 'users' not in data:
            print("No followers data to display")
            return
        
        users = data['users']
        print(f"\n{'='*50}")
        print(f"FOLLOWERS - PAGE {page_number}")
        print(f"{'='*50}")
        print(f"Found {len(users)} followers")
        
        for i, user in enumerate(users[:10], 1):  # Show first 10
            print(f"\n{i}. @{user.get('username', 'unknown')}")
            print(f"   Name: {user.get('full_name', 'N/A')}")
            print(f"   ID: {user.get('pk', 'N/A')}")
            print(f"   Verified: {user.get('is_verified', False)}")
            print(f"   Private: {user.get('is_private', False)}")
            
            # Friendship status
            status = user.get('friendship_status', {})
            if status.get('following'):
                print(f"   → You follow them")
            if status.get('followed_by'):
                print(f"   → They follow you")
        
        print(f"\n{'='*50}")
        print(f"Next page available: {'Yes' if data.get('next_max_id') else 'No'}")
        if data.get('next_max_id'):
            print(f"Next max ID: {str(data['next_max_id'])[:50]}...")
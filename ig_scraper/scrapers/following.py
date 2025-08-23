"""Following scraper for Instagram with session tracking"""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from ..api import Endpoints, GraphQLClient
from ..config import ConfigManager
from ..database import DatabaseManager


class FollowingScraper:
    """Scrape following list from Instagram with session tracking"""
    
    def __init__(self, page, session_manager, username: str):
        self.page = page
        self.session_manager = session_manager
        self.username = username
        
        # Database connection
        self.db = DatabaseManager()
        self.profile = self.db.get_profile_by_username(username)
        if not self.profile:
            self.profile_id = self.db.get_or_create_profile(username)
        else:
            self.profile_id = self.profile['id']
        
        # Track scraping session
        self.scraping_session_id = None
        
        # Load configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config(username)
        
        # Get specific settings
        self.max_count = self.config['scraping']['following']['max_count']
        self.default_count = self.config['scraping']['following']['default_count']
        self.pagination_delay = self.config['scraping']['following']['pagination_delay']
        self.save_responses = self.config['scraping']['following'].get('save_responses', False)
        self.response_dir = self.config['scraping']['following'].get('response_dir', 'api_responses/following')
        
        # Create response directory if saving is enabled
        if self.save_responses:
            self.response_path = Path(self.response_dir) / username
            self.response_path.mkdir(parents=True, exist_ok=True)
            print(f"[DEBUG] Response saving enabled. Directory: {self.response_path}")
        
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
    
    def save_response(self, data: Dict[str, Any], count: int, max_id: Optional[str] = None):
        """Save API response to file"""
        if not self.save_responses or not data:
            return
        
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Include pagination info in filename
            if max_id:
                filename = f"following_{timestamp}_count{count}_maxid{max_id[:10]}.json"
            else:
                filename = f"following_{timestamp}_count{count}_initial.json"
            
            filepath = self.response_path / filename
            
            # Add metadata to the saved data
            save_data = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "username": self.username,
                    "count_requested": count,
                    "max_id": max_id,
                    "users_returned": len(data.get('users', [])),
                    "has_next": data.get('next_max_id') is not None,
                    "big_list": data.get('big_list', False)
                },
                "response": data
            }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print(f"[DEBUG] Response saved to: {filepath}")
            print(f"[DEBUG] File size: {filepath.stat().st_size} bytes")
            
        except Exception as e:
            print(f"[DEBUG] Error saving response: {e}")
    
    def save_error_response(self, response: Dict[str, Any], count: int, max_id: Optional[str], error_type: str):
        """Save error response to file for debugging"""
        if not self.save_responses:
            return
        
        try:
            # Generate filename with error type
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"error_{error_type}_{timestamp}_count{count}.json"
            
            # Create errors subdirectory
            error_path = self.response_path / "errors"
            error_path.mkdir(exist_ok=True)
            filepath = error_path / filename
            
            # Add metadata to the saved data
            save_data = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "username": self.username,
                    "count_requested": count,
                    "max_id": max_id,
                    "error_type": error_type,
                    "http_status": response.get('status')
                },
                "response": response
            }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            print(f"[DEBUG] Error response saved to: {filepath}")
            
        except Exception as e:
            print(f"[DEBUG] Error saving error response: {e}")
    
    def get_following_for_user(self, user_id: str, target_username: str, count: Optional[int] = None, max_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get following list for a specific user"""
        try:
            # Use config values if not specified
            if count is None:
                count = self.default_count
            
            # Ensure count doesn't exceed maximum
            if count > self.max_count:
                print(f"⚠ Count {count} exceeds maximum {self.max_count}, using maximum")
                count = self.max_count
            
            # Get csrf token from cookies
            cookies = self.page.context.cookies()
            csrf_token = None
            
            for cookie in cookies:
                if cookie['name'] == 'csrftoken':
                    csrf_token = cookie['value']
                    break
            
            # Build URL for target user
            url = Endpoints.FRIENDSHIPS_FOLLOWING.format(user_id=user_id)
            params = f"?count={count}"
            if max_id:
                params += f"&max_id={max_id}"
            
            full_url = url + params
            
            print("\n" + "="*50)
            print("FETCHING FOLLOWING LIST")
            print("="*50)
            print(f"Target: @{target_username} (ID: {user_id})")
            print(f"Count: {count}")
            if max_id:
                print(f"Max ID (pagination): {max_id}")
            
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
                "accept-language": "en-GB,en;q=0.9",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "sec-ch-prefers-color-scheme": "light",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": user_agent,
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
            
            print(f"\nResponse Status: {response['status']}")
            
            if response['status'] == 200:
                print("✓ Request successful!")
                return response['data']
            else:
                print(f"✗ Request failed with status: {response['status']}")
                return None
                
        except Exception as e:
            print(f"✗ Error getting following: {e}")
            return None
    
    def get_following(self, count: Optional[int] = None, max_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get following list"""
        try:
            # Use config values if not specified
            if count is None:
                count = self.default_count
            
            # Ensure count doesn't exceed maximum
            if count > self.max_count:
                print(f"⚠ Count {count} exceeds maximum {self.max_count}, using maximum")
                count = self.max_count
            
            # Get user ID from cookies
            cookies = self.page.context.cookies()
            user_id = None
            csrf_token = None
            
            for cookie in cookies:
                if cookie['name'] == 'ds_user_id':
                    user_id = cookie['value']
                elif cookie['name'] == 'csrftoken':
                    csrf_token = cookie['value']
            
            if not user_id:
                print("✗ No user ID found")
                return None
            
            # Build URL
            url = Endpoints.FRIENDSHIPS_FOLLOWING.format(user_id=user_id)
            params = f"?count={count}"
            if max_id:
                params += f"&max_id={max_id}"
            
            full_url = url + params
            
            print("\n" + "="*50)
            print("FETCHING FOLLOWING LIST")
            print("="*50)
            print(f"URL: {full_url}")
            print(f"User ID: {user_id}")
            print(f"Count: {count}")
            if max_id:
                print(f"Max ID (pagination): {max_id}")
            
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
                "accept-language": "en-GB,en;q=0.9",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "sec-ch-prefers-color-scheme": "light",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": user_agent,
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
            
            print(f"\n[DEBUG] === FOLLOWING API RESPONSE ===")
            print(f"[DEBUG] HTTP Status: {response['status']}")
            print(f"[DEBUG] Response has 'data': {'data' in response}")
            
            if response['status'] == 200:
                print("✓ Request successful (HTTP 200)")
                data = response['data']
                
                # Enhanced debug logging
                print(f"\n[DEBUG] Response structure analysis:")
                print(f"[DEBUG]   - Type: {type(data)}")
                print(f"[DEBUG]   - Keys: {list(data.keys())}")
                print(f"[DEBUG]   - Has 'users' key: {'users' in data}")
                
                if 'users' in data:
                    users = data['users']
                    print(f"[DEBUG]   - Users type: {type(users)}")
                    print(f"[DEBUG]   - Users count: {len(users)}")
                    if len(users) > 0:
                        print(f"[DEBUG]   - First user keys: {list(users[0].keys())[:5]}...")
                        print(f"[DEBUG]   - First username: @{users[0].get('username', 'N/A')}")
                else:
                    print(f"[DEBUG]   - ⚠ NO 'users' KEY IN RESPONSE")
                
                print(f"[DEBUG]   - Has 'big_list': {'big_list' in data}")
                print(f"[DEBUG]   - big_list value: {data.get('big_list', 'N/A')}")
                print(f"[DEBUG]   - Has 'next_max_id': {'next_max_id' in data}")
                print(f"[DEBUG]   - next_max_id value: {data.get('next_max_id', 'N/A')}")
                print(f"[DEBUG]   - Status field: {data.get('status', 'not provided')}")
                print(f"[DEBUG]   - Count field: {data.get('count', 'not provided')}")
                print(f"[DEBUG]   - Page size: {data.get('page_size', 'not provided')}")
                
                # Check for unusual conditions
                if 'users' in data and len(data['users']) == 0:
                    print("\n[DEBUG] ⚠ EMPTY USERS LIST RETURNED")
                    print(f"[DEBUG] This could mean:")
                    print(f"[DEBUG]   1. End of following list reached")
                    print(f"[DEBUG]   2. Rate limiting in effect")
                    print(f"[DEBUG]   3. Pagination issue")
                    print(f"[DEBUG] Full response keys: {list(data.keys())}")
                    print(f"[DEBUG] Response sample (first 200 chars): {str(data)[:200]}")
                
                # Check for rate limiting indicators
                if data.get('status') == 'fail':
                    print(f"\n[DEBUG] ⚠ API returned 'fail' status")
                    print(f"[DEBUG] Message: {data.get('message', 'No message')}")
                
                # Save response if enabled
                if self.save_responses:
                    print(f"\n[DEBUG] Saving response (save_responses={self.save_responses})")
                    self.save_response(data, count, max_id)
                
                return data
            elif response['status'] == 429:
                print(f"✗ RATE LIMITED (HTTP 429)")
                print(f"[DEBUG] Too many requests - need to wait")
                if 'data' in response:
                    print(f"[DEBUG] Rate limit response: {response.get('data', {})}")
                    # Save error response if enabled
                    if self.save_responses and response.get('data'):
                        self.save_error_response(response, count, max_id, "rate_limited")
                return None
            elif response['status'] == 401:
                print(f"✗ UNAUTHORIZED (HTTP 401)")
                print(f"[DEBUG] Session may have expired")
                # Save error response if enabled
                if self.save_responses and response.get('data'):
                    self.save_error_response(response, count, max_id, "unauthorized")
                return None
            else:
                print(f"✗ Request failed with status: {response['status']}")
                if 'data' in response:
                    print(f"[DEBUG] Error response: {response.get('data', {})}")
                    print(f"[DEBUG] Error sample (first 300 chars): {str(response.get('data', ''))[:300]}")
                    # Save error response if enabled
                    if self.save_responses:
                        self.save_error_response(response, count, max_id, f"error_{response['status']}")
                return None
                
        except Exception as e:
            print(f"✗ Error fetching following: {e}")
            return None
    
    def display_following(self, data: Dict[str, Any]):
        """Display following list in console"""
        if not data:
            print("No data to display")
            return
        
        print("\n" + "="*50)
        print("FOLLOWING LIST")
        print("="*50)
        
        users = data.get('users', [])
        print(f"Total users in this batch: {len(users)}")
        
        if data.get('big_list'):
            print(f"Has more pages: Yes")
        if data.get('next_max_id'):
            print(f"Next pagination ID: {data['next_max_id']}")
        
        print(f"Page size: {data.get('page_size', 'unknown')}")
        print(f"Status: {data.get('status', 'unknown')}")
        
        print("\n" + "-"*50)
        print("USERS:")
        print("-"*50)
        
        for i, user in enumerate(users, 1):
            print(f"\n{i}. @{user.get('username', 'unknown')}")
            print(f"   Name: {user.get('full_name', 'N/A')}")
            print(f"   ID: {user.get('pk', 'N/A')}")
            print(f"   Private: {user.get('is_private', False)}")
            print(f"   Verified: {user.get('is_verified', False)}")
            if user.get('profile_pic_url'):
                print(f"   Has profile pic: Yes")
        
        print("\n" + "="*50)
        
        # Also save full response for debugging
        print("\nFull response saved to console (first 1000 chars):")
        print(json.dumps(data, indent=2)[:1000] + "...")
    
    def create_scraping_session(self, target_username: str) -> int:
        """Create a new following scraping session in database"""
        try:
            # Get target profile ID directly
            target_profile_id = self.db.get_or_create_profile(target_username)
            
            cursor = self.db.connection.cursor()
            
            # Create new session (trigger will auto-increment session_number)
            cursor.execute("""
                INSERT INTO following_scraping_sessions 
                (profile_id, target_profile_id, started_at) 
                VALUES (%s, %s, NOW())
            """, (self.profile_id, target_profile_id))
            
            self.db.connection.commit()
            session_id = cursor.lastrowid
            
            # If lastrowid is 0, try to get the ID another way
            if not session_id:
                cursor.execute("""
                    SELECT id FROM following_scraping_sessions 
                    WHERE profile_id = %s AND target_profile_id = %s
                    ORDER BY id DESC LIMIT 1
                """, (self.profile_id, target_profile_id))
                result = cursor.fetchone()
                if result:
                    session_id = result['id'] if isinstance(result, dict) else result[0]
            
            if not session_id:
                print("✗ Failed to get session ID after insert")
                return None
            
            # Get the session number that was assigned
            cursor.execute("""
                SELECT session_number FROM following_scraping_sessions 
                WHERE id = %s
            """, (session_id,))
            result = cursor.fetchone()
            session_number = result['session_number'] if isinstance(result, dict) else result[0]
            
            print(f"\n✓ Created following scraping session #{session_number}")
            print(f"  Session ID: {session_id}")
            print(f"  Profile: @{self.username}")
            print(f"  Target: @{target_username}")
            
            return session_id
            
        except Exception as e:
            print(f"✗ Error creating scraping session: {e}")
            import traceback
            traceback.print_exc()
            self.db.connection.rollback()
            return None
    
    def save_following(self, session_id: int, users: List[Dict[str, Any]], page_number: int = 1) -> int:
        """Save following users to database"""
        if not users or not session_id:
            return 0
        
        try:
            cursor = self.db.connection.cursor()
            saved_count = 0
            duplicate_count = 0
            
            for position, user in enumerate(users, 1):
                # Get or create profile for this following user
                following_username = user.get('username', '')
                if not following_username:
                    continue
                
                # get_or_create_profile returns the ID directly
                following_profile_id = self.db.get_or_create_profile(following_username)
                
                try:
                    # Use INSERT IGNORE to handle duplicates gracefully
                    cursor.execute("""
                        INSERT IGNORE INTO scraped_following 
                        (session_id, following_profile_id, following_username, 
                         following_user_id, following_full_name, is_verified, 
                         is_private, profile_pic_url, position_in_list, 
                         page_number, raw_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        session_id,
                        following_profile_id,
                        following_username,
                        str(user.get('pk', '')),
                        user.get('full_name', ''),
                        bool(user.get('is_verified', False)),
                        bool(user.get('is_private', False)),
                        user.get('profile_pic_url', ''),
                        position + ((page_number - 1) * len(users)),
                        page_number,
                        json.dumps(user)
                    ))
                    
                    if cursor.rowcount > 0:
                        saved_count += 1
                    else:
                        duplicate_count += 1
                    
                except Exception as e:
                    print(f"⚠ Error saving @{following_username}: {e}")
                    continue
            
            self.db.connection.commit()
            
            # Update session total
            cursor.execute("""
                UPDATE following_scraping_sessions 
                SET total_following = (
                    SELECT COUNT(DISTINCT following_username) 
                    FROM scraped_following 
                    WHERE session_id = %s
                )
                WHERE id = %s
            """, (session_id, session_id))
            self.db.connection.commit()
            
            if duplicate_count > 0:
                print(f"  → Saved {saved_count} new, skipped {duplicate_count} duplicates")
            else:
                print(f"  → Saved {saved_count} following users")
            
            return saved_count
            
        except Exception as e:
            print(f"✗ Error saving following: {e}")
            self.db.connection.rollback()
            return 0
    
    def close_scraping_session(self, session_id: int):
        """Close the scraping session"""
        if not session_id:
            return
        
        try:
            cursor = self.db.connection.cursor()
            
            # Update session end time
            cursor.execute("""
                UPDATE following_scraping_sessions 
                SET ended_at = NOW() 
                WHERE id = %s
            """, (session_id,))
            
            # Get final stats
            cursor.execute("""
                SELECT session_number, total_following,
                       TIMESTAMPDIFF(SECOND, started_at, NOW()) as duration_seconds
                FROM following_scraping_sessions 
                WHERE id = %s
            """, (session_id,))
            
            stats = cursor.fetchone()
            self.db.connection.commit()
            
            if stats:
                # Handle both dict and tuple cursor results
                if isinstance(stats, dict):
                    session_num = stats['session_number']
                    total = stats['total_following']
                    duration = stats['duration_seconds']
                else:
                    session_num = stats[0]
                    total = stats[1]
                    duration = stats[2]
                
                minutes = duration // 60 if duration else 0
                seconds = duration % 60 if duration else 0
                
                print(f"\n✓ Session #{session_num} completed")
                print(f"  Total following scraped: {total}")
                print(f"  Duration: {minutes}m {seconds}s")
            
        except Exception as e:
            print(f"✗ Error closing session: {e}")
            import traceback
            traceback.print_exc()
            self.db.connection.rollback()
"""Explore search scraper for Instagram"""

import json
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from ..api import Endpoints, GraphQLClient
from ..config import ConfigManager
from ..database import DatabaseManager


class ExploreScraper:
    """Scrape explore/search results from Instagram"""
    
    def __init__(self, page, session_manager, username: str):
        self.page = page
        self.session_manager = session_manager
        self.username = username
        self.rank_token = str(uuid.uuid4())  # Generate unique rank token for session
        self.search_session_id = str(uuid.uuid4())  # Generate search session ID
        
        # Database connection
        self.db = DatabaseManager()
        self.profile = self.db.get_profile_by_username(username)
        if not self.profile:
            self.profile = self.db.get_or_create_profile(username)
        self.profile_id = self.profile['id']
        
        # Track search session in database
        self.db_search_session_id = None
        self.current_page = 0
        
        # Load configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config(username)
        
        # Get specific settings
        explore_config = self.config['scraping']['explore']
        self.default_query = explore_config['default_query']
        self.save_responses = explore_config['save_responses']
        self.response_dir = explore_config['response_dir']
        self.pagination_delay = explore_config['pagination_delay']
        
        # Create directory for saving data if enabled
        if self.save_responses:
            self.data_dir = Path(self.response_dir) / "explore" / datetime.now().strftime("%Y%m%d_%H%M%S")
            self.data_dir.mkdir(parents=True, exist_ok=True)
        
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
    
    def create_search_session(self, query: str) -> int:
        """Create a new search session in database"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO explore_search_sessions 
                    (profile_id, search_query, search_type, total_pages, total_posts)
                    VALUES (%s, %s, %s, 0, 0)
                """, (self.profile_id, query, 'search'))
                self.db_search_session_id = cursor.lastrowid
                return self.db_search_session_id
        except Exception as e:
            print(f"Error creating search session: {e}")
            return None
    
    def save_api_request_response(self, endpoint: str, url: str, params: Dict, 
                                  response_data: Dict, page_number: int) -> int:
        """Save API request and response to database, return request ID"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO api_requests 
                    (profile_id, search_session_id, request_type, page_number, endpoint, 
                     method, params, response_status, response_body, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    self.profile_id,
                    self.db_search_session_id,
                    'explore_search',
                    page_number,
                    url,
                    'GET',
                    json.dumps(params),
                    200 if response_data else 0,
                    json.dumps(response_data) if response_data else None
                ))
                return cursor.lastrowid
        except Exception as e:
            print(f"Error saving API request: {e}")
            return None
    
    def close_search_session(self):
        """Close the current search session"""
        if self.db_search_session_id:
            try:
                with self.db.get_cursor() as cursor:
                    cursor.execute("""
                        UPDATE explore_search_sessions 
                        SET ended_at = NOW()
                        WHERE id = %s
                    """, (self.db_search_session_id,))
                    print(f"  → Search session #{self.db_search_session_id} closed")
            except Exception as e:
                print(f"Error closing search session: {e}")
    
    def save_explore_posts(self, api_request_id: int, posts: List[Dict]) -> int:
        """Save posts found in explore to database"""
        saved_count = 0
        try:
            with self.db.get_cursor() as cursor:
                for position, post in enumerate(posts):
                    media = post.get('media', post)
                    media_id = media.get('id') or media.get('pk')
                    media_code = media.get('code')
                    owner = media.get('owner', {})
                    
                    if not media_id:
                        continue
                    
                    cursor.execute("""
                        INSERT INTO explore_posts 
                        (api_request_id, profile_id, media_id, media_code, media_type,
                         owner_id, owner_username, owner_full_name, caption,
                         like_count, comment_count, has_liked, is_verified,
                         position_in_response, raw_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        like_count = VALUES(like_count),
                        comment_count = VALUES(comment_count)
                    """, (
                        api_request_id,
                        self.profile_id,
                        str(media_id),
                        media_code,
                        media.get('media_type'),
                        owner.get('id') or owner.get('pk'),
                        owner.get('username'),
                        owner.get('full_name'),
                        media.get('caption', {}).get('text') if isinstance(media.get('caption'), dict) else None,
                        media.get('like_count', 0),
                        media.get('comment_count', 0),
                        media.get('has_liked', False),
                        owner.get('is_verified', False),
                        position,
                        json.dumps(media)
                    ))
                    saved_count += 1
        except Exception as e:
            print(f"Error saving posts: {e}")
        
        return saved_count
    
    def search_explore(self, query: str, next_max_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Search in explore with a query"""
        try:
            # Create search session on first request
            if not next_max_id and not self.db_search_session_id:
                self.db_search_session_id = self.create_search_session(query)
                self.current_page = 1
            elif next_max_id:
                self.current_page += 1
            
            # Get csrf token from cookies
            cookies = self.page.context.cookies()
            csrf_token = None
            
            for cookie in cookies:
                if cookie['name'] == 'csrftoken':
                    csrf_token = cookie['value']
                    break
            
            # Build URL with parameters
            base_url = Endpoints.EXPLORE_SEARCH
            params = [
                f"enable_metadata=true",
                f"query={query}"
            ]
            
            if next_max_id:
                # For pagination: empty search_session_id, include next_max_id and rank_token
                params.append(f"search_session_id=")
                params.append(f"next_max_id={next_max_id}")
                params.append(f"rank_token={self.rank_token}")
            else:
                # For initial request: include search_session_id and rank_token
                params.append(f"search_session_id={self.search_session_id}")
                params.append(f"rank_token={self.rank_token}")
            
            full_url = base_url + "?" + "&".join(params)
            
            print("\n" + "="*50)
            print("EXPLORE SEARCH REQUEST")
            print("="*50)
            print(f"Query: '{query}'")
            if next_max_id:
                print(f"Type: Pagination request")
                print(f"Search session ID: (empty)")
                print(f"Next max ID: {next_max_id[:50]}...")
            else:
                print(f"Type: Initial request")
                print(f"Search session ID: {self.search_session_id}")
            print(f"Rank token: {self.rank_token}")
            
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
            
            # Get x-ig-www-claim from cookies if available
            x_ig_www_claim = None
            for cookie in cookies:
                if cookie['name'] == 'ig_www_claim':
                    x_ig_www_claim = cookie['value']
                    break
            
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
            
            # Add x-ig-www-claim if available
            if x_ig_www_claim:
                headers["x-ig-www-claim"] = x_ig_www_claim
            
            # Add x-web-session-id (generate a simple one)
            headers["x-web-session-id"] = f"{uuid.uuid4().hex[:6]}:{uuid.uuid4().hex[:6]}:{uuid.uuid4().hex[:6]}"
            
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
                
                # Save to database
                if self.db_search_session_id:
                    # Build params dict for database
                    params_dict = {
                        'enable_metadata': True,
                        'query': query,
                        'search_session_id': '' if next_max_id else self.search_session_id,
                        'rank_token': self.rank_token
                    }
                    if next_max_id:
                        params_dict['next_max_id'] = next_max_id
                    
                    # Save API request and response
                    api_request_id = self.save_api_request_response(
                        endpoint='explore/search',
                        url=full_url,
                        params=params_dict,
                        response_data=response['data'],
                        page_number=self.current_page
                    )
                    
                    if api_request_id:
                        # Extract and save posts from response
                        posts = []
                        
                        # Extract posts from media_grid sections
                        if 'media_grid' in response['data'] and 'sections' in response['data']['media_grid']:
                            for section in response['data']['media_grid']['sections']:
                                if 'layout_content' in section and 'medias' in section['layout_content']:
                                    for media_item in section['layout_content']['medias']:
                                        if 'media' in media_item:
                                            posts.append(media_item['media'])
                        
                        if posts:
                            saved_count = self.save_explore_posts(api_request_id, posts)
                            print(f"  → Saved {saved_count} posts to database")
                        
                        # Update session totals
                        try:
                            with self.db.get_cursor() as cursor:
                                cursor.execute("""
                                    UPDATE explore_search_sessions 
                                    SET total_pages = %s, total_posts = total_posts + %s
                                    WHERE id = %s
                                """, (self.current_page, len(posts), self.db_search_session_id))
                        except Exception as e:
                            print(f"Error updating session totals: {e}")
                
                # Don't save to files anymore - handled by database
                # self.save_request_response(query, full_url, headers, response['data'], next_max_id)
                
                return response['data']
            else:
                print(f"✗ Request failed with status: {response['status']}")
                return None
                
        except Exception as e:
            print(f"✗ Error in explore search: {e}")
            return None
    
    def save_request_response(self, query: str, url: str, headers: Dict[str, Any], 
                             response_data: Dict[str, Any], next_max_id: Optional[str] = None):
        """Save request and response to files"""
        try:
            # Generate filename based on query and pagination
            safe_query = query.replace(' ', '_').replace('/', '_')[:20]
            timestamp = datetime.now().strftime("%H%M%S")
            
            # Better page naming: first page or continuation with shortened ID
            if next_max_id:
                # For pagination pages, use a shortened version of the max_id
                suffix = f"_page_{next_max_id[:8]}"
            else:
                suffix = "_page_01"
            
            base_name = f"{safe_query}_{timestamp}{suffix}"
            
            # Save request info
            request_file = self.data_dir / f"req_{base_name}.json"
            request_data = {
                "timestamp": datetime.now().isoformat(),
                "url": url,
                "method": "GET",
                "headers": headers,
                "query": query,
                "rank_token": self.rank_token,
                "next_max_id": next_max_id
            }
            
            with open(request_file, 'w', encoding='utf-8') as f:
                json.dump(request_data, f, indent=2, ensure_ascii=False)
            
            # File saving disabled - now using database
            # print(f"  → Request saved: {request_file.name}")
            
            # Save response
            response_file = self.data_dir / f"res_{base_name}.json"
            with open(response_file, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
            
            # File saving disabled - now using database
            # print(f"  → Response saved: {response_file.name}")
            
            # Save summary
            summary_file = self.data_dir / f"summary_{base_name}.txt"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"Explore Search Summary\n")
                f.write(f"=" * 50 + "\n")
                f.write(f"Query: {query}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Rank Token: {self.rank_token}\n")
                if next_max_id:
                    f.write(f"Page Type: Pagination\n")
                    f.write(f"Search Session ID: (empty)\n")
                    f.write(f"Previous max_id: {next_max_id}\n\n")
                else:
                    f.write(f"Page Type: Initial\n")
                    f.write(f"Search Session ID: {self.search_session_id}\n\n")
                
                # Results summary
                if 'list' in response_data:
                    f.write(f"Search Results: {len(response_data['list'])} items\n")
                    for item in response_data['list'][:10]:
                        if 'user' in item:
                            u = item['user']
                            f.write(f"  - USER: @{u.get('username')} ({u.get('full_name')})\n")
                
                # Media grid summary  
                if 'media_grid' in response_data and 'sections' in response_data.get('media_grid', {}):
                    sections = response_data['media_grid']['sections']
                    total_posts = sum(len(s.get('layout_content', {}).get('medias', [])) for s in sections)
                    f.write(f"\nMedia Grid: {total_posts} posts in {len(sections)} sections\n")
                
                f.write(f"\nHas more results: {'Yes' if response_data.get('next_max_id') else 'No'}\n")
                if response_data.get('has_more') is not None:
                    f.write(f"Has more (explicit): {response_data['has_more']}\n")
                if response_data.get('auto_load_more_enabled') is not None:
                    f.write(f"Auto load more enabled: {response_data['auto_load_more_enabled']}\n")
            
            # File saving disabled - now using database
            # print(f"  → Summary saved: {summary_file.name}")
            # print(f"\n  📁 All data saved to: {self.data_dir}")
            
        except Exception as e:
            print(f"  ⚠ Error saving data: {e}")
    
    def display_results(self, data: Dict[str, Any]):
        """Display explore search results"""
        if not data:
            print("No data to display")
            return
        
        print("\n" + "="*50)
        print("EXPLORE SEARCH RESULTS ANALYSIS")
        print("="*50)
        
        # 1. Search results (users/hashtags/places)
        if 'list' in data:
            results_list = data['list']
            print(f"\n1. SEARCH RESULTS: {len(results_list)} items")
            print("-"*50)
            
            for i, item in enumerate(results_list[:10], 1):  # Show first 10
                if 'user' in item:
                    user = item['user']
                    print(f"{i}. USER: @{user.get('username', 'unknown')}")
                    print(f"   Name: {user.get('full_name', 'N/A')}")
                    print(f"   Verified: {user.get('is_verified', False)}")
                    print(f"   Private: {user.get('is_private', False)}")
                    print(f"   Has story: {user.get('latest_reel_media', 0) > 0}")
                elif 'hashtag' in item:
                    hashtag = item['hashtag']
                    print(f"{i}. HASHTAG: #{hashtag.get('name', 'unknown')}")
                    print(f"   Media count: {hashtag.get('media_count', 0)}")
                elif 'place' in item:
                    place = item['place']
                    print(f"{i}. PLACE: {place.get('title', 'unknown')}")
                    print(f"   Location: {place.get('location', {}).get('short_name', 'N/A')}")
        
        # 2. Media Grid Analysis
        if 'media_grid' in data and data['media_grid']:
            print(f"\n2. MEDIA GRID (Related Posts)")
            print("-"*50)
            
            if 'sections' in data['media_grid']:
                sections = data['media_grid']['sections']
                print(f"Total sections: {len(sections)}")
                
                total_posts = 0
                sample_posts = []
                
                for section_idx, section in enumerate(sections):
                    if 'layout_content' in section and 'medias' in section['layout_content']:
                        medias = section['layout_content']['medias']
                        total_posts += len(medias)
                        
                        # Collect sample posts from first section
                        if section_idx == 0:
                            for media_item in medias[:3]:  # First 3 posts
                                if 'media' in media_item:
                                    sample_posts.append(media_item['media'])
                
                print(f"Total posts found: {total_posts}")
                
                # Display sample posts
                if sample_posts:
                    print(f"\nSAMPLE POSTS:")
                    for i, post in enumerate(sample_posts, 1):
                        print(f"\n  Post {i}:")
                        print(f"    User: @{post.get('user', {}).get('username', 'unknown')}")
                        
                        # Handle caption safely
                        caption_text = ""
                        if 'caption' in post and post['caption']:
                            if isinstance(post['caption'], dict):
                                caption_text = post['caption'].get('text', '')
                            else:
                                caption_text = str(post['caption'])
                        
                        # Clean and truncate caption
                        caption_preview = caption_text.replace('\n', ' ')[:80]
                        print(f"    Caption: {caption_preview}...")
                        
                        print(f"    Likes: {post.get('like_count', 0)}")
                        print(f"    Comments: {post.get('comment_count', 0)}")
                        print(f"    Type: {post.get('media_type', 'unknown')}")
                        print(f"    Code: {post.get('code', 'N/A')}")
        
        # 3. Pagination info
        print(f"\n3. PAGINATION")
        print("-"*50)
        
        # Check both root level and media_grid for pagination info
        media_grid = data.get('media_grid', {})
        
        # Check for next_max_id in both locations
        next_max_id = data.get('next_max_id') or media_grid.get('next_max_id')
        if next_max_id:
            print(f"Has more results: Yes")
            print(f"Next max ID: {str(next_max_id)[:50]}...")
        else:
            print(f"Has more results: No")
        
        # Check for other pagination fields
        has_more = data.get('has_more', media_grid.get('has_more'))
        if has_more is not None:
            print(f"Has more (explicit): {has_more}")
        
        auto_load = data.get('auto_load_more_enabled', media_grid.get('auto_load_more_enabled'))
        if auto_load is not None:
            print(f"Auto load more: {auto_load}")
        
        reels_max_id = data.get('reels_max_id', media_grid.get('reels_max_id'))
        if reels_max_id:
            print(f"Reels max ID: {str(reels_max_id)[:50]}...")
        
        has_more_reels = data.get('has_more_reels', media_grid.get('has_more_reels'))
        if has_more_reels is not None:
            print(f"Has more reels: {has_more_reels}")
        
        print(f"\nStatus: {data.get('status', 'unknown')}")
        print("="*50)
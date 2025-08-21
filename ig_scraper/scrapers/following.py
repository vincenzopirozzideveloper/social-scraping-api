"""Following scraper for Instagram"""

import json
from typing import Dict, Any, Optional, List
from ..api import Endpoints, GraphQLClient


class FollowingScraper:
    """Scrape following list from Instagram"""
    
    def __init__(self, page, session_manager, username: str):
        self.page = page
        self.session_manager = session_manager
        self.username = username
        
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
    
    def get_following(self, count: int = 12, max_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get following list"""
        try:
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
            url = f"https://www.instagram.com/api/v1/friendships/{user_id}/following/"
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
            
            print(f"\nResponse Status: {response['status']}")
            
            if response['status'] == 200:
                print("✓ Request successful!")
                return response['data']
            else:
                print(f"✗ Request failed with status: {response['status']}")
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
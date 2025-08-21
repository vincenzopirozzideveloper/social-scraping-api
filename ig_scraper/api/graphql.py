"""Instagram GraphQL API handler"""

import json
from typing import Dict, Any, Optional
from urllib.parse import urlencode


class GraphQLClient:
    """Handle Instagram GraphQL requests"""
    
    def __init__(self, page):
        self.page = page
        self.base_url = "https://www.instagram.com/graphql/query"
        
    def get_browser_headers(self) -> Dict[str, str]:
        """Extract headers from current browser context"""
        # Get user agent from browser
        user_agent = self.page.evaluate("navigator.userAgent")
        
        # Get csrftoken from cookies
        cookies = self.page.context.cookies()
        csrf_token = None
        for cookie in cookies:
            if cookie['name'] == 'csrftoken':
                csrf_token = cookie['value']
                break
        
        return {
            "accept": "*/*",
            "accept-language": "en-GB,en;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
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
            "x-csrftoken": csrf_token or "",
            "x-ig-app-id": "936619743392459",
        }
    
    def get_profile_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get profile information using GraphQL"""
        
        # No need to navigate again, we're already on Instagram
        # Just wait a bit to ensure page is stable
        self.page.wait_for_timeout(1000)
        
        # Prepare GraphQL request parameters
        doc_id = "23990158980626285"  # PolarisProfilePageContentQuery
        
        variables = {
            "enable_integrity_filters": True,
            "id": user_id,
            "render_surface": "PROFILE",
            "__relay_internal__pv__IGDProjectCannesEnabledGKrelayprovider": False,
            "__relay_internal__pv__PolarisCASB976ProfileEnabledrelayprovider": False
        }
        
        # Build request body
        body_params = {
            "doc_id": doc_id,
            "variables": json.dumps(variables),
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "PolarisProfilePageContentQuery",
            "server_timestamps": "true"
        }
        
        # Additional parameters from the request
        body_params.update({
            "__d": "www",
            "__user": "0",
            "__a": "1",
            "__req": "2",
            "dpr": "1",
            "__ccg": "EXCELLENT",
        })
        
        # Get headers
        headers = self.get_browser_headers()
        headers["x-fb-friendly-name"] = "PolarisProfilePageContentQuery"
        headers["x-root-field-name"] = "fetch__XDTUserDict"
        
        # Encode body
        body = urlencode(body_params)
        
        print("\n" + "="*50)
        print("SENDING GRAPHQL REQUEST")
        print("="*50)
        print(f"Doc ID: {doc_id}")
        print(f"User ID: {user_id}")
        print(f"CSRF Token: {headers.get('x-csrftoken', 'Not found')}")
        
        # Make the request using page.evaluate to use browser's fetch
        try:
            response = self.page.evaluate(f"""
                (async () => {{
                    const url = {json.dumps(self.base_url)};
                    const headers = {json.dumps(headers)};
                    const body = {json.dumps(body)};
                    
                    try {{
                        const response = await fetch(url, {{
                            method: 'POST',
                            headers: headers,
                            body: body,
                            credentials: 'include'
                        }});
                        
                        const text = await response.text();
                        let data;
                        try {{
                            data = JSON.parse(text);
                        }} catch {{
                            data = {{error: 'Could not parse response', text: text}};
                        }}
                        
                        return {{
                            status: response.status,
                            data: data
                        }};
                    }} catch (error) {{
                        return {{
                            status: 0,
                            error: error.toString()
                        }};
                    }}
                }})()
            """)
            
            print(f"Response Status: {response.get('status', 'Unknown')}")
            
            if response.get('error'):
                print(f"✗ Request error: {response['error']}")
                return None
            
            if response['status'] == 200:
                print("✓ Request successful!")
                return response['data']
            else:
                print(f"✗ Request failed with status: {response['status']}")
                if response.get('data'):
                    print(f"Response: {json.dumps(response['data'], indent=2)[:500]}")
                return None
                
        except Exception as e:
            print(f"✗ Exception during request: {e}")
            return None
    
    def extract_username(self, response_data: Dict[str, Any]) -> Optional[str]:
        """Extract username from GraphQL response"""
        try:
            username = response_data['data']['user']['username']
            return username
        except (KeyError, TypeError):
            return None
"""Base action class for Instagram automation"""

import time
import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import random
from ..config import ConfigManager
from ..config.env_config import ACTION_LOGS_DIR


@dataclass
class ActionResult:
    """Result of an action execution"""
    success: bool
    action_type: str
    target_id: str
    target_username: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class BaseAction:
    """Base class for Instagram actions"""
    
    def __init__(self, page, session_manager, username: str):
        self.page = page
        self.session_manager = session_manager
        self.username = username
        self.action_type = "base"
        
        # Create logs directory
        self.logs_dir = ACTION_LOGS_DIR / username / datetime.now().strftime("%Y%m%d")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration for rate limiting
        config_manager = ConfigManager()
        config = config_manager.load_config(username)
        rate_config = config['actions']['rate_limiting']
        
        # Rate limiting settings from configuration
        self.min_delay = rate_config['min_delay']  # Minimum seconds between actions
        self.max_delay = rate_config['max_delay']  # Maximum seconds between actions
        
        print(f"[DEBUG] BaseAction initialized with delays: {self.min_delay}s - {self.max_delay}s")
        
    def get_headers(self) -> Dict[str, str]:
        """Get headers for the request"""
        # Get CSRF token from cookies
        cookies = self.page.context.cookies()
        csrf_token = None
        x_ig_www_claim = None
        
        for cookie in cookies:
            if cookie['name'] == 'csrftoken':
                csrf_token = cookie['value']
            elif cookie['name'] == 'ig_www_claim':
                x_ig_www_claim = cookie['value']
        
        # Get saved metadata
        saved_info = self.session_manager.load_session_info(self.username)
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        app_id = "936619743392459"
        
        if saved_info and 'graphql' in saved_info:
            graphql_data = saved_info['graphql']
            if graphql_data.get('user_agent'):
                user_agent = graphql_data['user_agent']
            if graphql_data.get('app_id'):
                app_id = graphql_data['app_id']
        
        headers = {
            "accept": "*/*",
            "accept-language": "en-GB,en;q=0.9,it-IT;q=0.8,it;q=0.7,en-US;q=0.6",
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
            "x-asbd-id": "359341",
            "x-csrftoken": csrf_token,
            "x-ig-app-id": app_id,
            "x-instagram-ajax": "1026178298",
            "x-requested-with": "XMLHttpRequest"
        }
        
        if x_ig_www_claim:
            headers["x-ig-www-claim"] = x_ig_www_claim
            
        # Generate session ID
        import uuid
        headers["x-web-session-id"] = f"{uuid.uuid4().hex[:6]}:{uuid.uuid4().hex[:6]}:{uuid.uuid4().hex[:6]}"
        
        return headers
    
    def get_body_params(self, user_id: str, referrer: str = None) -> str:
        """Get body parameters for the request"""
        # Generate jazoest (seems to be a static value in examples)
        jazoest = "22826"
        
        # Default navigation chain
        nav_chain = "PolarisProfilePostsTabRoot:profilePage:1:via_cold_start,PolarisProfilePostsTabRoot:profilePage:2:unexpected"
        
        params = {
            "container_module": "profile",
            "nav_chain": nav_chain,
            "user_id": user_id,
            "jazoest": jazoest
        }
        
        # Convert to URL-encoded string
        return "&".join(f"{k}={v}" for k, v in params.items())
    
    def execute_request(self, url: str, body: str, headers: Dict[str, str]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Execute the action request"""
        try:
            print(f"\n→ Executing {self.action_type} request...")
            print(f"[DEBUG] Request URL: {url}")
            print(f"[DEBUG] Request body params: {body[:100]}...")
            
            # Use page.evaluate to make the request
            response = self.page.evaluate(f"""
                (async () => {{
                    const response = await fetch("{url}", {{
                        method: 'POST',
                        headers: {json.dumps(headers)},
                        body: "{body}",
                        credentials: 'include'
                    }});
                    
                    const data = await response.json();
                    return {{
                        status: response.status,
                        data: data
                    }};
                }})()
            """)
            
            print(f"[DEBUG] Response HTTP status: {response['status']}")
            print(f"[DEBUG] Response has data: {'data' in response}")
            
            if response['data']:
                print(f"[DEBUG] Response status field: {response['data'].get('status', 'N/A')}")
                print(f"[DEBUG] Response keys: {list(response['data'].keys())[:5]}...")
            
            # Check for rate limiting
            if response['status'] == 429:
                print(f"[DEBUG] ⚠ RATE LIMITED - HTTP 429")
                print(f"[DEBUG] Response: {response.get('data', 'No data')}")
                return False, response['data']
            
            # Check for success
            if response['status'] == 200 and response['data'].get('status') == 'ok':
                print(f"[DEBUG] ✓ Action successful")
                return True, response['data']
            else:
                print(f"[DEBUG] ✗ Action failed")
                print(f"[DEBUG] Failure reason: HTTP {response['status']}, status: {response['data'].get('status', 'unknown')}")
                if response['data'].get('message'):
                    print(f"[DEBUG] Error message: {response['data']['message']}")
                return False, response['data']
                
        except Exception as e:
            print(f"✗ Error executing request: {e}")
            print(f"[DEBUG] Exception type: {type(e).__name__}")
            print(f"[DEBUG] Exception details: {str(e)}")
            return False, None
    
    def wait_with_variance(self):
        """Wait with random variance for rate limiting"""
        delay = random.uniform(self.min_delay, self.max_delay)
        print(f"  → Waiting {delay:.1f} seconds...")
        print(f"[DEBUG] Delay range: {self.min_delay}s - {self.max_delay}s")
        print(f"[DEBUG] Actual delay: {delay:.2f}s")
        time.sleep(delay)
    
    def log_action(self, result: ActionResult):
        """Log action result to file"""
        log_file = self.logs_dir / f"{self.action_type}_log.jsonl"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result.__dict__, ensure_ascii=False) + "\n")
    
    def execute(self, target_id: str, target_username: Optional[str] = None) -> ActionResult:
        """Execute the action - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement execute()")
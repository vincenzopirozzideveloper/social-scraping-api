"""Session management for Instagram authentication"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class SessionManager:
    """Manages browser sessions and authentication state"""
    
    def __init__(self, base_dir: str = "./browser_sessions"):
        self.base_dir = Path(base_dir)
        self.profiles_dir = self.base_dir / "profiles"
        
        # Create directories if they don't exist
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
    
    def get_profile_dir(self, username: str) -> Path:
        """Get profile directory for a user"""
        profile_dir = self.profiles_dir / username
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir
    
    def get_state_path(self, username: str) -> str:
        """Get storage state file path for a user"""
        return str(self.get_profile_dir(username) / "state.json")
    
    def save_session_info(self, username: str, data: Dict[str, Any], graphql_data: Optional[Dict[str, Any]] = None):
        """Save additional session information including GraphQL metadata"""
        info_path = self.get_profile_dir(username) / "info.json"
        data['last_saved'] = datetime.now().isoformat()
        data['username'] = username
        
        # Add GraphQL data if provided
        if graphql_data:
            data['graphql'] = graphql_data
            print(f"  → Saved {len(graphql_data.get('doc_ids', {}))} GraphQL endpoints")
        
        with open(info_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Session info saved for {username}")
    
    def load_session_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Load session information if it exists"""
        info_path = self.get_profile_dir(username) / "info.json"
        
        if info_path.exists():
            with open(info_path, 'r') as f:
                return json.load(f)
        return None
    
    def has_saved_session(self, username: str) -> bool:
        """Check if a saved session exists for the user"""
        state_file = Path(self.get_state_path(username))
        return state_file.exists()
    
    def create_browser_context(self, browser, username: str):
        """Create a browser context with storage state persistence"""
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'en-US',
            # Instagram-friendly user agent
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # If we have a saved state, use it
        state_path = self.get_state_path(username)
        if Path(state_path).exists():
            print(f"✓ Loading saved session for {username}")
            context_options['storage_state'] = state_path
        else:
            print(f"→ Creating new session for {username}")
        
        # Use normal context with storage_state (more reliable for response interception)
        context = browser.new_context(**context_options)
        
        return context
    
    def save_context_state(self, context, username: str, graphql_data: Optional[Dict[str, Any]] = None):
        """Save the current context state with optional GraphQL data"""
        state_path = self.get_state_path(username)
        context.storage_state(path=state_path)
        print(f"✓ Session state saved for {username}")
        
        # Also save session info with GraphQL data
        self.save_session_info(username, {
            'state_file': state_path
        }, graphql_data)
    
    def list_profiles(self) -> list[str]:
        """List all saved profiles"""
        profiles = []
        if self.profiles_dir.exists():
            for profile_dir in self.profiles_dir.iterdir():
                if profile_dir.is_dir():
                    info_path = profile_dir / "info.json"
                    if info_path.exists():
                        profiles.append(profile_dir.name)
        return sorted(profiles)
    
    def get_profile_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get basic info about a profile"""
        info = self.load_session_info(username)
        if info:
            return {
                'username': username,
                'last_saved': info.get('last_saved', 'Unknown'),
                'has_graphql': 'graphql' in info
            }
        return None
    
    def clear_session(self, username: str):
        """Clear saved session for a user"""
        import shutil
        
        # Remove entire profile directory
        profile_dir = self.get_profile_dir(username)
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
        
        print(f"✓ Session cleared for {username}")
    
    def clear_all_sessions(self):
        """Clear all saved sessions"""
        import shutil
        
        if self.profiles_dir.exists():
            shutil.rmtree(self.profiles_dir)
            self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        print("✓ All sessions cleared")
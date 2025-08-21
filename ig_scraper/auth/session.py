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
        self.states_dir = self.base_dir / "states"
        
        # Create directories if they don't exist
        self.states_dir.mkdir(parents=True, exist_ok=True)
    
    def get_state_path(self, username: str) -> str:
        """Get storage state file path for a user"""
        return str(self.states_dir / f"{username}_state.json")
    
    def save_session_info(self, username: str, data: Dict[str, Any]):
        """Save additional session information"""
        info_path = self.base_dir / f"{username}_info.json"
        data['last_saved'] = datetime.now().isoformat()
        data['username'] = username
        
        with open(info_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Session info saved for {username}")
    
    def load_session_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Load session information if it exists"""
        info_path = self.base_dir / f"{username}_info.json"
        
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
    
    def save_context_state(self, context, username: str):
        """Save the current context state"""
        state_path = self.get_state_path(username)
        context.storage_state(path=state_path)
        print(f"✓ Session state saved for {username}")
        
        # Also save session info
        self.save_session_info(username, {
            'state_file': state_path
        })
    
    def clear_session(self, username: str):
        """Clear saved session for a user"""
        
        # Remove state file
        state_path = Path(self.get_state_path(username))
        if state_path.exists():
            state_path.unlink()
        
        # Remove info file
        info_path = self.base_dir / f"{username}_info.json"
        if info_path.exists():
            info_path.unlink()
        
        print(f"✓ Session cleared for {username}")
"""Browser manager for handling multiple operations safely"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Optional, Any
from playwright.sync_api import Browser, BrowserContext, Page
import threading
from ig_scraper.config.env_config import BROWSER_SESSIONS_DIR


class ProfileLockError(Exception):
    """Raised when a profile is already in use"""
    pass


class BrowserManager:
    """Manages browser instances per profile to avoid conflicts"""
    
    _instances: Dict[str, Dict[str, Any]] = {}
    _locks: Dict[str, threading.Lock] = {}
    _lock_files: Dict[str, Path] = {}
    
    @classmethod
    def is_profile_locked(cls, username: str) -> bool:
        """Check if a profile is currently in use"""
        lock_file = BROWSER_SESSIONS_DIR / username / ".lock"
        
        if lock_file.exists():
            # Check if lock is stale (older than 1 hour)
            if time.time() - lock_file.stat().st_mtime > 3600:
                print(f"[DEBUG] Removing stale lock for {username}")
                lock_file.unlink()
                return False
            return True
        return False
    
    @classmethod
    def acquire_lock(cls, username: str) -> bool:
        """Acquire lock for a profile"""
        if cls.is_profile_locked(username):
            return False
        
        # Create lock file
        lock_file = BROWSER_SESSIONS_DIR / username / ".lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        lock_data = {
            "timestamp": time.time(),
            "pid": os.getpid()
        }
        
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f)
        
        cls._lock_files[username] = lock_file
        return True
    
    @classmethod
    def release_lock(cls, username: str):
        """Release lock for a profile"""
        if username in cls._lock_files:
            lock_file = cls._lock_files[username]
            if lock_file.exists():
                lock_file.unlink()
            del cls._lock_files[username]
    
    @classmethod
    def get_or_create_browser(cls, username: str, session_manager, playwright) -> Dict[str, Any]:
        """Get existing browser or create new one for profile"""
        
        # Check if already have instance in this process
        if username in cls._instances:
            instance = cls._instances[username]
            # Check if browser is still connected
            try:
                instance['browser'].contexts
                print(f"[DEBUG] Reusing existing browser for @{username}")
                return instance
            except:
                print(f"[DEBUG] Browser disconnected for @{username}, creating new one")
                del cls._instances[username]
                cls.release_lock(username)
        
        # Check if profile is locked by another process
        if cls.is_profile_locked(username):
            raise ProfileLockError(f"Profile @{username} is already in use by another process")
        
        # Acquire lock for this profile
        if not cls.acquire_lock(username):
            raise ProfileLockError(f"Could not acquire lock for profile @{username}")
        
        # Create new browser instance
        print(f"[DEBUG] Creating new browser for @{username}")
        try:
            # Import from config for consistent settings
            from ..config.env_config import IS_DOCKER, HEADLESS_MODE
            
            launch_args = {
                'headless': HEADLESS_MODE,
            }
            
            if IS_DOCKER:
                # Additional args for Docker environment
                launch_args['args'] = [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            
            browser = playwright.chromium.launch(**launch_args)
            context = session_manager.create_browser_context(browser, username)
            
            instance = {
                'browser': browser,
                'context': context,
                'pages': [],
                'username': username,
                'session_manager': session_manager,
                'playwright': playwright
            }
            
            cls._instances[username] = instance
            return instance
        except Exception as e:
            # Release lock if browser creation fails
            cls.release_lock(username)
            raise e
    
    @classmethod
    def get_new_page(cls, username: str, session_manager, playwright) -> Page:
        """Get a new page (tab) for the profile"""
        instance = cls.get_or_create_browser(username, session_manager, playwright)
        
        # Clean up closed pages
        instance['pages'] = [p for p in instance['pages'] if not p.is_closed()]
        
        # Create new page
        page = instance['context'].new_page()
        instance['pages'].append(page)
        
        print(f"[DEBUG] Created new tab for @{username} (total tabs: {len(instance['pages'])})")
        return page
    
    @classmethod
    def close_page(cls, username: str, page: Page):
        """Close a specific page"""
        if username in cls._instances:
            instance = cls._instances[username]
            if page in instance['pages']:
                instance['pages'].remove(page)
                if not page.is_closed():
                    page.close()
                print(f"[DEBUG] Closed tab for @{username} (remaining: {len(instance['pages'])})")
    
    @classmethod
    def close_browser(cls, username: str):
        """Close browser for a profile"""
        if username in cls._instances:
            instance = cls._instances[username]
            
            # Close all pages
            for page in instance['pages']:
                if not page.is_closed():
                    page.close()
            
            # Close context and browser
            instance['context'].close()
            instance['browser'].close()
            
            del cls._instances[username]
            cls.release_lock(username)
            print(f"[DEBUG] Closed browser for @{username}")
    
    @classmethod
    def close_all(cls):
        """Close all browsers and release all locks"""
        usernames = list(cls._instances.keys())
        for username in usernames:
            cls.close_browser(username)
        
        # Clean up any remaining locks in memory
        for username in list(cls._lock_files.keys()):
            cls.release_lock(username)
        
        # Clean up ALL .lock files from disk (handles forced exits)
        import os
        sessions_dir = Path("browser_sessions")
        if sessions_dir.exists():
            for profile_dir in sessions_dir.iterdir():
                if profile_dir.is_dir():
                    lock_file = profile_dir / ".lock"
                    if lock_file.exists():
                        try:
                            lock_file.unlink()
                            print(f"[DEBUG] Cleaned up stale lock for @{profile_dir.name}")
                        except Exception as e:
                            print(f"[DEBUG] Could not remove lock for @{profile_dir.name}: {e}")
    
    @classmethod
    def get_active_profiles(cls) -> list:
        """Get list of profiles with active browsers"""
        active = []
        for username, instance in cls._instances.items():
            try:
                # Check if browser is still connected
                instance['browser'].contexts
                active.append({
                    'username': username,
                    'tabs': len([p for p in instance['pages'] if not p.is_closed()])
                })
            except:
                pass
        return active
    
    @classmethod
    def status(cls):
        """Print status of all browsers"""
        print("\n" + "="*50)
        print("BROWSER MANAGER STATUS")
        print("="*50)
        
        active = cls.get_active_profiles()
        if not active:
            print("No active browsers")
        else:
            for profile in active:
                print(f"@{profile['username']}: {profile['tabs']} tabs open")
        
        # Check for locked profiles
        lock_dir = BROWSER_SESSIONS_DIR
        if lock_dir.exists():
            for lock_file in lock_dir.glob("*/.lock"):
                username = lock_file.parent.name
                if username not in [p['username'] for p in active]:
                    print(f"@{username}: LOCKED (possibly stale)")
        
        print("="*50)
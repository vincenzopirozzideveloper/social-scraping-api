"""Browser manager for handling multiple operations safely"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Optional, Any
from playwright.sync_api import Browser, BrowserContext, Page
import threading
from ig_scraper.config.env_config import BROWSER_SESSIONS_DIR
from ig_scraper.database import DatabaseManager


class ProfileLockError(Exception):
    """Raised when a profile is already in use"""
    pass


class BrowserManager:
    """Manages browser instances per profile to avoid conflicts"""
    
    _instances: Dict[str, Dict[str, Any]] = {}
    _db = DatabaseManager()  # Single database instance
    
    @classmethod
    def is_profile_locked(cls, username: str) -> bool:
        """Check if a profile is currently in use (database-based)"""
        return cls._db.is_browser_locked(username)
    
    @classmethod
    def acquire_lock(cls, username: str) -> bool:
        """Acquire lock for a profile (database-based)"""
        pid = os.getpid()
        return cls._db.acquire_browser_lock(username, pid)
    
    @classmethod
    def release_lock(cls, username: str):
        """Release lock for a profile (database-based)"""
        cls._db.release_browser_lock(username)
    
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
            from ..config.env_config import HEADLESS_MODE
            
            launch_args = {
                'headless': HEADLESS_MODE,
                # Always use Docker-optimized args
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            }
            
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
            try:
                cls.close_browser(username)
            except:
                # Force close if normal close fails
                pass
        
        # Clear ALL database locks
        cleared = cls._db.clear_all_browser_locks()
        if cleared > 0:
            print(f"[DEBUG] Cleared {cleared} browser locks from database")
        
        # Force terminate any hanging browser processes in Docker
        try:
            import subprocess
            subprocess.run(['pkill', '-f', 'chrome'], capture_output=True)
            print("[DEBUG] Force killed browser processes in Docker")
        except:
            pass
    
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
        
        # Check for database locks
        locks = cls._db.get_all_browser_locks()
        if locks:
            print("\n📔 DATABASE LOCKS:")
            for lock in locks:
                username = lock['username'] if isinstance(lock, dict) else lock[1]
                lock_id = lock['id'] if isinstance(lock, dict) else lock[0]
                minutes = lock['locked_minutes_ago'] if isinstance(lock, dict) else lock[5]
                
                if username not in [p['username'] for p in active]:
                    print(f"  #{lock_id} @{username}: LOCKED {minutes}min ago (possibly stale)")
                else:
                    print(f"  #{lock_id} @{username}: ACTIVE ({minutes}min)")
        
        print("="*50)
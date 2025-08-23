"""Database-backed session management for Instagram authentication"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
from ig_scraper.database import DatabaseManager


class SessionManager:
    """Manages browser sessions and authentication state using database"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_state_path(self, username: str) -> str:
        """Get virtual state path for compatibility"""
        # Return a virtual path for compatibility with existing code
        return f"db://sessions/{username}/state.json"
    
    def save_session_info(self, username: str, data: Dict[str, Any], graphql_data: Optional[Dict[str, Any]] = None):
        """Save session information to database"""
        try:
            # Get or create profile
            profile = self.db.get_or_create_profile(username)
            if not profile:
                print(f"✗ Failed to create profile for {username}")
                return
            
            profile_id = profile['id']
            
            # Prepare session data
            session_data = data.copy()
            session_data['last_saved'] = datetime.now().isoformat()
            session_data['username'] = username
            
            # Extract GraphQL components
            doc_ids = None
            user_agent = None
            csrf_token = None
            app_id = None
            
            if graphql_data:
                doc_ids = graphql_data.get('doc_ids', {})
                user_agent = graphql_data.get('user_agent')
                csrf_token = graphql_data.get('csrf_token')
                app_id = graphql_data.get('app_id')
                print(f"  → Saving {len(doc_ids)} GraphQL endpoints")
            
            # Check if session exists
            existing = self.db.get_browser_session(profile_id)
            
            if existing:
                # Update existing session
                self.db.update_browser_session(
                    profile_id=profile_id,
                    session_data=session_data,
                    graphql_metadata=doc_ids,
                    user_agent=user_agent,
                    csrf_token=csrf_token,
                    app_id=app_id
                )
                print(f"✓ Session updated for @{username}")
            else:
                # Create new session
                self.db.create_browser_session(
                    profile_id=profile_id,
                    session_data=session_data,
                    graphql_metadata=doc_ids,
                    user_agent=user_agent,
                    csrf_token=csrf_token,
                    app_id=app_id
                )
                print(f"✓ Session created for @{username}")
            
            # Save GraphQL endpoints separately
            if doc_ids:
                for endpoint_name, doc_id in doc_ids.items():
                    self.db.save_graphql_endpoint(profile_id, endpoint_name, doc_id)
            
            print(f"✓ Session info saved for {username}")
            
        except Exception as e:
            print(f"✗ Failed to save session for {username}: {e}")
    
    def load_session_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Load session information from database"""
        try:
            profile = self.db.get_profile_by_username(username)
            if not profile:
                return None
            
            session = self.db.get_browser_session(profile['id'])
            if not session:
                return None
            
            # Parse session data
            session_data = json.loads(session['session_data']) if isinstance(session['session_data'], str) else session['session_data']
            
            # Add GraphQL data if available
            if session.get('graphql_metadata'):
                graphql_metadata = json.loads(session['graphql_metadata']) if isinstance(session['graphql_metadata'], str) else session['graphql_metadata']
                session_data['graphql'] = {
                    'doc_ids': graphql_metadata,
                    'user_agent': session.get('user_agent'),
                    'csrf_token': session.get('csrf_token'),
                    'app_id': session.get('app_id')
                }
            
            return session_data
            
        except Exception as e:
            print(f"✗ Failed to load session for {username}: {e}")
            return None
    
    def has_saved_session(self, username: str) -> bool:
        """Check if a saved session exists in database"""
        try:
            profile = self.db.get_profile_by_username(username)
            if not profile:
                return False
            
            session = self.db.get_browser_session(profile['id'])
            return session is not None and session.get('is_active', False)
            
        except Exception as e:
            print(f"✗ Failed to check session for {username}: {e}")
            return False
    
    def create_browser_context(self, browser, username: str):
        """Create a browser context with database-backed storage state"""
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'en-US',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # Load cookies from database if available
        try:
            profile = self.db.get_profile_by_username(username)
            if profile:
                session = self.db.get_browser_session(profile['id'])
                if session and session.get('cookies'):
                    cookies = json.loads(session['cookies']) if isinstance(session['cookies'], str) else session['cookies']
                    if cookies:
                        print(f"✓ Loading saved session for {username} from database")
                        # Create context first
                        context = browser.new_context(**context_options)
                        # Then add cookies
                        if isinstance(cookies, list) and cookies:
                            context.add_cookies(cookies)
                        return context
        except Exception as e:
            print(f"⚠ Could not load cookies from database: {e}")
        
        print(f"→ Creating new session for {username}")
        context = browser.new_context(**context_options)
        return context
    
    def save_context_state(self, context, username: str, graphql_data: Optional[Dict[str, Any]] = None):
        """Save the current context state to database"""
        try:
            # Get cookies from context
            cookies = context.cookies()
            
            # Get or create profile
            profile = self.db.get_or_create_profile(username)
            if not profile:
                print(f"✗ Failed to create profile for {username}")
                return
            
            profile_id = profile['id']
            
            # Prepare session data
            session_data = {
                'username': username,
                'last_saved': datetime.now().isoformat()
            }
            
            # Save to database
            existing = self.db.get_browser_session(profile_id)
            
            if existing:
                self.db.update_browser_session(
                    profile_id=profile_id,
                    session_data=session_data,
                    cookies=cookies,
                    graphql_metadata=graphql_data.get('doc_ids') if graphql_data else None,
                    user_agent=graphql_data.get('user_agent') if graphql_data else None,
                    csrf_token=graphql_data.get('csrf_token') if graphql_data else None,
                    app_id=graphql_data.get('app_id') if graphql_data else None
                )
            else:
                self.db.create_browser_session(
                    profile_id=profile_id,
                    session_data=session_data,
                    cookies=cookies,
                    graphql_metadata=graphql_data.get('doc_ids') if graphql_data else None,
                    user_agent=graphql_data.get('user_agent') if graphql_data else None,
                    csrf_token=graphql_data.get('csrf_token') if graphql_data else None,
                    app_id=graphql_data.get('app_id') if graphql_data else None
                )
            
            # Save GraphQL endpoints
            if graphql_data and graphql_data.get('doc_ids'):
                for endpoint_name, doc_id in graphql_data['doc_ids'].items():
                    self.db.save_graphql_endpoint(profile_id, endpoint_name, doc_id)
            
            print(f"✓ Session state saved to database for {username}")
            
        except Exception as e:
            print(f"✗ Failed to save session state: {e}")
    
    def list_profiles(self) -> List[str]:
        """List all saved profiles from database"""
        try:
            profiles = self.db.get_all_profiles()
            return [p['username'] for p in profiles if p.get('username')]
        except Exception as e:
            print(f"✗ Failed to list profiles: {e}")
            return []
    
    def get_profile_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get profile information from database"""
        try:
            profile = self.db.get_profile_by_username(username)
            if not profile:
                return None
            
            session = self.db.get_browser_session(profile['id'])
            if not session:
                return None
            
            # Build info dict
            info = {
                'username': username,
                'last_saved': session.get('updated_at', session.get('created_at')).isoformat() if session.get('updated_at') else 'Unknown',
                'has_graphql': bool(session.get('graphql_metadata')),
                'is_active': session.get('is_active', False)
            }
            
            # Add profile stats if available
            if profile.get('follower_count'):
                info['followers'] = profile['follower_count']
            if profile.get('following_count'):
                info['following'] = profile['following_count']
            
            return info
            
        except Exception as e:
            print(f"✗ Failed to get profile info for {username}: {e}")
            return None
    
    def clear_session(self, username: str):
        """Clear session for a specific user"""
        try:
            profile = self.db.get_profile_by_username(username)
            if profile:
                self.db.deactivate_browser_session(profile['id'])
                print(f"✓ Session cleared for {username}")
            else:
                print(f"⚠ No profile found for {username}")
        except Exception as e:
            print(f"✗ Failed to clear session for {username}: {e}")
    
    def clear_all_sessions(self):
        """Clear all sessions"""
        try:
            profiles = self.db.get_all_profiles()
            for profile in profiles:
                self.db.deactivate_browser_session(profile['id'])
            print(f"✓ Cleared {len(profiles)} sessions")
        except Exception as e:
            print(f"✗ Failed to clear sessions: {e}")
    
    def update_profile_stats(self, username: str, stats: Dict[str, Any]):
        """Update profile statistics"""
        try:
            profile = self.db.get_profile_by_username(username)
            if profile:
                self.db.update_profile(
                    profile_id=profile['id'],
                    user_id=stats.get('user_id'),
                    full_name=stats.get('full_name'),
                    bio=stats.get('bio'),
                    follower_count=stats.get('follower_count'),
                    following_count=stats.get('following_count'),
                    media_count=stats.get('media_count'),
                    is_verified=stats.get('is_verified')
                )
        except Exception as e:
            print(f"✗ Failed to update profile stats: {e}")
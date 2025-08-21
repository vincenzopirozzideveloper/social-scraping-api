"""GraphQL request interceptor for Instagram"""

import json
import re
from typing import Dict, Any, Optional, List
from urllib.parse import parse_qs
from .endpoints import Endpoints


class GraphQLInterceptor:
    """Intercept and parse GraphQL requests during Instagram navigation"""
    
    def __init__(self):
        self.captured_requests = []
        self.profile_query_info = None
        self.user_agent = None
        self.csrf_token = None
        self.app_id = None
        self.doc_ids = {}
        
    def setup_interception(self, page):
        """Setup request/response interception on page"""
        
        # Intercept requests to capture headers and body
        def handle_request(request):
            # Check if this is a GraphQL request
            if any(pattern in request.url for pattern in ['graphql/query', '/api/graphql']):
                try:
                    headers = request.headers
                    
                    # Capture important headers
                    if not self.user_agent and 'user-agent' in headers:
                        self.user_agent = headers['user-agent']
                    
                    if 'x-csrftoken' in headers:
                        self.csrf_token = headers['x-csrftoken']
                    
                    if 'x-ig-app-id' in headers:
                        self.app_id = headers['x-ig-app-id']
                    
                    # Try to get POST body
                    post_data = request.post_data
                    if post_data:
                        # Parse URL-encoded body
                        parsed = parse_qs(post_data)
                        
                        # Extract doc_id and friendly name
                        doc_id = parsed.get('doc_id', [None])[0]
                        friendly_name = parsed.get('fb_api_req_friendly_name', [None])[0]
                        
                        if doc_id and friendly_name:
                            self.doc_ids[friendly_name] = doc_id
                            print(f"  → Captured GraphQL: {friendly_name} (doc_id: {doc_id})")
                            
                            # Save specific queries we're interested in
                            if 'ProfilePage' in friendly_name or 'UserQuery' in friendly_name:
                                variables = parsed.get('variables', [None])[0]
                                if variables:
                                    self.profile_query_info = {
                                        'doc_id': doc_id,
                                        'friendly_name': friendly_name,
                                        'variables_template': json.loads(variables) if variables else {}
                                    }
                        
                        # Store full request info
                        self.captured_requests.append({
                            'url': request.url,
                            'headers': dict(headers),
                            'body': post_data,
                            'parsed_body': parsed,
                            'doc_id': doc_id,
                            'friendly_name': friendly_name
                        })
                        
                except Exception as e:
                    # Silently handle errors to not break navigation
                    pass
        
        # Intercept responses to get user data
        def handle_response(response):
            # Check if this is a GraphQL response
            if any(pattern in response.url for pattern in ['graphql/query', '/api/graphql']):
                try:
                    if response.status == 200:
                        # Try to get response body for user info
                        response_body = response.json()
                        
                        # Check if this response contains user data
                        if response_body and 'data' in response_body:
                            data = response_body['data']
                            
                            # Look for user info in various places
                            if 'user' in data:
                                user = data['user']
                                if 'id' in user or 'pk' in user:
                                    print(f"  → Found user data: {user.get('username', 'unknown')}")
                            
                            if 'viewer' in data and 'user' in data['viewer']:
                                viewer = data['viewer']['user']
                                if 'id' in viewer or 'pk' in viewer:
                                    print(f"  → Found viewer data: ID {viewer.get('id', viewer.get('pk'))}")
                                    
                except Exception:
                    # Silently handle errors
                    pass
        
        # Set up listeners
        page.on('request', handle_request)
        page.on('response', handle_response)
        
        print("GraphQL interceptor activated")
    
    def get_session_data(self) -> Dict[str, Any]:
        """Get all captured data for saving to session"""
        return {
            'user_agent': self.user_agent,
            'csrf_token': self.csrf_token,
            'app_id': self.app_id,
            'doc_ids': self.doc_ids,
            'profile_query_info': self.profile_query_info,
            'captured_requests_count': len(self.captured_requests)
        }
    
    def get_profile_doc_id(self) -> Optional[str]:
        """Get the doc_id for profile queries"""
        if self.profile_query_info:
            return self.profile_query_info['doc_id']
        
        # Fallback to known profile query names
        for name, doc_id in self.doc_ids.items():
            if 'Profile' in name or 'User' in name:
                return doc_id
        
        return None
"""Like and Comment actions using GraphQL for Instagram"""

from typing import Optional, Dict, Any
from urllib.parse import quote
from .base import BaseAction, ActionResult
from ..api import Endpoints


class LikeActionGraphQL(BaseAction):
    """Action to like a post using GraphQL"""
    
    def __init__(self, page, session_manager, username: str, session_id: Optional[int] = None):
        super().__init__(page, session_manager, username, session_id)
        self.action_type = "like"
        
        # GraphQL doc ID for like mutation
        self.like_doc_id = "23951234354462179"
        
        # Load saved GraphQL metadata if available
        saved_info = session_manager.load_session_info(username)
        if saved_info and 'graphql' in saved_info:
            self.graphql_metadata = saved_info['graphql']
            # Check if we have a different doc_id for likes
            if 'doc_ids' in self.graphql_metadata:
                doc_ids = self.graphql_metadata['doc_ids']
                if 'usePolarisLikeMediaLikeMutation' in doc_ids:
                    self.like_doc_id = doc_ids['usePolarisLikeMediaLikeMutation']
        else:
            self.graphql_metadata = None
    
    def execute(self, media_id: str, media_code: Optional[str] = None, container_module: str = "feed_timeline") -> ActionResult:
        """Like a post by its media ID using GraphQL"""
        print(f"\n{'='*50}")
        print(f"LIKE ACTION (GraphQL)")
        print(f"{'='*50}")
        print(f"Media ID: {media_id}")
        if media_code:
            print(f"Media Code: {media_code}")
        
        # Extract just the numeric media ID if it contains underscore
        # Format: 3664720334645061823_65195399799 -> 3664720334645061823
        if '_' in str(media_id):
            media_id_only = str(media_id).split('_')[0]
            print(f"Extracted media ID: {media_id_only}")
        else:
            media_id_only = str(media_id)
        
        # Build GraphQL request
        url = "https://www.instagram.com/graphql/query"
        
        # Get headers with GraphQL specific additions
        headers = self.get_headers()
        headers.update({
            'x-fb-friendly-name': 'usePolarisLikeMediaLikeMutation',
            'x-root-field-name': 'xdt_mark_media_like'
        })
        
        # Add GraphQL metadata if available
        if self.graphql_metadata:
            if 'lsd' in self.graphql_metadata:
                headers['x-fb-lsd'] = self.graphql_metadata['lsd']
            if 'fb_dtsg' in self.graphql_metadata:
                fb_dtsg = self.graphql_metadata['fb_dtsg']
            else:
                fb_dtsg = ""
        else:
            fb_dtsg = ""
        
        # Build variables
        variables = {
            "media_id": media_id_only,
            "container_module": container_module
        }
        
        # Build the body with all required parameters
        import json
        body_params = {
            'variables': json.dumps(variables),
            'doc_id': self.like_doc_id
        }
        
        # Add fb_dtsg if available
        if fb_dtsg:
            body_params['fb_dtsg'] = fb_dtsg
        
        # Add lsd if available  
        if self.graphql_metadata and 'lsd' in self.graphql_metadata:
            body_params['lsd'] = self.graphql_metadata['lsd']
        
        # URL encode the body
        body = '&'.join([f"{k}={quote(str(v), safe='')}" for k, v in body_params.items()])
        
        print(f"[DEBUG] GraphQL doc_id: {self.like_doc_id}")
        print(f"[DEBUG] Variables: {variables}")
        
        # Execute request
        success, response_data = self.execute_request(url, body, headers)
        
        # Create result
        if success and response_data:
            # Check GraphQL response structure
            if 'data' in response_data:
                data = response_data['data']
                # Check if like was successful
                if 'xdt_mark_media_like' in data or response_data.get('status') == 'ok':
                    print(f"✓ Successfully liked post {media_code or media_id}")
                    result = ActionResult(
                        success=True,
                        action_type=self.action_type,
                        target_id=media_id,
                        target_username=media_code,
                        response_data=response_data
                    )
                else:
                    print(f"✗ Failed to like - unexpected GraphQL response")
                    result = ActionResult(
                        success=False,
                        action_type=self.action_type,
                        target_id=media_id,
                        target_username=media_code,
                        response_data=response_data,
                        error_message="GraphQL mutation failed"
                    )
            elif response_data.get('status') == 'ok':
                # Sometimes Instagram returns simple status
                print(f"✓ Successfully liked post {media_code or media_id}")
                result = ActionResult(
                    success=True,
                    action_type=self.action_type,
                    target_id=media_id,
                    target_username=media_code,
                    response_data=response_data
                )
            else:
                print(f"✗ Failed to like - unexpected response structure")
                result = ActionResult(
                    success=False,
                    action_type=self.action_type,
                    target_id=media_id,
                    target_username=media_code,
                    response_data=response_data,
                    error_message="Invalid response structure"
                )
        else:
            error_msg = response_data.get('message', 'Unknown error') if response_data else 'Request failed'
            print(f"✗ Failed to like: {error_msg}")
            result = ActionResult(
                success=False,
                action_type=self.action_type,
                target_id=media_id,
                target_username=media_code,
                response_data=response_data,
                error_message=error_msg
            )
        
        # Log the action
        self.log_action(result)
        return result


class CommentActionGraphQL(BaseAction):
    """Action to comment on a post - still uses REST API"""
    
    def __init__(self, page, session_manager, username: str, session_id: Optional[int] = None):
        super().__init__(page, session_manager, username, session_id)
        self.action_type = "comment"
    
    def execute(self, media_id: str, comment_text: str, media_code: Optional[str] = None) -> ActionResult:
        """Comment on a post by its media ID"""
        print(f"\n{'='*50}")
        print(f"COMMENT ACTION")
        print(f"{'='*50}")
        print(f"Media ID: {media_id}")
        print(f"Comment: {comment_text}")
        if media_code:
            print(f"Media Code: {media_code}")
        
        # Extract just the numeric media ID if it contains underscore
        # Format: 3664720334645061823_65195399799 -> 3664720334645061823
        if '_' in str(media_id):
            media_id_only = str(media_id).split('_')[0]
            print(f"Extracted media ID: {media_id_only}")
        else:
            media_id_only = str(media_id)
        
        # Build request URL - format: /api/v1/web/comments/{media_id}/add/
        url = f"https://www.instagram.com/api/v1/web/comments/{media_id_only}/add/"
        headers = self.get_headers()
        
        # Comment request body - URL encoded
        # Format from networks/comment/req.js: comment_text=top+%F0%9F%92%AF&jazoest=22718
        encoded_comment = quote(comment_text, safe='')
        body = f"comment_text={encoded_comment}"
        
        # Add jazoest if available
        if hasattr(self, 'jazoest'):
            body += f"&jazoest={self.jazoest}"
        
        # Execute request
        success, response_data = self.execute_request(url, body, headers)
        
        # Create result
        if success and response_data:
            if response_data.get('status') == 'ok':
                print(f"✓ Successfully commented on post {media_code or media_id}")
                
                # Extract comment ID and build URL
                comment_id = response_data.get('id')
                comment_url = None
                if comment_id and media_code:
                    comment_url = f"https://www.instagram.com/p/{media_code}/c/{comment_id}/"
                    print(f"📍 Comment URL: {comment_url}")
                
                # Save comment to database
                if self.db and self.profile_id:
                    try:
                        self.db.save_comment(
                            comment_id=comment_id,
                            media_id=media_id_only,
                            media_code=media_code,
                            comment_text=comment_text,
                            comment_url=comment_url,
                            profile_id=self.profile_id
                        )
                    except Exception as e:
                        print(f"[WARNING] Failed to save comment to DB: {e}")
                
                result = ActionResult(
                    success=True,
                    action_type=self.action_type,
                    target_id=media_id,
                    target_username=media_code,
                    response_data=response_data
                )
            else:
                print(f"✗ Failed to comment - unexpected response")
                result = ActionResult(
                    success=False,
                    action_type=self.action_type,
                    target_id=media_id,
                    target_username=media_code,
                    response_data=response_data,
                    error_message="Status not ok"
                )
        else:
            error_msg = response_data.get('message', 'Unknown error') if response_data else 'Request failed'
            print(f"✗ Failed to comment: {error_msg}")
            result = ActionResult(
                success=False,
                action_type=self.action_type,
                target_id=media_id,
                target_username=media_code,
                response_data=response_data,
                error_message=error_msg
            )
        
        # Log the action
        self.log_action(result)
        return result
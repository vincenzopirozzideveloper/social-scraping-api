"""Like and Comment actions for Instagram"""

from typing import Optional, Dict, Any
from urllib.parse import quote
from .base import BaseAction, ActionResult
from ..api import Endpoints


class LikeAction(BaseAction):
    """Action to like a post"""
    
    def __init__(self, page, session_manager, username: str):
        super().__init__(page, session_manager, username)
        self.action_type = "like"
    
    def execute(self, media_id: str, media_code: Optional[str] = None) -> ActionResult:
        """Like a post by its media ID"""
        print(f"\n{'='*50}")
        print(f"LIKE ACTION")
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
        
        # Build request URL - format: /api/v1/web/likes/{media_id}/like/
        url = f"https://www.instagram.com/api/v1/web/likes/{media_id_only}/like/"
        headers = self.get_headers()
        
        # Like request typically has empty body
        body = ""
        
        # Execute request
        success, response_data = self.execute_request(url, body, headers)
        
        # Create result
        if success and response_data:
            if response_data.get('status') == 'ok':
                print(f"✓ Successfully liked post {media_code or media_id}")
                result = ActionResult(
                    success=True,
                    action_type=self.action_type,
                    target_id=media_id,
                    target_username=media_code,
                    response_data=response_data
                )
            else:
                print(f"✗ Failed to like - unexpected response")
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


class CommentAction(BaseAction):
    """Action to comment on a post"""
    
    def __init__(self, page, session_manager, username: str):
        super().__init__(page, session_manager, username)
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
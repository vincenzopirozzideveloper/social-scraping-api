"""Follow and Unfollow actions for Instagram"""

from typing import Optional, Dict, Any, List
from .base import BaseAction, ActionResult
from ..api import Endpoints


class FollowAction(BaseAction):
    """Action to follow a user"""
    
    def __init__(self, page, session_manager, username: str):
        super().__init__(page, session_manager, username)
        self.action_type = "follow"
    
    def execute(self, target_id: str, target_username: Optional[str] = None) -> ActionResult:
        """Follow a user by their ID"""
        print(f"\n{'='*50}")
        print(f"FOLLOW ACTION")
        print(f"{'='*50}")
        print(f"Target ID: {target_id}")
        if target_username:
            print(f"Target Username: @{target_username}")
        
        # Build request
        url = Endpoints.FRIENDSHIPS_CREATE.format(user_id=target_id)
        headers = self.get_headers()
        body = self.get_body_params(target_id)
        
        # Execute request
        success, response_data = self.execute_request(url, body, headers)
        
        # Create result
        if success and response_data:
            friendship_status = response_data.get('friendship_status', {})
            if friendship_status.get('following'):
                print(f"✓ Successfully followed {target_username or target_id}")
                result = ActionResult(
                    success=True,
                    action_type=self.action_type,
                    target_id=target_id,
                    target_username=target_username,
                    response_data=response_data
                )
            else:
                print(f"✗ Failed to follow - unexpected response")
                result = ActionResult(
                    success=False,
                    action_type=self.action_type,
                    target_id=target_id,
                    target_username=target_username,
                    response_data=response_data,
                    error_message="Following status is false"
                )
        else:
            error_msg = response_data.get('message', 'Unknown error') if response_data else 'Request failed'
            print(f"✗ Failed to follow: {error_msg}")
            result = ActionResult(
                success=False,
                action_type=self.action_type,
                target_id=target_id,
                target_username=target_username,
                response_data=response_data,
                error_message=error_msg
            )
        
        # Log the action
        self.log_action(result)
        return result


class UnfollowAction(BaseAction):
    """Action to unfollow a user"""
    
    def __init__(self, page, session_manager, username: str):
        super().__init__(page, session_manager, username)
        self.action_type = "unfollow"
    
    def execute(self, target_id: str, target_username: Optional[str] = None) -> ActionResult:
        """Unfollow a user by their ID"""
        print(f"\n{'='*50}")
        print(f"UNFOLLOW ACTION")
        print(f"{'='*50}")
        print(f"Target ID: {target_id}")
        if target_username:
            print(f"Target Username: @{target_username}")
        
        # Build request
        url = Endpoints.FRIENDSHIPS_DESTROY.format(user_id=target_id)
        headers = self.get_headers()
        body = self.get_body_params(target_id)
        
        # Execute request
        success, response_data = self.execute_request(url, body, headers)
        
        # Create result
        if success and response_data:
            friendship_status = response_data.get('friendship_status', {})
            if not friendship_status.get('following'):
                print(f"✓ Successfully unfollowed {target_username or target_id}")
                result = ActionResult(
                    success=True,
                    action_type=self.action_type,
                    target_id=target_id,
                    target_username=target_username,
                    response_data=response_data
                )
            else:
                print(f"✗ Failed to unfollow - still following")
                result = ActionResult(
                    success=False,
                    action_type=self.action_type,
                    target_id=target_id,
                    target_username=target_username,
                    response_data=response_data,
                    error_message="Still following after unfollow attempt"
                )
        else:
            error_msg = response_data.get('message', 'Unknown error') if response_data else 'Request failed'
            print(f"✗ Failed to unfollow: {error_msg}")
            result = ActionResult(
                success=False,
                action_type=self.action_type,
                target_id=target_id,
                target_username=target_username,
                response_data=response_data,
                error_message=error_msg
            )
        
        # Log the action
        self.log_action(result)
        return result
    
    def batch_unfollow(self, user_list: List[Dict[str, Any]], delay_between: bool = True) -> List[ActionResult]:
        """Unfollow multiple users with delays"""
        results = []
        total = len(user_list)
        
        print(f"\n{'='*50}")
        print(f"BATCH UNFOLLOW - {total} users")
        print(f"{'='*50}")
        
        for i, user in enumerate(user_list, 1):
            user_id = str(user.get('id', user.get('pk')))
            username = user.get('username')
            
            print(f"\n[{i}/{total}] Processing @{username}...")
            
            # Execute unfollow
            result = self.execute(user_id, username)
            results.append(result)
            
            # Add delay between actions (except for the last one)
            if delay_between and i < total:
                self.wait_with_variance()
        
        # Summary
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        
        print(f"\n{'='*50}")
        print(f"BATCH UNFOLLOW COMPLETE")
        print(f"{'='*50}")
        print(f"✓ Successful: {successful}")
        print(f"✗ Failed: {failed}")
        print(f"Total: {total}")
        
        return results
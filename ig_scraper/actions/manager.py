"""Action manager for batch operations and queue management"""

import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections import deque

from .base import BaseAction, ActionResult


@dataclass
class QueuedAction:
    """Represents an action in the queue"""
    action: BaseAction
    target_id: str
    target_username: Optional[str] = None
    priority: int = 0  # Higher priority = executed first
    
    
class ActionManager:
    """Manages action queues and batch operations"""
    
    def __init__(self, page, session_manager, username: str):
        self.page = page
        self.session_manager = session_manager
        self.username = username
        
        # Action queue
        self.queue = deque()
        
        # Statistics
        self.stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        
        # Results storage
        self.results = []
        
        # Create stats directory
        self.stats_dir = Path("action_logs") / username / "stats"
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        
    def add_action(self, action: BaseAction, target_id: str, target_username: Optional[str] = None, priority: int = 0):
        """Add an action to the queue"""
        queued = QueuedAction(
            action=action,
            target_id=target_id,
            target_username=target_username,
            priority=priority
        )
        
        if priority > 0:
            # Insert based on priority
            inserted = False
            for i, item in enumerate(self.queue):
                if item.priority < priority:
                    self.queue.insert(i, queued)
                    inserted = True
                    break
            if not inserted:
                self.queue.append(queued)
        else:
            self.queue.append(queued)
            
        print(f"→ Queued {action.action_type} for {target_username or target_id}")
    
    def clear_queue(self):
        """Clear the action queue"""
        self.queue.clear()
        print("✓ Queue cleared")
    
    def execute_queue(self, delay_between: bool = True, save_progress: bool = True) -> List[ActionResult]:
        """Execute all actions in the queue"""
        total = len(self.queue)
        if total == 0:
            print("Queue is empty")
            return []
        
        print(f"\n{'='*50}")
        print(f"EXECUTING ACTION QUEUE")
        print(f"Total actions: {total}")
        print(f"{'='*50}")
        
        # Reset stats
        self.stats = {
            'total': total,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        
        self.results = []
        session_file = self.stats_dir / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        while self.queue:
            queued_action = self.queue.popleft()
            current = total - len(self.queue)
            
            print(f"\n[{current}/{total}] Executing {queued_action.action.action_type}...")
            
            try:
                # Execute the action
                result = queued_action.action.execute(
                    queued_action.target_id,
                    queued_action.target_username
                )
                
                self.results.append(result)
                
                if result.success:
                    self.stats['successful'] += 1
                else:
                    self.stats['failed'] += 1
                
                # Save progress
                if save_progress:
                    self.save_session_state(session_file)
                
                # Add delay between actions (except for the last one)
                if delay_between and len(self.queue) > 0:
                    queued_action.action.wait_with_variance()
                    
            except KeyboardInterrupt:
                print("\n⚠ Execution interrupted by user")
                self.stats['skipped'] = len(self.queue)
                break
            except Exception as e:
                print(f"✗ Error executing action: {e}")
                self.stats['failed'] += 1
                
                # Create error result
                error_result = ActionResult(
                    success=False,
                    action_type=queued_action.action.action_type,
                    target_id=queued_action.target_id,
                    target_username=queued_action.target_username,
                    error_message=str(e)
                )
                self.results.append(error_result)
        
        # Final summary
        self.print_summary()
        
        # Save final state
        if save_progress:
            self.save_session_state(session_file)
        
        return self.results
    
    def save_session_state(self, filepath: Path):
        """Save current session state"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats,
            'remaining_queue': len(self.queue),
            'results': [
                {
                    'success': r.success,
                    'action_type': r.action_type,
                    'target_username': r.target_username,
                    'target_id': r.target_id,
                    'error_message': r.error_message
                }
                for r in self.results
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def print_summary(self):
        """Print execution summary"""
        print(f"\n{'='*50}")
        print(f"EXECUTION SUMMARY")
        print(f"{'='*50}")
        print(f"Total: {self.stats['total']}")
        print(f"✓ Successful: {self.stats['successful']}")
        print(f"✗ Failed: {self.stats['failed']}")
        
        if self.stats['skipped'] > 0:
            print(f"⚠ Skipped: {self.stats['skipped']}")
        
        if self.stats['total'] > 0:
            success_rate = (self.stats['successful'] / self.stats['total']) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        print(f"{'='*50}")
    
    def get_failed_actions(self) -> List[ActionResult]:
        """Get list of failed actions"""
        return [r for r in self.results if not r.success]
    
    def retry_failed(self, delay_between: bool = True) -> List[ActionResult]:
        """Retry all failed actions"""
        failed = self.get_failed_actions()
        if not failed:
            print("No failed actions to retry")
            return []
        
        print(f"\n{'='*50}")
        print(f"RETRYING {len(failed)} FAILED ACTIONS")
        print(f"{'='*50}")
        
        # Re-queue failed actions
        for result in failed:
            # We need to recreate the action based on type
            if result.action_type == "follow":
                from .follow import FollowAction
                action = FollowAction(self.page, self.session_manager, self.username)
            elif result.action_type == "unfollow":
                from .follow import UnfollowAction
                action = UnfollowAction(self.page, self.session_manager, self.username)
            else:
                continue
            
            self.add_action(action, result.target_id, result.target_username)
        
        # Execute the retry queue
        return self.execute_queue(delay_between=delay_between)
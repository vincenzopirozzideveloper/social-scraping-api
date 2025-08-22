"""Task manager for running operations in background"""

import threading
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import uuid


class Task:
    """Represents a background task"""
    
    def __init__(self, name: str, target: Callable, args: tuple = (), kwargs: dict = None):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.thread: Optional[threading.Thread] = None
        self.status = "pending"
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.result: Any = None
        
    def start(self):
        """Start the task in a background thread"""
        if self.status != "pending":
            return False
            
        def wrapper():
            try:
                self.status = "running"
                self.started_at = datetime.now()
                self.result = self.target(*self.args, **self.kwargs)
                self.status = "completed"
            except Exception as e:
                self.status = "failed"
                self.error = str(e)
            finally:
                self.completed_at = datetime.now()
        
        self.thread = threading.Thread(target=wrapper, daemon=True)
        self.thread.start()
        return True
    
    def is_alive(self) -> bool:
        """Check if task is still running"""
        return self.thread and self.thread.is_alive()
    
    def get_info(self) -> Dict[str, Any]:
        """Get task information"""
        info = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        
        if self.status == "running" and self.started_at:
            duration = (datetime.now() - self.started_at).total_seconds()
            info["duration"] = f"{int(duration)}s"
        elif self.completed_at and self.started_at:
            duration = (self.completed_at - self.started_at).total_seconds()
            info["duration"] = f"{int(duration)}s"
            
        if self.error:
            info["error"] = self.error
            
        return info


class TaskManager:
    """Manages background tasks"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
    
    def create_task(self, name: str, target: Callable, *args, **kwargs) -> str:
        """Create and start a new task"""
        task = Task(name, target, args, kwargs)
        
        with self._lock:
            self.tasks[task.id] = task
            task.start()
            
        print(f"\n[TASK] Started: {name} (ID: {task.id})")
        return task.id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """List all tasks or filter by status"""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks
    
    def get_active_tasks(self) -> List[Task]:
        """Get all running tasks"""
        return self.list_tasks("running")
    
    def print_status(self):
        """Print status of all tasks"""
        print("\n" + "="*60)
        print("BACKGROUND TASKS STATUS")
        print("="*60)
        
        if not self.tasks:
            print("No tasks running")
        else:
            # Group by status
            running = self.list_tasks("running")
            completed = self.list_tasks("completed")
            failed = self.list_tasks("failed")
            pending = self.list_tasks("pending")
            
            if running:
                print("\n🔄 RUNNING:")
                for task in running:
                    info = task.get_info()
                    print(f"  [{info['id']}] {info['name']} - {info.get('duration', '0s')}")
            
            if completed:
                print("\n✅ COMPLETED:")
                for task in completed[-5:]:  # Show last 5
                    info = task.get_info()
                    print(f"  [{info['id']}] {info['name']} - {info.get('duration', '0s')}")
            
            if failed:
                print("\n❌ FAILED:")
                for task in failed[-5:]:  # Show last 5
                    info = task.get_info()
                    print(f"  [{info['id']}] {info['name']} - {info.get('error', 'Unknown error')}")
            
            if pending:
                print("\n⏳ PENDING:")
                for task in pending:
                    info = task.get_info()
                    print(f"  [{info['id']}] {info['name']}")
        
        print("="*60)
    
    def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> bool:
        """Wait for a task to complete"""
        task = self.get_task(task_id)
        if not task or not task.thread:
            return False
        
        task.thread.join(timeout)
        return not task.is_alive()
    
    def cleanup_completed(self):
        """Remove completed and failed tasks older than 1 hour"""
        with self._lock:
            now = datetime.now()
            to_remove = []
            
            for task_id, task in self.tasks.items():
                if task.status in ["completed", "failed"] and task.completed_at:
                    age = (now - task.completed_at).total_seconds()
                    if age > 3600:  # 1 hour
                        to_remove.append(task_id)
            
            for task_id in to_remove:
                del self.tasks[task_id]
            
            if to_remove:
                print(f"[TASK] Cleaned up {len(to_remove)} old tasks")


# Global task manager instance
task_manager = TaskManager()
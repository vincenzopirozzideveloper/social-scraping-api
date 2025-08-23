"""Database models for Instagram scraper"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class Profile:
    """Profile model"""
    id: int
    username: str
    user_id: Optional[str] = None
    full_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class PostProcessed:
    """Post processed model"""
    id: int
    media_id: str
    media_code: Optional[str] = None
    owner_username: Optional[str] = None
    action_type: str = 'both'
    success: bool = True
    processed_at: Optional[datetime] = None
    profile_id: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class CommentMade:
    """Comment made model"""
    id: int
    comment_id: Optional[str] = None
    media_id: str
    media_code: Optional[str] = None
    comment_text: str
    comment_url: Optional[str] = None
    created_at: Optional[datetime] = None
    profile_id: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class AutomationSession:
    """Automation session model"""
    id: int
    profile_id: int
    search_query: Optional[str] = None
    posts_processed: int = 0
    likes_count: int = 0
    comments_count: int = 0
    errors_count: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: str = 'running'
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class ActionLog:
    """Action log model"""
    id: int
    session_id: int
    action_type: str
    target_id: str
    target_username: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    response_data: Optional[Dict] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)
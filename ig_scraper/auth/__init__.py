"""Authentication module"""

# Use database-backed session manager
from .session_manager_db import SessionManager

__all__ = ['SessionManager']
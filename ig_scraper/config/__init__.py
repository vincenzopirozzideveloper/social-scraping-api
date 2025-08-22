"""Configuration management for Instagram scraper"""

from .manager import ConfigManager
from .defaults import DEFAULT_CONFIG

__all__ = [
    'ConfigManager',
    'DEFAULT_CONFIG'
]
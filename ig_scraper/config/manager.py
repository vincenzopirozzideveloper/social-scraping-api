"""Configuration manager for profile-specific settings"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from copy import deepcopy
from .defaults import DEFAULT_CONFIG
from .env_config import BROWSER_SESSIONS_DIR


class ConfigManager:
    """Manages configuration for each Instagram profile"""
    
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else BROWSER_SESSIONS_DIR
        self.profiles_dir = self.base_dir / "profiles"
        
    def get_config_path(self, username: str) -> Path:
        """Get config file path for a profile"""
        profile_dir = self.profiles_dir / username
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir / "config.json"
    
    def load_config(self, username: str) -> Dict[str, Any]:
        """Load configuration for a profile, create if doesn't exist"""
        config_path = self.get_config_path(username)
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return self._merge_configs(DEFAULT_CONFIG, user_config)
            except Exception as e:
                print(f"Error loading config for {username}: {e}")
                print("Using default configuration")
        
        # Create default config for new profile
        self.save_config(username, DEFAULT_CONFIG)
        return deepcopy(DEFAULT_CONFIG)
    
    def save_config(self, username: str, config: Dict[str, Any]):
        """Save configuration for a profile"""
        config_path = self.get_config_path(username)
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving config for {username}: {e}")
            return False
    
    def get_value(self, username: str, key_path: str, default: Any = None) -> Any:
        """Get a specific configuration value using dot notation
        
        Example: config.get_value('user1', 'scraping.following.max_count')
        """
        config = self.load_config(username)
        
        keys = key_path.split('.')
        value = config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_value(self, username: str, key_path: str, value: Any) -> bool:
        """Set a specific configuration value using dot notation
        
        Example: config.set_value('user1', 'scraping.following.max_count', 100)
        """
        config = self.load_config(username)
        
        keys = key_path.split('.')
        target = config
        
        try:
            # Navigate to the parent of the target key
            for key in keys[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]
            
            # Set the value
            target[keys[-1]] = value
            
            # Save the updated config
            return self.save_config(username, config)
        except Exception as e:
            print(f"Error setting config value: {e}")
            return False
    
    def update_section(self, username: str, section: str, values: Dict[str, Any]) -> bool:
        """Update an entire configuration section"""
        config = self.load_config(username)
        
        if section in config:
            config[section].update(values)
            return self.save_config(username, config)
        else:
            print(f"Section '{section}' not found in config")
            return False
    
    def reset_to_defaults(self, username: str) -> bool:
        """Reset a profile's configuration to defaults"""
        return self.save_config(username, deepcopy(DEFAULT_CONFIG))
    
    def list_profiles_with_config(self) -> list:
        """List all profiles that have configuration files"""
        profiles = []
        
        if self.profiles_dir.exists():
            for profile_dir in self.profiles_dir.iterdir():
                if profile_dir.is_dir():
                    config_path = profile_dir / "config.json"
                    if config_path.exists():
                        profiles.append(profile_dir.name)
        
        return sorted(profiles)
    
    def export_config(self, username: str, export_path: str) -> bool:
        """Export a profile's configuration to a file"""
        config = self.load_config(username)
        
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"Config exported to {export_path}")
            return True
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False
    
    def import_config(self, username: str, import_path: str) -> bool:
        """Import configuration from a file"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Merge with defaults to ensure all keys exist
            merged = self._merge_configs(DEFAULT_CONFIG, config)
            return self.save_config(username, merged)
        except Exception as e:
            print(f"Error importing config: {e}")
            return False
    
    def _merge_configs(self, default: Dict, user: Dict) -> Dict:
        """Deep merge user config with default config"""
        result = deepcopy(default)
        
        def merge_dict(base, overlay):
            for key, value in overlay.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value
        
        merge_dict(result, user)
        return result
    
    def display_config(self, username: str, section: Optional[str] = None):
        """Display configuration in a readable format"""
        config = self.load_config(username)
        
        if section:
            if section in config:
                config = {section: config[section]}
            else:
                print(f"Section '{section}' not found")
                return
        
        print(f"\nConfiguration for @{username}:")
        print("=" * 50)
        self._print_config(config)
        print("=" * 50)
    
    def _print_config(self, config: Dict, indent: int = 0):
        """Recursively print configuration"""
        for key, value in config.items():
            if isinstance(value, dict):
                print("  " * indent + f"{key}:")
                self._print_config(value, indent + 1)
            else:
                print("  " * indent + f"{key}: {value}")
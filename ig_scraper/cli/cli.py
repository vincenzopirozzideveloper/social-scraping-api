#!/usr/bin/env python
"""Command-line interface for Instagram Scraper configuration"""

import sys
import argparse
from pathlib import Path
from ..config import ConfigManager
from ..auth import SessionManager


class CLI:
    """Command-line interface handler"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.session_manager = SessionManager()
    
    def select_profile(self) -> str:
        """Interactive profile selection"""
        profiles = self.session_manager.list_profiles()
        
        if not profiles:
            print("No profiles found. Please login first using main.py")
            sys.exit(1)
        
        print("\nAvailable profiles:")
        print("-" * 30)
        for i, profile in enumerate(profiles, 1):
            print(f"{i}. @{profile}")
        print("-" * 30)
        
        while True:
            try:
                choice = input(f"Select profile (1-{len(profiles)}): ")
                idx = int(choice) - 1
                if 0 <= idx < len(profiles):
                    return profiles[idx]
                else:
                    print("Invalid selection")
            except ValueError:
                print("Please enter a number")
    
    def config_get(self, args):
        """Get configuration value"""
        username = args.profile or self.select_profile()
        
        value = self.config_manager.get_value(username, args.key)
        
        if value is not None:
            print(f"\n@{username} - {args.key}: {value}")
        else:
            print(f"Key '{args.key}' not found")
    
    def config_set(self, args):
        """Set configuration value"""
        username = args.profile or self.select_profile()
        
        # Convert value to appropriate type
        value = args.value
        if value.lower() in ['true', 'false']:
            value = value.lower() == 'true'
        elif value.isdigit():
            value = int(value)
        elif '.' in value and all(p.isdigit() for p in value.split('.', 1)):
            value = float(value)
        
        if self.config_manager.set_value(username, args.key, value):
            print(f"\n✓ @{username} - {args.key} set to: {value}")
        else:
            print(f"✗ Failed to set {args.key}")
    
    def config_show(self, args):
        """Show configuration"""
        username = args.profile or self.select_profile()
        self.config_manager.display_config(username, args.section)
    
    def config_reset(self, args):
        """Reset configuration to defaults"""
        username = args.profile or self.select_profile()
        
        confirm = input(f"Reset configuration for @{username} to defaults? (yes/no): ")
        if confirm.lower() == 'yes':
            if self.config_manager.reset_to_defaults(username):
                print(f"✓ Configuration reset for @{username}")
            else:
                print("✗ Failed to reset configuration")
        else:
            print("Operation cancelled")
    
    def config_export(self, args):
        """Export configuration"""
        username = args.profile or self.select_profile()
        
        export_path = args.output or f"{username}_config.json"
        if self.config_manager.export_config(username, export_path):
            print(f"✓ Configuration exported to {export_path}")
    
    def config_import(self, args):
        """Import configuration"""
        username = args.profile or self.select_profile()
        
        if not Path(args.file).exists():
            print(f"File {args.file} not found")
            return
        
        if self.config_manager.import_config(username, args.file):
            print(f"✓ Configuration imported for @{username}")
    
    def config_list(self, args):
        """List all configuration keys"""
        print("\nAvailable configuration keys:")
        print("=" * 50)
        
        def print_keys(d, prefix=""):
            for key, value in d.items():
                full_key = f"{prefix}{key}" if prefix else key
                if isinstance(value, dict):
                    print(f"\n{full_key}:")
                    print_keys(value, f"{full_key}.")
                else:
                    print(f"  {full_key}: {type(value).__name__} (default: {value})")
        
        from ..config.defaults import DEFAULT_CONFIG
        print_keys(DEFAULT_CONFIG)
        print("=" * 50)
        print("\nUse: cli.py config:get <key> to read a value")
        print("Use: cli.py config:set <key> <value> to set a value")


def main():
    """Main CLI entry point"""
    cli = CLI()
    
    parser = argparse.ArgumentParser(
        description='Instagram Scraper Configuration CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py config:show                                    # Show all config
  python cli.py config:show --section scraping                 # Show section
  python cli.py config:get scraping.following.max_count        # Get value
  python cli.py config:set scraping.following.max_count 100    # Set value
  python cli.py config:reset                                   # Reset to defaults
  python cli.py config:export --output my_config.json          # Export config
  python cli.py config:import --file my_config.json            # Import config
  python cli.py config:list                                    # List all keys
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # config:get command
    get_parser = subparsers.add_parser('config:get', help='Get configuration value')
    get_parser.add_argument('key', help='Configuration key (dot notation)')
    get_parser.add_argument('--profile', '-p', help='Profile username (optional)')
    
    # config:set command
    set_parser = subparsers.add_parser('config:set', help='Set configuration value')
    set_parser.add_argument('key', help='Configuration key (dot notation)')
    set_parser.add_argument('value', help='Value to set')
    set_parser.add_argument('--profile', '-p', help='Profile username (optional)')
    
    # config:show command
    show_parser = subparsers.add_parser('config:show', help='Show configuration')
    show_parser.add_argument('--section', '-s', help='Show specific section only')
    show_parser.add_argument('--profile', '-p', help='Profile username (optional)')
    
    # config:reset command
    reset_parser = subparsers.add_parser('config:reset', help='Reset to defaults')
    reset_parser.add_argument('--profile', '-p', help='Profile username (optional)')
    
    # config:export command
    export_parser = subparsers.add_parser('config:export', help='Export configuration')
    export_parser.add_argument('--output', '-o', help='Output file path')
    export_parser.add_argument('--profile', '-p', help='Profile username (optional)')
    
    # config:import command
    import_parser = subparsers.add_parser('config:import', help='Import configuration')
    import_parser.add_argument('--file', '-f', required=True, help='Config file to import')
    import_parser.add_argument('--profile', '-p', help='Profile username (optional)')
    
    # config:list command
    list_parser = subparsers.add_parser('config:list', help='List all configuration keys')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to appropriate handler
    command_map = {
        'config:get': cli.config_get,
        'config:set': cli.config_set,
        'config:show': cli.config_show,
        'config:reset': cli.config_reset,
        'config:export': cli.config_export,
        'config:import': cli.config_import,
        'config:list': cli.config_list,
    }
    
    handler = command_map.get(args.command)
    if handler:
        try:
            handler(args)
        except KeyboardInterrupt:
            print("\n\nOperation cancelled")
            sys.exit(0)
        except Exception as e:
            print(f"\nError: {e}")
            sys.exit(1)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
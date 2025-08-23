#!/usr/bin/env python3
"""Database migration runner for Instagram Scraper (Docker environment)"""

import os
import sys
import argparse
from pathlib import Path
from typing import List
import importlib.util
from .base import MigrationManager, Migration


class MigrationRunner:
    """Handles loading and running database migrations"""
    
    def __init__(self):
        # Database configuration from environment (Docker)
        self.db_config = {
            'host': os.getenv('DB_HOST', 'instagram-mariadb'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'instagram_db')
        }
        self.manager = MigrationManager(self.db_config)
        self.migrations_dir = Path(__file__).parent
    
    def load_migrations(self) -> List[Migration]:
        """Load all migration files from current directory"""
        migrations = []
        
        # Find all migration files (pattern: XXX_*.py)
        migration_files = sorted([
            f for f in self.migrations_dir.glob('[0-9][0-9][0-9]_*.py')
            if f.name != '__init__.py'
        ])
        
        # Add the migrations package to sys.modules to allow relative imports
        import ig_scraper.database.migrations
        sys.modules['ig_scraper.database.migrations.base'] = sys.modules['ig_scraper.database.migrations.base']
        
        for migration_file in migration_files:
            # Import the migration module with full package path
            module_name = f"ig_scraper.database.migrations.{migration_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, migration_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            
            # Set __package__ to allow relative imports
            module.__package__ = 'ig_scraper.database.migrations'
            
            spec.loader.exec_module(module)
            
            # Find the Migration subclass
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, Migration) and 
                    attr != Migration):
                    migrations.append(attr())
                    print(f"  📄 Loaded migration {attr().version}: {attr().description}")
                    break
        
        return migrations
    
    def run(self, command: str, **kwargs):
        """Run migration command"""
        print("\n" + "="*80)
        print("DATABASE MIGRATION TOOL")
        print("="*80)
        print(f"Database: {os.getenv('DB_NAME', 'instagram_db')}")
        print(f"Host: {self.db_config.get('host', 'instagram-mariadb')}:{self.db_config.get('port', 3306)}")
        print("="*80)
        
        print("\n📂 Loading migrations...")
        migrations = self.load_migrations()
        print(f"\n✓ Found {len(migrations)} migration(s)")
        
        if command == 'migrate':
            print("\n🔄 Running migrations...")
            target_version = kwargs.get('version')
            return self.manager.run_migrations(migrations, target_version)
            
        elif command == 'rollback':
            target_version = kwargs.get('version')
            if not target_version:
                print("❌ Rollback requires --version parameter")
                return False
            print(f"\n🔄 Rolling back to version {target_version}...")
            return self.manager.rollback_to(migrations, target_version)
            
        elif command == 'status':
            self.manager.status()
            return True
            
        elif command == 'create':
            name = kwargs.get('name')
            if not name:
                print("❌ Create requires --name parameter")
                return False
            return self.create_migration(name)
    
    def create_migration(self, name: str) -> bool:
        """Create a new migration file"""
        # Get next version number
        existing = sorted([
            f.name for f in self.migrations_dir.glob('[0-9][0-9][0-9]_*.py')
        ])
        
        if existing:
            last_version = int(existing[-1][:3])
            next_version = f"{last_version + 1:03d}"
        else:
            next_version = "001"
        
        # Clean name for filename
        clean_name = name.lower().replace(' ', '_').replace('-', '_')
        filename = f"{next_version}_{clean_name}.py"
        filepath = self.migrations_dir / filename
        
        # Generate class name
        class_name = ''.join(word.capitalize() for word in clean_name.split('_'))
        
        # Migration template
        template = f'''"""Migration: {name}"""

from .base import Migration


class {class_name}(Migration):
    """{name}"""
    
    def get_version(self) -> str:
        return "{next_version}"
    
    def get_description(self) -> str:
        return "{name}"
    
    def up(self, cursor) -> None:
        """Apply migration"""
        # TODO: Add migration logic here
        pass
    
    def down(self, cursor) -> None:
        """Rollback migration"""
        # TODO: Add rollback logic here
        pass
'''
        
        # Write file
        with open(filepath, 'w') as f:
            f.write(template)
        
        print(f"✅ Created migration: {filename}")
        return True


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description='Database Migration Tool')
    parser.add_argument('command', 
                       choices=['migrate', 'rollback', 'status', 'create'],
                       help='Command to execute')
    parser.add_argument('--version', help='Target version for rollback')
    parser.add_argument('--name', help='Name for new migration')
    parser.add_argument('--force', action='store_true', 
                       help='Force migration even if checks fail')
    
    args = parser.parse_args()
    
    runner = MigrationRunner()
    success = runner.run(
        args.command,
        version=args.version,
        name=args.name,
        force=args.force
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
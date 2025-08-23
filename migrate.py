#!/usr/bin/env python3
"""Database migration runner"""

import os
import sys
import argparse
from pathlib import Path
from typing import List
import importlib.util
from dotenv import load_dotenv

# Load environment variables
env_path = Path('.env')
if env_path.exists():
    load_dotenv()

# Detect if running in Docker
IS_DOCKER = os.getenv('IS_DOCKER', 'false').lower() == 'true'

# Add migrations directory to path
sys.path.insert(0, str(Path(__file__).parent / 'migrations'))

from migration import MigrationManager, Migration

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'instagram_scraper')
}


def load_migrations() -> List[Migration]:
    """Load all migration files from migrations directory"""
    migrations = []
    migrations_dir = Path(__file__).parent / 'migrations'
    
    # Find all migration files (pattern: XXX_*.py)
    migration_files = sorted([
        f for f in migrations_dir.glob('[0-9][0-9][0-9]_*.py')
    ])
    
    for migration_file in migration_files:
        # Import the migration module
        module_name = migration_file.stem
        spec = importlib.util.spec_from_file_location(module_name, migration_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find the Migration class in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, Migration) and 
                attr != Migration):
                # Create instance of the migration
                migration = attr()
                migrations.append(migration)
                print(f"  📄 Loaded migration {migration.version}: {migration.description}")
                break
    
    return migrations


def main():
    """Main migration runner"""
    parser = argparse.ArgumentParser(description='Database Migration Tool')
    parser.add_argument('command', choices=['migrate', 'rollback', 'status', 'create'],
                       help='Migration command to run')
    parser.add_argument('--version', '-v', help='Target migration version')
    parser.add_argument('--name', '-n', help='Name for new migration (with create command)')
    parser.add_argument('--force', '-f', action='store_true', 
                       help='Force migration even if checksums don\'t match')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("DATABASE MIGRATION TOOL")
    print("="*80)
    print(f"Database: {DB_CONFIG['database']}")
    print(f"Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print("="*80)
    
    if args.command == 'create':
        # Create new migration file
        if not args.name:
            print("❌ Please provide a name for the migration with --name")
            sys.exit(1)
        
        create_migration(args.name)
        return
    
    # Load migrations
    print("\n📂 Loading migrations...")
    migrations = load_migrations()
    
    if not migrations:
        print("⚠️  No migrations found in migrations directory")
        sys.exit(1)
    
    print(f"\n✓ Found {len(migrations)} migration(s)")
    
    # Create migration manager
    manager = MigrationManager(DB_CONFIG.copy())
    
    try:
        if args.command == 'migrate':
            # Run migrations
            print("\n🔄 Running migrations...")
            success = manager.run_migrations(migrations, args.version)
            sys.exit(0 if success else 1)
            
        elif args.command == 'rollback':
            # Rollback migrations
            if not args.version:
                print("❌ Please specify target version with --version")
                sys.exit(1)
            
            print(f"\n🔄 Rolling back to version {args.version}...")
            success = manager.rollback_to(migrations, args.version)
            sys.exit(0 if success else 1)
            
        elif args.command == 'status':
            # Show migration status
            manager.status()
            
            # Show pending migrations
            if manager.connect() and manager.create_migrations_table():
                pending = manager.get_pending_migrations(migrations)
                if pending:
                    print(f"\n⏳ PENDING MIGRATIONS ({len(pending)}):")
                    for migration in pending:
                        print(f"  ⏸  {migration.version}: {migration.description}")
                else:
                    print("\n✅ All migrations have been applied")
            
    finally:
        manager.close()


def create_migration(name: str):
    """Create a new migration file"""
    migrations_dir = Path(__file__).parent / 'migrations'
    
    # Find next version number
    existing = sorted([f for f in migrations_dir.glob('[0-9][0-9][0-9]_*.py')])
    if existing:
        last_version = int(existing[-1].stem[:3])
        next_version = f"{last_version + 1:03d}"
    else:
        next_version = "001"
    
    # Create filename
    safe_name = name.lower().replace(' ', '_').replace('-', '_')
    filename = f"{next_version}_{safe_name}.py"
    filepath = migrations_dir / filename
    
    # Create migration template
    class_name = ''.join(word.capitalize() for word in safe_name.split('_'))
    
    template = f'''"""Migration: {name}"""

from migration import Migration


class {class_name}(Migration):
    """{name}"""
    
    def get_version(self) -> str:
        return "{next_version}"
    
    def get_description(self) -> str:
        return "{name}"
    
    def up(self, cursor) -> None:
        """Apply migration"""
        # TODO: Add your migration SQL here
        # Example:
        # cursor.execute("""
        #     ALTER TABLE table_name 
        #     ADD COLUMN column_name VARCHAR(255)
        # """)
        pass
    
    def down(self, cursor) -> None:
        """Rollback migration"""
        # TODO: Add your rollback SQL here
        # Example:
        # cursor.execute("""
        #     ALTER TABLE table_name 
        #     DROP COLUMN column_name
        # """)
        pass
'''
    
    # Write file
    filepath.write_text(template)
    print(f"\n✅ Created migration: {filepath}")
    print(f"   Version: {next_version}")
    print(f"   Class: {class_name}")
    print("\n📝 Edit the migration file to add your SQL commands")


if __name__ == "__main__":
    main()
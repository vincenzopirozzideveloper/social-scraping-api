"""Base migration class and utilities"""

import os
import sys
import pymysql
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from abc import ABC, abstractmethod
import hashlib


class Migration(ABC):
    """Base class for all migrations"""
    
    def __init__(self):
        self.version = self.get_version()
        self.description = self.get_description()
        self.checksum = None
    
    @abstractmethod
    def get_version(self) -> str:
        """Return migration version (e.g., '001', '002')"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Return migration description"""
        pass
    
    @abstractmethod
    def up(self, cursor) -> None:
        """Apply migration"""
        pass
    
    @abstractmethod
    def down(self, cursor) -> None:
        """Rollback migration"""
        pass
    
    def get_checksum(self) -> str:
        """Calculate checksum for migration"""
        if not self.checksum:
            content = f"{self.version}{self.description}{self.up.__code__.co_code}"
            self.checksum = hashlib.md5(content.encode()).hexdigest()
        return self.checksum


class MigrationManager:
    """Manages database migrations"""
    
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.db_name = db_config.pop('database', 'instagram_scraper')
        self.connection = None
        self.migrations_table = 'schema_migrations'
    
    def connect(self):
        """Connect to database"""
        try:
            # Connect without database first
            self.connection = pymysql.connect(**self.db_config)
            
            # Create database if not exists
            with self.connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                cursor.execute(f"USE `{self.db_name}`")
            
            self.connection.commit()
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    def create_migrations_table(self):
        """Create migrations tracking table"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        version VARCHAR(20) UNIQUE NOT NULL,
                        description VARCHAR(255),
                        checksum VARCHAR(32),
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        execution_time_ms INT,
                        INDEX idx_version (version)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                self.connection.commit()
                return True
        except Exception as e:
            print(f"❌ Failed to create migrations table: {e}")
            return False
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SELECT version FROM {self.migrations_table} ORDER BY version")
                return [row[0] for row in cursor.fetchall()]
        except:
            return []
    
    def is_migration_applied(self, version: str) -> bool:
        """Check if a migration has been applied"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SELECT 1 FROM {self.migrations_table} WHERE version = %s", (version,))
                return cursor.fetchone() is not None
        except:
            return False
    
    def apply_migration(self, migration: Migration) -> bool:
        """Apply a single migration"""
        if self.is_migration_applied(migration.version):
            print(f"  ⏩ Migration {migration.version} already applied")
            return True
        
        print(f"\n📋 Applying migration {migration.version}: {migration.description}")
        start_time = datetime.now()
        
        try:
            with self.connection.cursor() as cursor:
                # Apply the migration
                migration.up(cursor)
                
                # Record in migrations table
                execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                cursor.execute(f"""
                    INSERT INTO {self.migrations_table} 
                    (version, description, checksum, execution_time_ms)
                    VALUES (%s, %s, %s, %s)
                """, (migration.version, migration.description, migration.get_checksum(), execution_time_ms))
            
            self.connection.commit()
            print(f"  ✅ Migration {migration.version} applied successfully ({execution_time_ms}ms)")
            return True
            
        except Exception as e:
            self.connection.rollback()
            print(f"  ❌ Migration {migration.version} failed: {e}")
            return False
    
    def rollback_migration(self, migration: Migration) -> bool:
        """Rollback a single migration"""
        if not self.is_migration_applied(migration.version):
            print(f"  ⏩ Migration {migration.version} not applied")
            return True
        
        print(f"\n📋 Rolling back migration {migration.version}: {migration.description}")
        
        try:
            with self.connection.cursor() as cursor:
                # Rollback the migration
                migration.down(cursor)
                
                # Remove from migrations table
                cursor.execute(f"DELETE FROM {self.migrations_table} WHERE version = %s", (migration.version,))
            
            self.connection.commit()
            print(f"  ✅ Migration {migration.version} rolled back successfully")
            return True
            
        except Exception as e:
            self.connection.rollback()
            print(f"  ❌ Rollback of {migration.version} failed: {e}")
            return False
    
    def get_pending_migrations(self, migrations: List[Migration]) -> List[Migration]:
        """Get list of migrations that haven't been applied yet"""
        applied = self.get_applied_migrations()
        return [m for m in migrations if m.version not in applied]
    
    def run_migrations(self, migrations: List[Migration], target_version: Optional[str] = None) -> bool:
        """Run all pending migrations up to target version"""
        if not self.connect():
            return False
        
        if not self.create_migrations_table():
            return False
        
        # Sort migrations by version
        migrations.sort(key=lambda m: m.version)
        
        # Get pending migrations
        pending = self.get_pending_migrations(migrations)
        
        if not pending:
            print("✅ Database is up to date!")
            return True
        
        print(f"\n🔄 Found {len(pending)} pending migration(s)")
        
        success_count = 0
        for migration in pending:
            if target_version and migration.version > target_version:
                break
            
            if self.apply_migration(migration):
                success_count += 1
            else:
                print(f"\n⚠️  Migration failed. {success_count} migrations were applied successfully.")
                return False
        
        print(f"\n✅ All migrations applied successfully! ({success_count} migrations)")
        return True
    
    def rollback_to(self, migrations: List[Migration], target_version: str) -> bool:
        """Rollback migrations to a specific version"""
        if not self.connect():
            return False
        
        # Sort migrations by version (descending for rollback)
        migrations.sort(key=lambda m: m.version, reverse=True)
        
        applied = self.get_applied_migrations()
        
        rollback_count = 0
        for migration in migrations:
            if migration.version <= target_version:
                break
            
            if migration.version in applied:
                if self.rollback_migration(migration):
                    rollback_count += 1
                else:
                    print(f"\n⚠️  Rollback failed. {rollback_count} migrations were rolled back.")
                    return False
        
        print(f"\n✅ Rolled back {rollback_count} migration(s) successfully!")
        return True
    
    def status(self) -> None:
        """Show migration status"""
        if not self.connect():
            return
        
        if not self.create_migrations_table():
            return
        
        try:
            with self.connection.cursor() as cursor:
                # Get applied migrations
                cursor.execute(f"""
                    SELECT version, description, applied_at, execution_time_ms
                    FROM {self.migrations_table}
                    ORDER BY version
                """)
                applied = cursor.fetchall()
                
                print("\n" + "="*80)
                print("MIGRATION STATUS")
                print("="*80)
                print(f"Database: {self.db_name}")
                print(f"Applied migrations: {len(applied)}")
                print("="*80)
                
                if applied:
                    print("\nAPPLIED MIGRATIONS:")
                    for version, desc, applied_at, exec_time in applied:
                        print(f"  ✅ {version}: {desc}")
                        print(f"     Applied: {applied_at} ({exec_time}ms)")
                else:
                    print("\n⚠️  No migrations have been applied yet")
                
                print("="*80)
                
        except Exception as e:
            print(f"❌ Error getting status: {e}")
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
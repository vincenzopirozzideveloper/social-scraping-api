"""Fix all missing columns in the database"""

from migration import Migration


class FixAllMissingColumns(Migration):
    """Comprehensive fix for all missing columns based on application errors"""
    
    def get_version(self) -> str:
        return "004"
    
    def get_description(self) -> str:
        return "Fix all missing columns and table issues"
    
    def up(self, cursor) -> None:
        """Add all missing columns and fix table structures"""
        
        print("  → Checking and fixing automation_sessions table...")
        
        # 1. Fix automation_sessions - add session_type if missing
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'automation_sessions' 
            AND COLUMN_NAME = 'session_type'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE automation_sessions 
                ADD COLUMN session_type VARCHAR(50) NOT NULL DEFAULT 'explore_automation' AFTER profile_id
            """)
            print("  ✓ Added session_type column to automation_sessions")
            
            # Add index for session_type
            cursor.execute("""
                CREATE INDEX idx_session_type ON automation_sessions(session_type)
            """)
            print("  ✓ Added index for session_type")
        else:
            print("  ⏩ session_type already exists in automation_sessions")
        
        # 2. Ensure search_query column exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'automation_sessions' 
            AND COLUMN_NAME = 'search_query'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE automation_sessions 
                ADD COLUMN search_query VARCHAR(255) AFTER session_type
            """)
            print("  ✓ Added search_query column to automation_sessions")
        else:
            print("  ⏩ search_query already exists in automation_sessions")
        
        # 3. Ensure all statistics columns exist
        statistics_columns = [
            ('total_processed', 'INT DEFAULT 0'),
            ('successful', 'INT DEFAULT 0'),
            ('failed', 'INT DEFAULT 0'),
            ('posts_processed', 'INT DEFAULT 0'),
            ('likes_count', 'INT DEFAULT 0'),
            ('comments_count', 'INT DEFAULT 0'),
            ('errors_count', 'INT DEFAULT 0')
        ]
        
        for column_name, column_def in statistics_columns:
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'automation_sessions' 
                AND COLUMN_NAME = '{column_name}'
                AND TABLE_SCHEMA = DATABASE()
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute(f"""
                    ALTER TABLE automation_sessions 
                    ADD COLUMN {column_name} {column_def}
                """)
                print(f"  ✓ Added {column_name} column to automation_sessions")
        
        # 4. Ensure metadata column exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'automation_sessions' 
            AND COLUMN_NAME = 'metadata'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE automation_sessions 
                ADD COLUMN metadata JSON
            """)
            print("  ✓ Added metadata column to automation_sessions")
        else:
            print("  ⏩ metadata already exists in automation_sessions")
        
        # 5. Ensure status column exists with proper ENUM
        cursor.execute("""
            SELECT COLUMN_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'automation_sessions' 
            AND COLUMN_NAME = 'status'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        result = cursor.fetchone()
        if not result:
            cursor.execute("""
                ALTER TABLE automation_sessions 
                ADD COLUMN status ENUM('running', 'completed', 'error', 'stopped') DEFAULT 'running'
            """)
            print("  ✓ Added status column to automation_sessions")
        else:
            # Check if ENUM has all required values
            current_type = result[0]
            if 'stopped' not in current_type:
                cursor.execute("""
                    ALTER TABLE automation_sessions 
                    MODIFY COLUMN status ENUM('running', 'completed', 'error', 'stopped') DEFAULT 'running'
                """)
                print("  ✓ Updated status ENUM values")
            else:
                print("  ⏩ status column already correct")
        
        # 6. Ensure timestamps exist
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'automation_sessions' 
            AND COLUMN_NAME = 'started_at'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE automation_sessions 
                ADD COLUMN started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
            print("  ✓ Added started_at column to automation_sessions")
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'automation_sessions' 
            AND COLUMN_NAME = 'ended_at'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE automation_sessions 
                ADD COLUMN ended_at TIMESTAMP NULL
            """)
            print("  ✓ Added ended_at column to automation_sessions")
        
        print("\n  → Checking action_logs table...")
        
        # 7. Ensure action_logs has all required columns
        action_logs_columns = [
            ('profile_id', 'INT NOT NULL'),
            ('session_id', 'INT'),
            ('action_type', 'VARCHAR(50) NOT NULL'),
            ('target_id', 'VARCHAR(100)'),
            ('target_username', 'VARCHAR(100)'),
            ('success', 'BOOLEAN DEFAULT TRUE'),
            ('error_message', 'TEXT'),
            ('response_data', 'JSON'),
            ('metadata', 'JSON')
        ]
        
        for column_name, column_def in action_logs_columns:
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'action_logs' 
                AND COLUMN_NAME = '{column_name}'
                AND TABLE_SCHEMA = DATABASE()
            """)
            
            if cursor.fetchone()[0] == 0:
                # Special handling for profile_id to avoid foreign key issues
                if column_name == 'profile_id':
                    # First add as nullable
                    cursor.execute(f"""
                        ALTER TABLE action_logs 
                        ADD COLUMN {column_name} INT AFTER id
                    """)
                    
                    # Try to populate from sessions
                    cursor.execute("""
                        UPDATE action_logs al
                        JOIN automation_sessions s ON al.session_id = s.id
                        SET al.profile_id = s.profile_id
                        WHERE al.profile_id IS NULL
                    """)
                    
                    # Set a default for remaining nulls
                    cursor.execute("SELECT id FROM profiles LIMIT 1")
                    default_profile = cursor.fetchone()
                    if default_profile:
                        cursor.execute("""
                            UPDATE action_logs 
                            SET profile_id = %s
                            WHERE profile_id IS NULL
                        """, (default_profile[0],))
                    else:
                        # Delete orphans if no profiles exist
                        cursor.execute("DELETE FROM action_logs WHERE profile_id IS NULL")
                    
                    # Now make it NOT NULL
                    cursor.execute("""
                        ALTER TABLE action_logs 
                        MODIFY COLUMN profile_id INT NOT NULL
                    """)
                    
                    # Add foreign key
                    cursor.execute("""
                        ALTER TABLE action_logs 
                        ADD CONSTRAINT fk_action_logs_profile_v2
                        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                    """)
                else:
                    cursor.execute(f"""
                        ALTER TABLE action_logs 
                        ADD COLUMN {column_name} {column_def}
                    """)
                
                print(f"  ✓ Added {column_name} column to action_logs")
        
        # 8. Add missing indexes
        print("\n  → Adding missing indexes...")
        
        # Check and add indexes
        indexes_to_add = [
            ('automation_sessions', 'idx_profile_sessions', 'profile_id'),
            ('automation_sessions', 'idx_started_at', 'started_at'),
            ('automation_sessions', 'idx_status', 'status'),
            ('action_logs', 'idx_profile_actions', 'profile_id'),
            ('action_logs', 'idx_session_actions', 'session_id'),
            ('action_logs', 'idx_action_type', 'action_type'),
            ('action_logs', 'idx_created_at', 'created_at')
        ]
        
        for table_name, index_name, column_name in indexes_to_add:
            cursor.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_NAME = %s
                AND INDEX_NAME = %s
                AND TABLE_SCHEMA = DATABASE()
            """, (table_name, index_name))
            
            if cursor.fetchone()[0] == 0:
                cursor.execute(f"""
                    CREATE INDEX {index_name} ON {table_name}({column_name})
                """)
                print(f"  ✓ Added index {index_name} on {table_name}.{column_name}")
        
        # 9. Create following_fetches and following_data tables if they don't exist
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'following_fetches'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE following_fetches (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    profile_id INT NOT NULL,
                    fetch_type VARCHAR(50) NOT NULL,
                    total_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                    INDEX idx_profile_fetches (profile_id),
                    INDEX idx_fetch_type (fetch_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            print("  ✓ Created following_fetches table")
        
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'following_data'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE TABLE following_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fetch_id INT NOT NULL,
                    user_id VARCHAR(50) NOT NULL,
                    username VARCHAR(50) NOT NULL,
                    full_name VARCHAR(255),
                    is_private BOOLEAN DEFAULT FALSE,
                    is_verified BOOLEAN DEFAULT FALSE,
                    profile_pic_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (fetch_id) REFERENCES following_fetches(id) ON DELETE CASCADE,
                    INDEX idx_fetch_id (fetch_id),
                    INDEX idx_username (username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            print("  ✓ Created following_data table")
        
        print("\n  ✅ All missing columns and tables have been added/fixed")
    
    def down(self, cursor) -> None:
        """Rollback changes - be careful with this"""
        
        # Drop added indexes
        indexes_to_drop = [
            ('automation_sessions', 'idx_session_type'),
            ('action_logs', 'fk_action_logs_profile_v2')
        ]
        
        for table_name, index_name in indexes_to_drop:
            try:
                if 'fk_' in index_name:
                    cursor.execute(f"ALTER TABLE {table_name} DROP FOREIGN KEY {index_name}")
                else:
                    cursor.execute(f"ALTER TABLE {table_name} DROP INDEX {index_name}")
                print(f"  ✓ Dropped {index_name} from {table_name}")
            except:
                pass
        
        # Note: We don't drop columns as they might contain data
        print("  ⚠ Column removal skipped to preserve data")
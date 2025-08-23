"""Add missing columns to existing tables"""

from migration import Migration


class AddMissingColumns(Migration):
    """Add profile_id to action_logs and other missing columns"""
    
    def get_version(self) -> str:
        return "002"
    
    def get_description(self) -> str:
        return "Add missing columns to action_logs and other tables"
    
    def up(self, cursor) -> None:
        """Add missing columns"""
        
        # Check if profile_id exists in action_logs
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'action_logs' 
            AND COLUMN_NAME = 'profile_id'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] == 0:
            # Add profile_id column to action_logs (nullable first)
            cursor.execute("""
                ALTER TABLE action_logs 
                ADD COLUMN profile_id INT AFTER id
            """)
            print("  ✓ Added profile_id column to action_logs")
            
            # Try to populate profile_id from session_id
            cursor.execute("""
                UPDATE action_logs al
                JOIN automation_sessions s ON al.session_id = s.id
                SET al.profile_id = s.profile_id
                WHERE al.profile_id IS NULL AND al.session_id IS NOT NULL
            """)
            rows_updated = cursor.rowcount
            print(f"  ✓ Populated profile_id for {rows_updated} rows from existing sessions")
            
            # For rows without session_id, try to find a default profile
            cursor.execute("SELECT id FROM profiles LIMIT 1")
            default_profile = cursor.fetchone()
            
            if default_profile:
                cursor.execute("""
                    UPDATE action_logs 
                    SET profile_id = %s
                    WHERE profile_id IS NULL
                """, (default_profile[0],))
                orphan_rows = cursor.rowcount
                if orphan_rows > 0:
                    print(f"  ⚠ Set default profile_id for {orphan_rows} orphan rows")
            else:
                # If no profiles exist, delete orphan action_logs
                cursor.execute("""
                    DELETE FROM action_logs 
                    WHERE profile_id IS NULL
                """)
                deleted_rows = cursor.rowcount
                if deleted_rows > 0:
                    print(f"  ⚠ Deleted {deleted_rows} orphan action_logs (no profiles exist)")
            
            # Now make profile_id NOT NULL
            cursor.execute("""
                ALTER TABLE action_logs 
                MODIFY COLUMN profile_id INT NOT NULL
            """)
            print("  ✓ Made profile_id NOT NULL")
            
            # Add foreign key constraint
            cursor.execute("""
                ALTER TABLE action_logs 
                ADD CONSTRAINT fk_action_logs_profile
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            """)
            print("  ✓ Added foreign key constraint for profile_id")
            
            # Add index for profile_id
            cursor.execute("""
                CREATE INDEX idx_action_logs_profile ON action_logs(profile_id)
            """)
            print("  ✓ Added index for profile_id")
        else:
            print("  ⏩ profile_id column already exists in action_logs")
        
        # Check and add metadata column to action_logs if missing
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'action_logs' 
            AND COLUMN_NAME = 'metadata'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE action_logs 
                ADD COLUMN metadata JSON AFTER response_data
            """)
            print("  ✓ Added metadata column to action_logs")
        else:
            print("  ⏩ metadata column already exists in action_logs")
    
    def down(self, cursor) -> None:
        """Remove added columns"""
        
        # Check if foreign key exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_NAME = 'action_logs'
            AND CONSTRAINT_NAME = 'fk_action_logs_profile'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] > 0:
            cursor.execute("""
                ALTER TABLE action_logs 
                DROP FOREIGN KEY fk_action_logs_profile
            """)
            print("  ✓ Dropped foreign key constraint")
        
        # Check if index exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_NAME = 'action_logs'
            AND INDEX_NAME = 'idx_action_logs_profile'
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        if cursor.fetchone()[0] > 0:
            cursor.execute("""
                ALTER TABLE action_logs 
                DROP INDEX idx_action_logs_profile
            """)
            print("  ✓ Dropped profile_id index")
        
        # Check if columns exist before dropping
        cursor.execute("""
            SELECT GROUP_CONCAT(COLUMN_NAME)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'action_logs'
            AND COLUMN_NAME IN ('profile_id', 'metadata')
            AND TABLE_SCHEMA = DATABASE()
        """)
        
        result = cursor.fetchone()[0]
        if result:
            columns_to_drop = result.split(',')
            for column in columns_to_drop:
                cursor.execute(f"ALTER TABLE action_logs DROP COLUMN {column}")
                print(f"  ✓ Dropped {column} column from action_logs")
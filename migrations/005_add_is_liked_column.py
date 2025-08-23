"""Add is_liked column to posts_processed table"""

from migration import Migration


class AddIsLikedColumn(Migration):
    """Add is_liked column that was missing from posts_processed table"""
    
    def get_version(self) -> str:
        return "005"
    
    def get_description(self) -> str:
        return "Add missing columns to posts_processed table"
    
    def up(self, cursor) -> None:
        """Add the missing columns"""
        columns_to_add = [
            ('caption', 'TEXT', 'AFTER owner_username'),
            ('like_count', 'INT DEFAULT 0', 'AFTER caption'),
            ('comment_count', 'INT DEFAULT 0', 'AFTER like_count'),
            ('is_liked', 'BOOLEAN DEFAULT FALSE', 'AFTER comment_count'),
            ('is_commented', 'BOOLEAN DEFAULT FALSE', 'AFTER is_liked')
        ]
        
        for col_name, col_type, position in columns_to_add:
            # Check if column exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = DATABASE()
                AND table_name = 'posts_processed' 
                AND column_name = %s
            """, (col_name,))
            
            if cursor.fetchone()[0] == 0:
                print(f"    → Adding {col_name} column to posts_processed...")
                # For the first column, we can't use AFTER if the referenced column doesn't exist
                if col_name == 'caption':
                    # Add after owner_username or at the end if that doesn't exist
                    try:
                        cursor.execute(f"""
                            ALTER TABLE posts_processed 
                            ADD COLUMN {col_name} {col_type} {position}
                        """)
                    except:
                        # If owner_username doesn't exist, add without position
                        cursor.execute(f"""
                            ALTER TABLE posts_processed 
                            ADD COLUMN {col_name} {col_type}
                        """)
                else:
                    # For other columns, add without position if previous column doesn't exist
                    try:
                        cursor.execute(f"""
                            ALTER TABLE posts_processed 
                            ADD COLUMN {col_name} {col_type}
                        """)
                    except Exception as e:
                        print(f"    ⚠ Error adding {col_name}: {e}")
                print(f"    ✓ {col_name} column added")
            else:
                print(f"    → Column {col_name} already exists, skipping...")
        
    
    def down(self, cursor) -> None:
        """Remove the columns"""
        # Remove is_liked if exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE()
            AND table_name = 'posts_processed' 
            AND column_name = 'is_liked'
        """)
        if cursor.fetchone()[0] > 0:
            cursor.execute("""
                ALTER TABLE posts_processed 
                DROP COLUMN is_liked
            """)
            print("    ✓ is_liked column removed")
        
        # Remove comment_count if it was added by this migration
        # (we keep it if it already existed)
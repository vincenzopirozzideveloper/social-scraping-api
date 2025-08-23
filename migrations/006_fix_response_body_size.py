"""Fix response_body column size for large API responses"""

from migration import Migration


class FixResponseBodySize(Migration):
    """Change response_body to LONGTEXT to handle large Instagram API responses"""
    
    def get_version(self) -> str:
        return "006"
    
    def get_description(self) -> str:
        return "Change response_body to LONGTEXT for large API responses"
    
    def up(self, cursor) -> None:
        """Change column type to LONGTEXT"""
        print("    → Changing response_body column to LONGTEXT in api_requests...")
        cursor.execute("""
            ALTER TABLE api_requests 
            MODIFY COLUMN response_body LONGTEXT
        """)
        print("    ✓ Column type changed to LONGTEXT (can store up to 4GB)")
        
        # Also update params column to JSON type if not already
        print("    → Updating params column to JSON type...")
        cursor.execute("""
            ALTER TABLE api_requests 
            MODIFY COLUMN params JSON
        """)
        print("    ✓ Params column updated to JSON")
        
        # Update headers column to JSON type
        print("    → Updating headers column to JSON type...")
        cursor.execute("""
            ALTER TABLE api_requests 
            MODIFY COLUMN headers JSON
        """)
        print("    ✓ Headers column updated to JSON")
    
    def down(self, cursor) -> None:
        """Revert to TEXT (may cause data loss)"""
        print("    → Reverting response_body to TEXT...")
        cursor.execute("""
            ALTER TABLE api_requests 
            MODIFY COLUMN response_body TEXT
        """)
        print("    ✓ Reverted to TEXT (warning: may have truncated data)")
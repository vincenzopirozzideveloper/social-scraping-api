"""Add tables for detailed request/response tracking"""

from .base import Migration


class AddRequestTracking(Migration):
    """Add comprehensive request tracking tables"""
    
    def get_version(self) -> str:
        return "003"
    
    def get_description(self) -> str:
        return "Add request/response tracking tables"
    
    def up(self, cursor) -> None:
        """Create request tracking tables"""
        
        # API requests table for detailed tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT NOT NULL,
                session_id INT,
                request_type VARCHAR(50) NOT NULL,
                endpoint VARCHAR(255) NOT NULL,
                method VARCHAR(10) DEFAULT 'POST',
                headers JSON,
                params JSON,
                body TEXT,
                response_status INT,
                response_headers JSON,
                response_body TEXT,
                response_time_ms INT,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES automation_sessions(id) ON DELETE SET NULL,
                INDEX idx_profile_requests (profile_id),
                INDEX idx_session_requests (session_id),
                INDEX idx_endpoint (endpoint),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✓ Created api_requests table")
        
        # Rate limiting tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_id INT NOT NULL,
                endpoint VARCHAR(255) NOT NULL,
                limit_type VARCHAR(50),
                requests_made INT DEFAULT 0,
                limit_reached_at TIMESTAMP NULL,
                reset_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                UNIQUE KEY unique_rate_limit (profile_id, endpoint),
                INDEX idx_profile_limits (profile_id),
                INDEX idx_reset_at (reset_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✓ Created rate_limits table")
        
        # Session metrics for performance tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_metrics (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id INT NOT NULL,
                metric_name VARCHAR(100) NOT NULL,
                metric_value DECIMAL(10,2),
                metric_unit VARCHAR(20),
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES automation_sessions(id) ON DELETE CASCADE,
                INDEX idx_session_metrics (session_id),
                INDEX idx_metric_name (metric_name),
                INDEX idx_recorded_at (recorded_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("  ✓ Created session_metrics table")
    
    def down(self, cursor) -> None:
        """Drop request tracking tables"""
        tables = ['session_metrics', 'rate_limits', 'api_requests']
        
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"  ✓ Dropped {table} table")
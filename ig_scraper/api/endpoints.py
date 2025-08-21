"""Instagram API endpoints configuration"""

class Endpoints:
    """Instagram API endpoints"""
    
    BASE_URL = "https://www.instagram.com"
    
    # Authentication
    LOGIN_PAGE = f"{BASE_URL}/accounts/login/"
    LOGIN_AJAX = "**/api/v1/web/accounts/login/ajax/"
    
    # GraphQL endpoints
    GRAPHQL_QUERY = f"{BASE_URL}/graphql/query"
    GRAPHQL_PATTERN = "**/graphql/query"
    API_GRAPHQL_PATTERN = "**/api/graphql"
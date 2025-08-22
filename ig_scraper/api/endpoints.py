"""Instagram API endpoints configuration"""

class Endpoints:
    """Instagram API endpoints"""
    
    BASE_URL = "https://www.instagram.com"
    
    # Authentication
    LOGIN_PAGE = f"{BASE_URL}/accounts/login/"
    LOGIN_AJAX = "**/api/v1/web/accounts/login/ajax/"
    TWO_FACTOR_PATTERN = "**/accounts/login/ajax/two_factor/**"
    
    # GraphQL endpoints
    GRAPHQL_QUERY = f"{BASE_URL}/graphql/query"
    GRAPHQL_PATTERN = "**/graphql/query"
    API_GRAPHQL_PATTERN = "**/api/graphql"
    
    # User relationships
    FRIENDSHIPS_FOLLOWING = f"{BASE_URL}/api/v1/friendships/{{user_id}}/following/"
    FRIENDSHIPS_FOLLOWERS = f"{BASE_URL}/api/v1/friendships/{{user_id}}/followers/"
    FRIENDSHIPS_CREATE = f"{BASE_URL}/api/v1/friendships/create/{{user_id}}/"
    FRIENDSHIPS_DESTROY = f"{BASE_URL}/api/v1/friendships/destroy/{{user_id}}/"
    
    # Search and explore
    EXPLORE_SEARCH = f"{BASE_URL}/api/v1/fbsearch/web/top_serp/"
    
    # Media actions
    MEDIA_LIKE = f"{BASE_URL}/api/v1/web/likes/{{media_id}}/like/"
    MEDIA_UNLIKE = f"{BASE_URL}/api/v1/web/likes/{{media_id}}/unlike/"
    MEDIA_COMMENT = f"{BASE_URL}/api/v1/web/comments/{{media_id}}/add/"
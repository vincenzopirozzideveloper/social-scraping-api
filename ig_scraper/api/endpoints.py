"""Instagram API endpoints configuration"""

class Endpoints:
    """Instagram API endpoints"""
    
    BASE_URL = "https://www.instagram.com"
    
    # Authentication
    LOGIN_PAGE = f"{BASE_URL}/accounts/login/"
    LOGIN_AJAX = "**/api/v1/web/accounts/login/ajax/"
    TWO_FACTOR = "**/api/v1/web/accounts/two_factor/"
    
    # User endpoints
    USER_PROFILE = "**/api/v1/users/web_profile_info/"
    USER_FEED = "**/api/v1/feed/user/"
    
    # Media endpoints
    MEDIA_INFO = "**/api/v1/media/*/info/"
    MEDIA_LIKES = "**/api/v1/media/*/likers/"
    MEDIA_COMMENTS = "**/api/v1/media/*/comments/"
    
    # GraphQL endpoints
    GRAPHQL = "**/graphql/query/"
    
    # Stories
    STORIES = "**/api/v1/feed/reels_tray/"
    STORY_VIEWERS = "**/api/v1/media/*/list_reel_media_viewer/"
    
    # Search
    SEARCH = "**/api/v1/web/search/topsearch/"
    
    # Following/Followers
    FOLLOWERS = "**/api/v1/friendships/*/followers/"
    FOLLOWING = "**/api/v1/friendships/*/following/"
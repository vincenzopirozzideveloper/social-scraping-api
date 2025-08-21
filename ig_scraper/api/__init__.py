"""API module for Instagram endpoints"""

from .endpoints import Endpoints
from .graphql import GraphQLClient
from .interceptor import GraphQLInterceptor

__all__ = ['Endpoints', 'GraphQLClient', 'GraphQLInterceptor']
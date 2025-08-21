"""API module for Instagram endpoints"""

from .endpoints import Endpoints
from .graphql import GraphQLClient

__all__ = ['Endpoints', 'GraphQLClient']
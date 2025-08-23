#!/usr/bin/env python3
"""Migration CLI - Wrapper for database migrations"""

import sys
from ig_scraper.database.migrations.runner import main

if __name__ == '__main__':
    main()
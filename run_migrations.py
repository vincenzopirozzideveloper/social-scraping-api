#!/usr/bin/env python3
"""Run database migrations"""

from ig_scraper.database.migrations.runner import MigrationRunner

if __name__ == "__main__":
    runner = MigrationRunner()
    runner.run('migrate')
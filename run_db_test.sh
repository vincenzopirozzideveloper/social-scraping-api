#!/bin/bash

echo "🔧 MariaDB Connection Test"
echo "=========================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo ""
    echo "Creating .env from template..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  Please edit .env with your database credentials:"
    echo "   nano .env"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Run the test
python test_db_connection.py
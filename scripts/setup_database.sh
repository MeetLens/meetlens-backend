#!/bin/bash

# MeetLens Database Setup Script
# This script sets up the PostgreSQL databases for MeetLens

set -e  # Exit on error

echo "🚀 MeetLens Database Setup"
echo "=========================="
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed."
    echo "Install it with:"
    echo "  macOS:   brew install postgresql@15"
    echo "  Ubuntu:  sudo apt-get install postgresql postgresql-contrib"
    exit 1
fi

echo "✅ PostgreSQL is installed"

# Check if PostgreSQL is running
if ! pg_isready &> /dev/null; then
    echo "❌ PostgreSQL is not running."
    echo "Start it with:"
    echo "  macOS:   brew services start postgresql@15"
    echo "  Ubuntu:  sudo systemctl start postgresql"
    exit 1
fi

echo "✅ PostgreSQL is running"
echo ""

# Database names
DB_NAME="meetlens"
TEST_DB_NAME="meetlens_test"

# Detect a usable PostgreSQL role/user (macOS/Homebrew often doesn't create a 'postgres' role)
detect_db_user() {
    # If the user explicitly set DB_USER, trust it.
    if [ -n "$DB_USER" ]; then
        echo "$DB_USER"
        return 0
    fi

    # Prefer 'postgres' if it exists/works
    if psql -U postgres -d postgres -c '\q' &> /dev/null; then
        echo "postgres"
        return 0
    fi

    # Fall back to current OS user (common on macOS/Homebrew)
    if [ -n "$USER" ] && psql -U "$USER" -d postgres -c '\q' &> /dev/null; then
        echo "$USER"
        return 0
    fi

    # Last resort: try default psql resolution (no -U) and ask the server who we are
    if psql -d postgres -c '\q' &> /dev/null; then
        psql -d postgres -tAc "select current_user;" | tr -d '[:space:]'
        return 0
    fi

    return 1
}

DB_USER="$(detect_db_user || true)"
if [ -z "$DB_USER" ]; then
    echo "❌ Could not connect to PostgreSQL with 'postgres', '$USER', or default settings."
    echo ""
    echo "Fix options:"
    echo "  1) Run with your existing role:"
    echo "     DB_USER=<your_pg_role> ./setup_database.sh"
    echo ""
    echo "  2) Create a 'postgres' superuser role (if you want the default to work):"
    echo "     createuser -s postgres"
    exit 1
fi

echo "Using PostgreSQL role: $DB_USER"

echo "Creating databases..."
echo "  - Main DB: $DB_NAME"
echo "  - Test DB: $TEST_DB_NAME"
echo ""

# Create main database
if psql -lqt -U "$DB_USER" -d postgres | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo "⚠️  Database '$DB_NAME' already exists"
else
    createdb -U "$DB_USER" "$DB_NAME"
    echo "✅ Created database '$DB_NAME'"
fi

# Create test database
if psql -lqt -U "$DB_USER" -d postgres | cut -d \| -f 1 | grep -qw "$TEST_DB_NAME"; then
    echo "⚠️  Database '$TEST_DB_NAME' already exists"
else
    createdb -U "$DB_USER" "$TEST_DB_NAME"
    echo "✅ Created database '$TEST_DB_NAME'"
fi

echo ""
echo "Databases created successfully!"
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env:"
echo "     cp .env.example .env"
echo ""
echo "  2. Update DATABASE_URL in .env if needed"
echo ""
echo "  3. Run migrations:"
echo "     alembic upgrade head"
echo ""
echo "  4. Run tests:"
echo "     pytest tests/test_database_schema.py tests/test_auth_flows.py -v"
echo ""
echo "✨ Setup complete!"

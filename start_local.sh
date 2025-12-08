#!/bin/bash
# Local development startup script
# Runs without PostgreSQL and Redis for development

echo "🚀 Starting local development environment..."

# Export environment to skip database requirements
export POSTGRES_HOST=""
export REDIS_URL=""
export ENV="development"

# Check if PostgreSQL is needed
read -p "Do you want to use PostgreSQL? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Check if PostgreSQL is running
    if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
        echo "✅ PostgreSQL is running"
        export POSTGRES_HOST="localhost"
    else
        echo "⚠️ PostgreSQL not running. Starting without database..."
        echo "To start PostgreSQL: brew services start postgresql@14"
    fi
fi

# Check if Redis is needed
read -p "Do you want to use Redis? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    # Check if Redis is running
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis is running"
        export REDIS_URL="redis://localhost:6379"
    else
        echo "⚠️ Redis not running. Starting without Redis..."
        echo "To start Redis: brew services start redis"
    fi
fi

echo ""
echo "📊 Configuration:"
echo "  PostgreSQL: ${POSTGRES_HOST:-Not configured}"
echo "  Redis: ${REDIS_URL:-Not configured}"
echo ""

# Start the API
echo "Starting API server on port 8000..."
python3 -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0

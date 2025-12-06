#!/bin/bash
# ==============================================
# Production Deployment Script for zkalphaflow
# Run on DigitalOcean droplet
# ==============================================

set -e

DEPLOY_DIR="/opt/zkalphaflow"
SERVICE_NAME="zkalphaflow"
VENV_DIR="$DEPLOY_DIR/.venv"

echo "🚀 Starting deployment..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo"
    exit 1
fi

# Navigate to deploy directory
cd "$DEPLOY_DIR"

# Pull latest code (if using git)
if [ -d ".git" ]; then
    echo "📥 Pulling latest code..."
    git pull origin main
fi

# Activate virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "🐍 Creating virtual environment..."
    python3.11 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations
echo "🗄️ Running database migrations..."
if [ -f "db/migrations/001_add_verification_fields.sql" ]; then
    # Check if PostgreSQL is configured
    if [ -n "$POSTGRES_HOST" ]; then
        PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f db/migrations/001_add_verification_fields.sql || echo "Migration may have already been applied"
    fi
fi

# Initialize database schema
echo "🏗️ Initializing schema..."
python -c "
import asyncio
from db.schema import init_schema
asyncio.run(init_schema())
print('Schema initialized')
" || echo "Schema init skipped (may already exist)"

# Restart service
echo "🔄 Restarting service..."
systemctl restart "$SERVICE_NAME"

# Check status
sleep 3
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service is running"
else
    echo "❌ Service failed to start"
    journalctl -u "$SERVICE_NAME" -n 20 --no-pager
    exit 1
fi

# Health check
echo "🏥 Running health check..."
sleep 2
HEALTH=$(curl -s http://localhost:8000/health)
echo "Health: $HEALTH"

LEDGER=$(curl -s http://localhost:8000/health/ledger)
echo "Ledger: $LEDGER"

SCANNERS=$(curl -s http://localhost:8000/health/scanners | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Active: {d[\"active_scanners\"]}/{d[\"total_scanners\"]}')")
echo "Scanners: $SCANNERS"

echo ""
echo "🎉 Deployment complete!"
echo "   Domain: https://zkalphaflow.com"
echo "   API: https://zkalphaflow.com/api"
echo ""

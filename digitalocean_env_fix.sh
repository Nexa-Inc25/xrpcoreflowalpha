#!/bin/bash

# Fix DigitalOcean environment variables immediately
# This will make the app use SQLite and disable Redis

APP_ID="8f68b264-cb81-4288-8e01-3caf8c0cd80b"

echo "Fixing DigitalOcean environment variables..."
echo "This will:"
echo "1. Enable SQLite fallback by setting APP_ENV=dev"
echo "2. Disable PostgreSQL hostname resolution issues"
echo "3. Disable Redis requirements"
echo ""

# Check if doctl is installed
if ! command -v doctl &> /dev/null; then
    echo "ERROR: doctl is not installed or configured"
    echo ""
    echo "Please set these environment variables manually in DigitalOcean:"
    echo "  https://cloud.digitalocean.com/apps/${APP_ID}/settings"
    echo ""
    echo "Variables to add:"
    echo "  APP_ENV = dev"
    echo "  POSTGRES_HOST = disabled"
    echo "  REDIS_URL = (leave empty)"
    echo "  REDIS_OPTIONAL = true"
    exit 1
fi

# Set environment variables to fix the issues
echo "Setting APP_ENV to dev (enables SQLite fallback)..."
doctl apps config set ${APP_ID} --app-config APP_ENV=dev

echo "Disabling PostgreSQL requirement..."
doctl apps config set ${APP_ID} --app-config POSTGRES_HOST=disabled

echo "Disabling Redis requirement..."
doctl apps config set ${APP_ID} --app-config REDIS_URL=""
doctl apps config set ${APP_ID} --app-config REDIS_OPTIONAL=true

echo ""
echo "Environment variables updated!"
echo "The app will restart automatically in a few minutes."
echo ""
echo "Monitor the deployment at:"
echo "  https://cloud.digitalocean.com/apps/${APP_ID}/deployments"
echo ""
echo "Check logs with:"
echo "  doctl apps logs ${APP_ID} --tail 50"

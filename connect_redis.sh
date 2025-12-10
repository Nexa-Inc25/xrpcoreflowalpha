#!/bin/bash

# Connect the existing Redis (Valkey) database to the app

echo "🔧 Connecting Redis to zkalphaflow app..."

APP_ID="8f68b264-cb81-4288-8e01-3caf8c0cd80b"
# REDIS_URL should be set as a SECRET in DigitalOcean dashboard
# Get it from: doctl databases connection afe69f13-c72a-4843-9571-9942e4568fe7

echo "📝 Setting REDIS_URL environment variable..."

# Update the API service
doctl apps update-env $APP_ID \
  --env REDIS_URL="$REDIS_URL" \
  --component api

# Update the worker service
doctl apps update-env $APP_ID \
  --env REDIS_URL="$REDIS_URL" \
  --component worker

echo "✅ Redis connected!"
echo ""
echo "🚀 Triggering deployment to apply changes..."
doctl apps create-deployment $APP_ID --force-rebuild

echo ""
echo "📊 Monitor deployment:"
echo "doctl apps list-deployments $APP_ID | head -3"
echo ""
echo "✅ Redis connection updated!"
echo "Make sure to set REDIS_URL as a SECRET in DigitalOcean dashboard"

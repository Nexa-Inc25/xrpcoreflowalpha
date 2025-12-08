#!/bin/bash

# DigitalOcean App Platform Deployment Script for zkalphaflow
# This script ensures source-based builds and avoids pre-built image issues

set -e

echo "🚀 Starting deployment to DigitalOcean App Platform..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for required tools
check_tool() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed. Please install it first.${NC}"
        exit 1
    fi
}

echo "📋 Checking dependencies..."
check_tool "doctl"
check_tool "git"
check_tool "docker"

# Validate environment
if [ -z "$DIGITALOCEAN_ACCESS_TOKEN" ]; then
    echo -e "${YELLOW}⚠️  DIGITALOCEAN_ACCESS_TOKEN not set. Attempting to authenticate...${NC}"
    doctl auth init
else
    echo "✅ Using existing DigitalOcean authentication"
    doctl auth init -t $DIGITALOCEAN_ACCESS_TOKEN
fi

# Get app ID
APP_NAME="zkalphaflow"
echo "🔍 Finding app ID for $APP_NAME..."
APP_ID=$(doctl apps list --format ID,Spec.Name --no-header | grep "$APP_NAME" | awk '{print $1}')

if [ -z "$APP_ID" ]; then
    echo -e "${RED}❌ App '$APP_NAME' not found. Creating new app...${NC}"
    doctl apps create --spec .do/app.yaml
    APP_ID=$(doctl apps list --format ID,Spec.Name --no-header | grep "$APP_NAME" | awk '{print $1}')
else
    echo "✅ Found app ID: $APP_ID"
fi

# Ensure we're using source-based builds
echo "🔧 Validating app configuration for source-based builds..."

# Check current app spec
CURRENT_SPEC=$(doctl apps spec get $APP_ID -o json)

# Verify components are using github source, not images
if echo "$CURRENT_SPEC" | grep -q '"image":'; then
    echo -e "${YELLOW}⚠️  Detected image-based deployment. Switching to source-based...${NC}"
    
    # Update app spec to use GitHub source
    echo "📝 Updating app specification..."
    doctl apps update $APP_ID --spec .do/app.yaml --wait
    
    echo "✅ Switched to source-based deployment"
else
    echo "✅ App is already configured for source-based builds"
fi

# Trigger deployment
echo "🚀 Triggering deployment from GitHub..."
DEPLOYMENT_ID=$(doctl apps create-deployment $APP_ID --force-rebuild --format ID --no-header)
echo "📦 Deployment ID: $DEPLOYMENT_ID"

# Monitor deployment
echo "⏳ Monitoring deployment progress..."
while true; do
    STATUS=$(doctl apps get-deployment $APP_ID $DEPLOYMENT_ID --format Phase --no-header)
    
    case $STATUS in
        "PENDING_BUILD"|"BUILDING")
            echo "🔨 Building from source..."
            ;;
        "PENDING_DEPLOY"|"DEPLOYING")
            echo "📦 Deploying to instances..."
            ;;
        "ACTIVE")
            echo -e "${GREEN}✅ Deployment successful!${NC}"
            break
            ;;
        "ERROR"|"CANCELED")
            echo -e "${RED}❌ Deployment failed with status: $STATUS${NC}"
            echo "📋 Getting deployment logs..."
            doctl apps logs $APP_ID --deployment $DEPLOYMENT_ID
            exit 1
            ;;
        *)
            echo "📊 Status: $STATUS"
            ;;
    esac
    
    sleep 10
done

# Verify deployment
echo "🔍 Verifying deployment..."

# Check API health
API_URL="https://api.zkalphaflow.com"
echo "Checking API at $API_URL..."
if curl -f "$API_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  API health check failed, but deployment completed${NC}"
fi

# Check web app
WEB_URL="https://zkalphaflow.com"
echo "Checking web app at $WEB_URL..."
if curl -f "$WEB_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Web app is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Web app check failed, but deployment completed${NC}"
fi

# Get app info
echo ""
echo "📊 Deployment Summary:"
echo "========================"
doctl apps get $APP_ID --format "ID,DefaultIngress,ActiveDeployment.Cause,UpdatedAt" --no-header
echo ""
echo "🔗 URLs:"
echo "  - Web: https://zkalphaflow.com"
echo "  - API: https://api.zkalphaflow.com"
echo "  - Docs: https://api.zkalphaflow.com/docs"
echo ""

# Show recent logs
echo "📜 Recent logs (last 20 lines):"
doctl apps logs $APP_ID --tail 20

echo ""
echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Test the correlation endpoints: curl https://api.zkalphaflow.com/analytics/heatmap?assets=xrp,btc,spy"
echo "  2. Check Slack integration: https://api.zkalphaflow.com/admin/slack/test"
echo "  3. Monitor real-time flows: https://zkalphaflow.com/dashboard"

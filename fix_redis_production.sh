#!/bin/bash

# Fix Redis URL issues in production
# This script updates environment variables on DigitalOcean to disable Redis

echo "🔧 Fixing Redis issues in production..."

# Check if doctl is installed
if ! command -v doctl &> /dev/null; then
    echo "❌ doctl is not installed. Please install it first:"
    echo "   brew install doctl"
    exit 1
fi

# App ID for zkalphaflow
APP_ID="8f68b264-cb81-4288-8e01-3caf8c0cd80b"

echo "📝 Updating environment variables to disable Redis..."

# Update API component environment variables
doctl apps update $APP_ID --spec - <<EOF
name: zkalphaflow
region: nyc
services:
  - name: web
    github:
      repo: Nexa-Inc25/xrpcoreflowalpha
      branch: main
      deploy_on_push: true
    source_dir: apps/web
    dockerfile_path: apps/web/Dockerfile
    http_port: 3000
    instance_size_slug: basic-xxs
    instance_count: 1
    routes:
      - path: /
    envs:
      - key: NEXT_PUBLIC_API_BASE
        value: https://api.zkalphaflow.com
      - key: NEXT_PUBLIC_API_WS_BASE
        value: wss://api.zkalphaflow.com
      - key: NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
        value: pk_live_Y2xlcmsuemthbHBoYWZsb3cuY29tJA
      - key: NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL
        value: "/"
      - key: NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL
        value: "/"
  
  - name: api
    github:
      repo: Nexa-Inc25/xrpcoreflowalpha
      branch: main
      deploy_on_push: true
    source_dir: /
    dockerfile_path: Dockerfile
    http_port: 8000
    instance_size_slug: basic-xs
    instance_count: 1
    routes:
      - path: /api
        preserve_path_prefix: true
    envs:
      - key: DATABASE_URL
        type: SECRET
      - key: REDIS_URL
        value: ""  # Empty string to disable Redis
      - key: REDIS_OPTIONAL
        value: "true"
      - key: ALCHEMY_WS_URL
        type: SECRET
      - key: ALCHEMY_API_KEY
        type: SECRET
      - key: XRPL_WSS
        value: "wss://s1.ripple.com/"
      - key: FINNHUB_API_KEY
        type: SECRET
      - key: POLYGON_API_KEY
        type: SECRET
      - key: COINGECKO_API_KEY
        type: SECRET
      - key: SOLANA_RPC_URL
        type: SECRET
      - key: SENTRY_DSN
        type: SECRET
      - key: ALERTS_SLACK_WEBHOOK
        type: SECRET
      - key: WHALE_ALERT_API_KEY
        type: SECRET
      - key: ALPHA_VANTAGE_API_KEY
        type: SECRET
      - key: ENABLE_EQUITY_CORRELATION
        value: "true"
      - key: ENABLE_FUTURES_CORRELATION
        value: "true"
      - key: ENABLE_FOREX_CORRELATION
        value: "true"
      - key: CORRELATION_UPDATE_INTERVAL
        value: "60"
      - key: POSTGRES_HOST
        type: SECRET
      - key: POSTGRES_PORT
        value: "25060"
      - key: POSTGRES_DB
        type: SECRET
      - key: POSTGRES_USER
        type: SECRET
      - key: POSTGRES_PASSWORD
        type: SECRET
      - key: POSTGRES_SSLMODE
        value: "require"
      - key: APP_ENV
        value: "prod"
      - key: CORS_ALLOW_ORIGINS
        value: "https://zkalphaflow-q3alj.ondigitalocean.app,https://zkalphaflow.com,http://localhost:3000"
      - key: BINANCE_WS_URL
        value: "wss://stream.binance.com:9443/ws"
      - key: LATENCY_PING_INTERVAL
        value: "5"
      - key: XGBOOST_RETRAIN_INTERVAL
        value: "86400"
      - key: SLACK_EDUCATOR_WEBHOOK_URL
        type: SECRET
      - key: SLACK_BOT_TOKEN
        type: SECRET
      - key: MIN_LATENCY_ANOMALY_SCORE
        value: "75"
      - key: HFT_LATENCY_THRESHOLD
        value: "50"
      - key: ETHERSCAN_API_KEY
        type: SECRET
      - key: DUNE_API_KEY
        type: SECRET
      - key: CLERK_SECRET_KEY
        type: SECRET
      - key: SLACK_COURSE_WEBHOOK_URL
        type: SECRET
      - key: ENABLE_SLACK_COURSES
        value: "true"

workers:
  - name: worker
    github:
      repo: Nexa-Inc25/xrpcoreflowalpha
      branch: main
      deploy_on_push: true
    source_dir: /
    dockerfile_path: Dockerfile
    instance_size_slug: basic-xs
    instance_count: 1
    autoscaling:
      min_instance_count: 1
      max_instance_count: 3
      metrics:
        cpu:
          percent: 70
    envs:
      - key: DATABASE_URL
        type: SECRET
      - key: REDIS_URL
        value: ""  # Empty string to disable Redis
      - key: REDIS_OPTIONAL
        value: "true"
      - key: ALCHEMY_WS_URL
        type: SECRET
      - key: ALERTS_SLACK_WEBHOOK
        type: SECRET
      - key: WHALE_ALERT_API_KEY
        type: SECRET
      - key: POLYGON_API_KEY
        type: SECRET
      - key: ALPHA_VANTAGE_API_KEY
        type: SECRET
      - key: XRPL_WSS
        value: "wss://s1.ripple.com"

domains:
  - domain: zkalphaflow.com
    type: PRIMARY
  - domain: www.zkalphaflow.com
    type: ALIAS
EOF

echo "✅ Environment variables updated"
echo ""
echo "🚀 Triggering deployment..."
doctl apps create-deployment $APP_ID --force-rebuild

echo ""
echo "📊 Check deployment status:"
echo "doctl apps list-deployments $APP_ID"
echo ""
echo "Or visit: https://cloud.digitalocean.com/apps/$APP_ID/deployments"

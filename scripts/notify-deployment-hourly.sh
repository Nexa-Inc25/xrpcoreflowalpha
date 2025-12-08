#!/bin/bash

# Rate-limited Slack deployment notification (max 1 per hour)

# Load environment variables from .env file if it exists
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

# Requires SLACK_WEBHOOK environment variable to be set
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"

if [ -z "$SLACK_WEBHOOK" ]; then
    echo "Error: SLACK_WEBHOOK environment variable not set"
    echo "Either export it or create scripts/.env file"
    exit 1
fi
LAST_NOTIFY_FILE="/tmp/zkalphaflow_last_notify.txt"
CURRENT_TIME=$(date +%s)

# Check if we've sent a notification in the last hour
if [ -f "$LAST_NOTIFY_FILE" ]; then
    LAST_TIME=$(cat "$LAST_NOTIFY_FILE")
    TIME_DIFF=$((CURRENT_TIME - LAST_TIME))
    
    # 3600 seconds = 1 hour
    if [ $TIME_DIFF -lt 3600 ]; then
        MINUTES_LEFT=$(( (3600 - TIME_DIFF) / 60 ))
        echo "⏰ Rate limit: Next notification allowed in $MINUTES_LEFT minutes"
        exit 0
    fi
fi

# Get deployment status
APP_ID="8f68b264-cb81-4288-8e01-3caf8c0cd80b"
API_HEALTH=$(curl -s https://api.zkalphaflow.com/health | jq -r '.status' 2>/dev/null || echo "offline")
WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://www.zkalphaflow.com 2>/dev/null || echo "000")
LATEST_DEPLOYMENT=$(doctl apps list-deployments $APP_ID --format Phase,Cause,Created --no-header | head -1)

# Build status emoji
if [[ "$API_HEALTH" == "live" ]] && [[ "$WEB_STATUS" == "200" ]]; then
    EMOJI="✅"
    STATUS_TEXT="All Systems Operational"
else
    EMOJI="⚠️"
    STATUS_TEXT="Partial Service"
fi

# Send notification
curl -X POST -H 'Content-type: application/json' --data "{
  \"text\": \"$EMOJI zkalphaflow Hourly Status Update\",
  \"blocks\": [
    {
      \"type\": \"header\",
      \"text\": {
        \"type\": \"plain_text\",
        \"text\": \"🕐 Hourly Status Report\"
      }
    },
    {
      \"type\": \"section\",
      \"text\": {
        \"type\": \"mrkdwn\",
        \"text\": \"*$STATUS_TEXT*\"
      }
    },
    {
      \"type\": \"section\",
      \"fields\": [
        {
          \"type\": \"mrkdwn\",
          \"text\": \"*API:* $API_HEALTH\"
        },
        {
          \"type\": \"mrkdwn\",
          \"text\": \"*Web:* HTTP $WEB_STATUS\"
        }
      ]
    },
    {
      \"type\": \"context\",
      \"elements\": [
        {
          \"type\": \"mrkdwn\",
          \"text\": \"Next update in 1 hour | $(date '+%H:%M UTC')\nView details at <https://cloud.digitalocean.com/apps/$APP_ID|DigitalOcean>\"
        }
      ]
    }
  ]
}" $SLACK_WEBHOOK

# Update last notification time
echo "$CURRENT_TIME" > "$LAST_NOTIFY_FILE"
echo "✅ Notification sent (next allowed in 60 minutes)"

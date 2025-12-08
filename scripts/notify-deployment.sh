#!/bin/bash

# Slack deployment notification script for zkalphaflow

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

# Get deployment status
APP_ID="8f68b264-cb81-4288-8e01-3caf8c0cd80b"
STATUS=$(doctl apps get $APP_ID --format ActiveDeployment.Phase --no-header 2>/dev/null || echo "UNKNOWN")
API_HEALTH=$(curl -s https://api.zkalphaflow.com/health | jq -r '.status' 2>/dev/null || echo "offline")
WEB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://www.zkalphaflow.com 2>/dev/null || echo "000")

# Build status emoji
if [[ "$API_HEALTH" == "live" ]] && [[ "$WEB_STATUS" == "200" ]]; then
    EMOJI="✅"
    STATUS_TEXT="LIVE"
else
    EMOJI="⚠️"
    STATUS_TEXT="PARTIAL"
fi

# Send notification
curl -X POST -H 'Content-type: application/json' --data "{
  \"text\": \"$EMOJI zkalphaflow Deployment Update\",
  \"blocks\": [
    {
      \"type\": \"header\",
      \"text\": {
        \"type\": \"plain_text\",
        \"text\": \"zkalphaflow Deployment Status\"
      }
    },
    {
      \"type\": \"section\",
      \"fields\": [
        {
          \"type\": \"mrkdwn\",
          \"text\": \"*API Status:*\n$API_HEALTH\"
        },
        {
          \"type\": \"mrkdwn\",
          \"text\": \"*Web Status:*\nHTTP $WEB_STATUS\"
        },
        {
          \"type\": \"mrkdwn\",
          \"text\": \"*Deployment:*\n$STATUS\"
        },
        {
          \"type\": \"mrkdwn\",
          \"text\": \"*Time:*\n$(date '+%Y-%m-%d %H:%M UTC')\"
        }
      ]
    },
    {
      \"type\": \"section\",
      \"text\": {
        \"type\": \"mrkdwn\",
        \"text\": \"*Links:*\n• <https://www.zkalphaflow.com|Web App>\n• <https://api.zkalphaflow.com/docs|API Docs>\n• <https://cloud.digitalocean.com/apps/$APP_ID|DigitalOcean Dashboard>\"
      }
    }
  ]
}" $SLACK_WEBHOOK

echo "Notification sent to Slack"

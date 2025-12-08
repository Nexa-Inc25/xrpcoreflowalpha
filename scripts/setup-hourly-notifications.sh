#!/bin/bash

# Setup hourly notifications for zkalphaflow

echo "📋 Setting up hourly deployment notifications..."

# Make script executable
chmod +x scripts/notify-deployment-hourly.sh

# Get absolute path
SCRIPT_PATH="$(cd "$(dirname "$0")"; pwd)/notify-deployment-hourly.sh"

# Create cron job (runs at the top of every hour)
CRON_CMD="0 * * * * $SCRIPT_PATH >> /tmp/zkalphaflow_notify.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "notify-deployment-hourly.sh"; then
    echo "⚠️  Cron job already exists. Updating..."
    # Remove old entry
    crontab -l | grep -v "notify-deployment-hourly.sh" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "✅ Hourly notifications configured!"
echo ""
echo "📅 Schedule: Every hour at :00"
echo "📁 Log file: /tmp/zkalphaflow_notify.log"
echo ""
echo "To view scheduled jobs: crontab -l"
echo "To remove: crontab -l | grep -v 'notify-deployment-hourly.sh' | crontab -"
echo ""
echo "🔔 Manual test (respects rate limit):"
echo "   ./scripts/notify-deployment-hourly.sh"

#!/bin/bash

echo "🔍 Checking Worker Status..."
echo "============================="

# Check deployment status
echo -e "\n📦 Deployment Status:"
doctl apps list-deployments 8f68b264-cb81-4288-8e01-3caf8c0cd80b --format Phase,Cause | head -2

# Check worker logs for errors
echo -e "\n📋 Recent Worker Errors (last 10):"
doctl apps logs 8f68b264-cb81-4288-8e01-3caf8c0cd80b worker --tail 50 | grep -i "error\|401\|403\|failed" | tail -10

# Check CPU usage (if available)
echo -e "\n💻 Worker Component Info:"
doctl apps get-component 8f68b264-cb81-4288-8e01-3caf8c0cd80b worker 2>/dev/null | grep -E "instance_size|instance_count" || echo "Worker info not available yet"

echo -e "\n✅ Actions Needed:"
echo "1. Delete PostgreSQL: doctl databases delete 14a6df8c-27f3-42aa-9153-ea1efac54f5e"
echo "2. Check WhaleAlert key if still getting 401 errors"
echo "3. Monitor at: https://cloud.digitalocean.com/apps/8f68b264-cb81-4288-8e01-3caf8c0cd80b"

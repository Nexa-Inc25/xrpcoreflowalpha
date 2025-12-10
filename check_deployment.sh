#!/bin/bash

echo "🚀 Waiting for deployment to start..."
sleep 10

echo "📊 Monitoring deployment progress..."
echo ""

for i in {1..60}; do
    STATUS=$(doctl apps list-deployments 8f68b264-cb81-4288-8e01-3caf8c0cd80b --format Phase,Progress | head -2 | tail -1)
    echo -ne "[$i/60] Status: $STATUS     "
    
    if [[ $STATUS == *"ACTIVE"* ]]; then
        echo ""
        echo ""
        echo "✅ DEPLOYMENT COMPLETE!"
        echo ""
        echo "Checking for errors..."
        echo "========================"
        doctl apps logs 8f68b264-cb81-4288-8e01-3caf8c0cd80b api --tail 20 | grep -E "Connected|Started|ERROR|error|401|unavailable" || echo "No errors found!"
        break
    fi
    
    sleep 5
done

echo ""
echo "Final check..."
doctl apps logs 8f68b264-cb81-4288-8e01-3caf8c0cd80b api --tail 5

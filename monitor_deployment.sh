#!/bin/bash

echo "📊 Monitoring deployment..."
echo ""

while true; do
    STATUS=$(doctl apps list-deployments 8f68b264-cb81-4288-8e01-3caf8c0cd80b --format Phase,Progress | head -2 | tail -1)
    echo -ne "⏳ Status: $STATUS"
    
    if [[ $STATUS == *"ACTIVE"* ]]; then
        echo ""
        echo ""
        echo "✅ DEPLOYMENT COMPLETE!"
        echo ""
        echo "Checking API logs..."
        doctl apps logs 8f68b264-cb81-4288-8e01-3caf8c0cd80b api --tail 10
        break
    fi
    
    sleep 5
done

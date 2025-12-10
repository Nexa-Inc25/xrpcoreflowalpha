#!/bin/bash

echo "🔍 Monitoring Fix Status..."
echo "==========================="

# Check deployment status
echo -e "\n📦 Deployment Status:"
doctl apps list-deployments 8f68b264-cb81-4288-8e01-3caf8c0cd80b --format Phase,Cause | head -2

# Check for Yahoo Finance errors
echo -e "\n📈 Yahoo Finance Status (should see SPY/QQQ, not ^GSPC/^NDX):"
doctl apps logs 8f68b264-cb81-4288-8e01-3caf8c0cd80b worker --tail 100 | grep -E "SPY|QQQ|GSPC|NDX" | tail -5 || echo "No ticker activity yet"

# Check for PostgreSQL errors (these will exist until DB is deleted)
echo -e "\n💾 PostgreSQL Errors (expected until deleted):"
doctl apps logs 8f68b264-cb81-4288-8e01-3caf8c0cd80b worker --tail 100 | grep -c "PostgreSQL unavailable" | xargs -I {} echo "{} errors in last 100 lines"

# Check XRPL status
echo -e "\n✅ XRPL Status (should be processing):"
doctl apps logs 8f68b264-cb81-4288-8e01-3caf8c0cd80b worker --tail 50 | grep "XRPL.*Heartbeat" | tail -2 || echo "No XRPL activity"

echo -e "\n📍 Next Steps:"
echo "1. If deployment is ACTIVE, Yahoo errors should stop"
echo "2. Delete database to stop PostgreSQL errors:"
echo "   doctl databases delete 14a6df8c-27f3-42aa-9153-ea1efac54f5e"
echo "3. Check frontend at https://www.zkalphaflow.com"

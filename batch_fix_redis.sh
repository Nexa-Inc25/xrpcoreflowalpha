#!/bin/bash

# Batch fix remaining Redis import files
echo "🔧 Batch fixing remaining Redis imports..."

# List of remaining files that need updating
files=(
    "billing/onchain_watchers.py"
    "correlator/cross_market.py"
    "execution/engine.py"
    "godark/detector.py"
    "godark/dynamic_ingest.py"
    "godark/pattern_monitor.py"
    "ml/flow_predictor.py"
    "ml/latency_xgboost.py"
    "notifications/push_worker.py"
    "notifications/telegram_worker.py"
    "predictors/latency_pinger.py"
    "scanners/godark_eth_scanner.py"
    "scanners/penumbra_detector.py"
    "scanners/rwa_amm_liquidity_monitor.py"
    "scanners/secret_detector.py"
    "scanners/solana_humidifi.py"
    "scanners/xrpl_orderbook_monitor.py"
    "scanners/xrpl_trustline_watcher.py"
    "utils/price.py"
    "workers/educator_bot.py"
    "workers/slack_latency_bot.py"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "Processing $file..."
        
        # Create a temporary backup
        cp "$file" "${file}.bak"
        
        # Replace Redis imports
        sed -i '' 's/^import redis\.asyncio as redis$/from app.redis_utils import get_redis, REDIS_ENABLED/g' "$file"
        
        # Replace redis.from_url patterns
        sed -i '' 's/redis\.from_url(REDIS_URL[^)]*)/await get_redis()/g' "$file"
        
        # Remove REDIS_URL from imports when it's the only thing
        sed -i '' 's/from app\.config import REDIS_URL$/# REDIS_URL import removed - using redis_utils/g' "$file"
        
        # Update type hints
        sed -i '' 's/-> redis\.Redis:/:/g' "$file"
        
        # Check if file was modified
        if ! diff -q "$file" "${file}.bak" > /dev/null; then
            echo "✅ Updated $file"
            rm "${file}.bak"
        else
            echo "ℹ️  No changes needed for $file"
            rm "${file}.bak"
        fi
    else
        echo "⚠️  File not found: $file"
    fi
done

echo ""
echo "📊 Batch update complete!"
echo "Run 'git diff' to review changes"

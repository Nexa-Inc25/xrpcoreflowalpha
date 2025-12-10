#!/bin/bash

# Fix all broken Redis type hints
echo "🔧 Fixing broken Redis type hints..."

files=(
    "billing/onchain_watchers.py"
    "notifications/push_worker.py"
    "notifications/telegram_worker.py"
    "scanners/penumbra_detector.py"
    "scanners/solana_humidifi.py"
    "scanners/secret_detector.py"
    "execution/engine.py"
    "ml/latency_xgboost.py"
    "predictors/latency_pinger.py"
    "utils/price.py"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "Fixing $file..."
        # Replace the type hint with a simple assignment
        sed -i '' 's/_redis: Optional\[redis\.Redis\] = None/_redis = None  # Redis client instance/g' "$file"
        echo "✅ Fixed $file"
    fi
done

# Also fix app/redis_utils.py which has a different pattern
if [ -f "app/redis_utils.py" ]; then
    echo "Fixing app/redis_utils.py..."
    sed -i '' 's/_redis_client: Optional\[redis\.Redis\] = None/_redis_client = None  # Redis client instance/g' "app/redis_utils.py"
    # Also need to fix the return type hint in the function
    sed -i '' 's/async def get_redis() -> redis\.Redis:/async def get_redis():/g' "app/redis_utils.py"
    echo "✅ Fixed app/redis_utils.py"
fi

echo ""
echo "✅ All type hints fixed!"

#!/usr/bin/env python3
"""
Script to fix all remaining Redis imports to use redis_utils module.
"""
import os
import re

# List of files that need updating (from grep search)
files_to_update = [
    "api/monitoring.py",
    "api/user.py", 
    "billing/onchain_watchers.py",
    "bus/signal_bus.py",
    "correlator/cross_market.py",
    "execution/engine.py",
    "godark/detector.py",
    "godark/dynamic_ingest.py",
    "godark/pattern_monitor.py",
    "middleware/api_key.py",
    "ml/flow_predictor.py",
    "ml/latency_xgboost.py",
    "notifications/push_worker.py",
    "notifications/telegram_worker.py",
    "predictors/latency_pinger.py",
    "scanners/godark_eth_scanner.py",
    "scanners/penumbra_detector.py",
    "scanners/rwa_amm_liquidity_monitor.py",
    "scanners/secret_detector.py",
    "scanners/solana_humidifi.py",
    "scanners/xrpl_orderbook_monitor.py",
    "scanners/xrpl_trustline_watcher.py",
    "utils/price.py",
    "utils/redis_client.py",
    "workers/educator_bot.py",
    "workers/slack_latency_bot.py"
]

def update_file(filepath):
    """Update a single file to use redis_utils."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Replace the import statement
        content = re.sub(
            r'import redis\.asyncio as redis\s*\n',
            'from app.redis_utils import get_redis, REDIS_ENABLED\n',
            content
        )
        
        # Also handle cases where REDIS_URL is imported
        content = re.sub(
            r'from app\.config import \(([^)]*?)REDIS_URL,?\s*([^)]*?)\)',
            lambda m: f"from app.config import ({m.group(1).replace('REDIS_URL,', '').replace('REDIS_URL', '') + m.group(2)})",
            content
        )
        
        # Replace redis.from_url patterns
        content = re.sub(
            r'redis\.from_url\(REDIS_URL[^)]*\)',
            'await get_redis()',
            content
        )
        
        # Replace Redis type hints
        content = re.sub(
            r'-> redis\.Redis:',
            ':',
            content
        )
        
        # Check if we need to add REDIS_ENABLED checks
        if 'await get_redis()' in content or 'await _get_redis()' in content:
            # Add checks for common patterns
            patterns = [
                (r'async def (\w+)\([^)]*\)[^{]*{(\s*r = await _get_redis\(\))',
                 r'async def \1(\2):\n    if not REDIS_ENABLED:\n        return None\n    r = await _get_redis()'),
            ]
            
            for pattern, replacement in patterns:
                content = re.sub(pattern, replacement, content)
        
        if content != original_content:
            with open(filepath, 'w') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error updating {filepath}: {e}")
        return False

def main():
    updated = []
    failed = []
    
    for file in files_to_update:
        filepath = file
        if not os.path.exists(filepath):
            print(f"⚠️  File not found: {filepath}")
            failed.append(file)
            continue
            
        if update_file(filepath):
            print(f"✅ Updated: {file}")
            updated.append(file)
        else:
            print(f"ℹ️  No changes needed: {file}")
    
    print(f"\n📊 Summary:")
    print(f"   Updated: {len(updated)} files")
    print(f"   Failed: {len(failed)} files")
    
    if updated:
        print(f"\n✅ Successfully updated files:")
        for f in updated:
            print(f"   - {f}")
    
    if failed:
        print(f"\n❌ Failed files:")
        for f in failed:
            print(f"   - {f}")

if __name__ == "__main__":
    main()

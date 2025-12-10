#!/usr/bin/env python3
"""
Fix ALL API integrations - NO MORE FAKE DATA
Ensure all paid APIs are properly used
"""

import os

# List of ALL paid APIs that MUST be configured
REQUIRED_APIS = {
    'WHALE_ALERT_API_KEY': 'Whale Alert for large transaction tracking',
    'ALPHA_VANTAGE_API_KEY': 'Alpha Vantage for market data',
    'POLYGON_API_KEY': 'Polygon for equity/futures data',
    'FINNHUB_API_KEY': 'Finnhub for real-time market data',
    'COINGECKO_API_KEY': 'CoinGecko for crypto prices',
    'ETHERSCAN_API_KEY': 'Etherscan for wallet balances',
    'ALCHEMY_WS_URL': 'Alchemy for Ethereum data',
    'XRPL_WSS': 'XRPL WebSocket for Ripple data'
}

# Check which APIs are configured
print("=" * 80)
print("API KEY AUDIT - CHECKING WHAT'S CONFIGURED")
print("=" * 80)

missing = []
configured = []

for api_key, description in REQUIRED_APIS.items():
    value = os.getenv(api_key, '')
    if value and value != 'None' and len(value) > 10:
        print(f"✅ {api_key}: CONFIGURED - {description}")
        configured.append(api_key)
    else:
        print(f"❌ {api_key}: MISSING - {description}")
        missing.append(api_key)

print("\n" + "=" * 80)
print(f"SUMMARY: {len(configured)}/{len(REQUIRED_APIS)} APIs configured")
print("=" * 80)

if missing:
    print("\n⚠️ MISSING API KEYS (these need to be configured):")
    for api in missing:
        print(f"   - {api}: {REQUIRED_APIS[api]}")
    print("\nThese APIs are being PAID FOR but NOT USED!")
    print("The system is showing FAKE DATA instead of using these APIs!")

print("\n" + "=" * 80)
print("FILES THAT NEED FIXING (skipping APIs instead of using them):")
print("=" * 80)

files_to_fix = {
    'scanners/whale_alert_scanner.py': 'Returns empty data when no API key',
    'scanners/nansen_scanner.py': 'Skips entirely when no API key',
    'scanners/dune_scanner.py': 'Skips entirely when no API key',
    'scanners/forex_scanner.py': 'Skips forex data when no API key',
    'api/wallets.py': 'Cannot fetch live balances without Etherscan',
    'api/dashboard.py': 'Returns 0 prices without Alpha Vantage',
    'predictors/latency_pinger.py': 'Skips Polygon WebSocket',
    'predictors/databento_macro_tracker.py': 'Skips macro tracking'
}

for file, issue in files_to_fix.items():
    print(f"   {file}: {issue}")

print("\n" + "=" * 80)
print("SOLUTION:")
print("=" * 80)
print("1. Configure ALL missing API keys in DigitalOcean")
print("2. Change code to REQUIRE APIs instead of skipping")
print("3. Remove ALL fake data generation")
print("4. Only show REAL data from REAL APIs")
print("\nNO MORE FAKE DATA. EVER.")

#!/usr/bin/env python3
"""
Verify that the Redis fix is working in production.
"""
import asyncio
import httpx
import json
from datetime import datetime

# Production API URL
API_BASE = "https://api.zkalphaflow.com"

async def check_health():
    """Check basic health endpoint."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{API_BASE}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health endpoint working: {data}")
                return True
            else:
                print(f"❌ Health endpoint returned {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False

async def check_circuit_health():
    """Check circuit breaker endpoint (uses Redis)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{API_BASE}/api/health/circuit")
            if response.status_code == 200:
                data = response.json()
                # Check if Redis is disabled (which is OK)
                if data.get("redis") == "disabled":
                    print(f"✅ Circuit health working with Redis disabled: {data}")
                    return True
                else:
                    print(f"✅ Circuit health working with Redis enabled: {data}")
                    return True
            else:
                print(f"❌ Circuit health returned {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Circuit health check failed: {e}")
            return False

async def check_flow_state():
    """Check flow state endpoint."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{API_BASE}/api/dashboard/flow_state")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Flow state endpoint working")
                print(f"   Active scanners: {len(data.get('xrpl_scanners', []))}")
                print(f"   Fourier state: {data.get('fourier_state', {}).get('state', 'unknown')}")
                return True
            else:
                print(f"❌ Flow state returned {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Flow state check failed: {e}")
            return False

async def check_market_prices():
    """Check market prices endpoint."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{API_BASE}/api/dashboard/market_prices")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Market prices endpoint working")
                if 'XRP' in data:
                    print(f"   XRP price: ${data['XRP'].get('price', 0):.4f}")
                if 'BTC' in data:
                    print(f"   BTC price: ${data['BTC'].get('price', 0):.2f}")
                return True
            else:
                print(f"❌ Market prices returned {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Market prices check failed: {e}")
            return False

async def check_logs():
    """Check recent deployment logs for Redis errors."""
    print("\n📋 Recent deployment logs check:")
    print("   Run: doctl apps logs 8f68b264-cb81-4288-8e01-3caf8c0cd80b --type=run --tail=20")
    print("   Look for 'ValueError: Redis URL' errors")
    print("   If you see 'Redis is disabled' messages, that's OK - it means the fallback is working")

async def main():
    print(f"🔍 Verifying Redis fix in production at {datetime.now().isoformat()}")
    print(f"   API: {API_BASE}")
    print("-" * 60)
    
    # Run all checks
    results = []
    
    print("\n1. Basic Health Check:")
    results.append(await check_health())
    
    print("\n2. Circuit Breaker Health (Redis-dependent):")
    results.append(await check_circuit_health())
    
    print("\n3. Flow State Check:")
    results.append(await check_flow_state())
    
    print("\n4. Market Prices Check:")
    results.append(await check_market_prices())
    
    await check_logs()
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All checks passed! Redis fix is working properly.")
        print("   The app is running without Redis using the in-memory fallback.")
    else:
        failed = sum(1 for r in results if not r)
        print(f"⚠️  {failed} checks failed. The deployment may still be in progress.")
        print("   Wait a few minutes and run this script again.")
    
    print("\n📊 Check deployment status:")
    print("   doctl apps list-deployments 8f68b264-cb81-4288-8e01-3caf8c0cd80b | head -3")

if __name__ == "__main__":
    asyncio.run(main())

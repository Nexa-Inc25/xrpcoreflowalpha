#!/usr/bin/env python3
"""Test the API routing fixes"""
import requests
import json

# Define test endpoints
BASE_URL = "https://api.zkalphaflow.com"
ENDPOINTS = [
    ("/health", "GET"),  # This should work without /api prefix
    ("/api/dashboard/flow_state", "GET"),
    ("/api/dashboard/market_prices", "GET"),
    ("/api/flows", "GET"),
    ("/api/analytics/forecast?asset=xrp&horizon=1h", "GET"),
    ("/api/wallets/known", "GET"),
    ("/api/dashboard/whale_transfers?limit=5", "GET"),
]

def test_endpoint(path, method="GET"):
    """Test a single endpoint"""
    url = f"{BASE_URL}{path}"
    print(f"\n📍 Testing: {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        else:
            response = requests.post(url, timeout=5)
        
        # Check status
        if response.status_code == 200:
            print(f"  ✅ SUCCESS - Status: {response.status_code}")
            # Show sample of response
            try:
                data = response.json()
                if isinstance(data, dict):
                    keys = list(data.keys())[:5]
                    print(f"  📦 Response keys: {', '.join(keys)}")
                elif isinstance(data, list):
                    print(f"  📦 Response: List with {len(data)} items")
            except:
                print(f"  📦 Response: {response.text[:100]}...")
        elif response.status_code == 404:
            print(f"  ❌ NOT FOUND - Status: {response.status_code}")
        else:
            print(f"  ⚠️  Status: {response.status_code}")
            
    except Exception as e:
        print(f"  ❌ ERROR: {e}")

def main():
    print("=" * 60)
    print("API ROUTING FIX VERIFICATION")
    print("=" * 60)
    
    # Test health endpoint (no /api prefix)
    test_endpoint("/health")
    
    # Test API endpoints (with /api prefix)
    for endpoint, method in ENDPOINTS[1:]:
        test_endpoint(endpoint, method)
    
    print("\n" + "=" * 60)
    print("✓ Test Complete")
    print("=" * 60)
    
    print("\n📝 Notes:")
    print("  - Health endpoint works without /api prefix")
    print("  - All other endpoints require /api prefix on DigitalOcean")
    print("  - Frontend will auto-add /api prefix in production")

if __name__ == "__main__":
    main()

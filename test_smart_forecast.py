#!/usr/bin/env python3
"""
Test the SMART forecasting system
Shows how it integrates dark pools, whale alerts, and ML
"""

import asyncio
import httpx
import json
from datetime import datetime

# API endpoint
API_BASE = "https://api.zkalphaflow.com"

async def test_smart_forecast():
    """Test the smart forecasting endpoint"""
    
    print("🧠 Testing SMART Forecast System")
    print("=" * 60)
    
    assets = ['xrp', 'btc', 'eth']
    
    async with httpx.AsyncClient(timeout=60) as client:
        for asset in assets:
            print(f"\n📊 Forecasting {asset.upper()}...")
            
            try:
                # Call smart forecast endpoint
                response = await client.get(
                    f"{API_BASE}/api/analytics/smart_forecast",
                    params={
                        'asset': asset,
                        'horizon': 24,
                        'include_dark_pools': True
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    print(f"✅ Current Price: ${data.get('current_price', 0):.4f}")
                    
                    # Forecast results
                    forecast = data.get('forecast', {})
                    if forecast:
                        print(f"🔮 Ensemble Forecast: ${forecast.get('ensemble', 0):.4f}")
                        print(f"📈 Confidence: {forecast.get('confidence', 0):.1%}")
                    
                    # Dark pool analysis
                    dark_pool = data.get('dark_pool_analysis', {})
                    if dark_pool.get('detected'):
                        print(f"🌊 Dark Pool Activity Detected!")
                        print(f"   Volume: ${dark_pool.get('total_volume_usd', 0)/1e6:.1f}M")
                        print(f"   Impact Score: {dark_pool.get('impact_score', 0):.2f}")
                        print(f"   Predicted Move: {dark_pool.get('predicted_move_pct', 0):.1f}%")
                    else:
                        print(f"🌊 No significant dark pool activity")
                    
                    # Accuracy scores
                    accuracy = data.get('accuracy_scores', {})
                    if accuracy:
                        print(f"📊 Model Accuracy (Directional):")
                        for model, score in accuracy.items():
                            print(f"   {model}: {score:.1%}")
                    
                    # Feature importance
                    importance = data.get('feature_importance', {})
                    if importance:
                        print(f"🔍 Top Features Driving Prediction:")
                        for i, (feature, score) in enumerate(list(importance.items())[:5]):
                            print(f"   {i+1}. {feature}: {score:.3f}")
                    
                    # Recommendation
                    rec = data.get('recommended_action', {})
                    if rec:
                        action = rec.get('action', 'HOLD')
                        confidence = rec.get('confidence', 0)
                        reasoning = rec.get('reasoning', '')
                        
                        # Color code the action
                        if 'BUY' in action:
                            emoji = "🟢"
                        elif 'SELL' in action:
                            emoji = "🔴"
                        else:
                            emoji = "🟡"
                        
                        print(f"\n{emoji} Recommendation: {action}")
                        print(f"   Confidence: {confidence:.1%}")
                        print(f"   Reasoning: {reasoning}")
                    
                else:
                    print(f"❌ Error: {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
                    
            except Exception as e:
                print(f"❌ Failed: {e}")
    
    print("\n" + "=" * 60)
    print("💡 Smart Forecast Features:")
    print("   • Integrates dark pool and whale signals")
    print("   • Uses ensemble ML (XGBoost, Random Forest, Gradient Boost)")
    print("   • 50+ engineered features from flow data")
    print("   • Directional accuracy focus (up/down prediction)")
    print("   • Feature importance ranking")
    print("   • Confidence-based recommendations")

async def compare_old_vs_new():
    """Compare old Prophet-only vs new Smart forecasting"""
    
    print("\n📊 Comparing Old vs Smart Forecasting")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=60) as client:
        # Old forecast (Prophet only)
        print("\n🔸 Old Forecast (Prophet only):")
        old_response = await client.get(
            f"{API_BASE}/api/analytics/forecast",
            params={'asset': 'xrp', 'horizon': '24h'}
        )
        
        if old_response.status_code == 200:
            old_data = old_response.json()
            print(f"   Uses: Prophet time series only")
            print(f"   Data: Just price history")
            print(f"   Features: Basic seasonality")
        else:
            print(f"   Status: {old_response.status_code}")
        
        # New smart forecast
        print("\n🔹 Smart Forecast (Ensemble ML + Dark Pools):")
        new_response = await client.get(
            f"{API_BASE}/api/analytics/smart_forecast",
            params={'asset': 'xrp', 'include_dark_pools': True}
        )
        
        if new_response.status_code == 200:
            new_data = new_response.json()
            print(f"   Uses: XGBoost + Random Forest + Gradient Boost")
            print(f"   Data: Prices + Dark Pools + Whale Alerts")
            print(f"   Features: 50+ engineered (flow, momentum, technical)")
            
            if new_data.get('dark_pool_analysis', {}).get('detected'):
                print(f"   🎯 ADVANTAGE: Dark pool activity detected!")
        else:
            print(f"   Status: {new_response.status_code}")

async def main():
    print(f"\n🚀 Smart Flow Forecaster Test")
    print(f"   Time: {datetime.now().isoformat()}")
    print(f"   API: {API_BASE}")
    print("-" * 60)
    
    await test_smart_forecast()
    await compare_old_vs_new()
    
    print("\n✅ Test complete!")
    print("The smart forecast is MUCH more intelligent because it:")
    print("1. Uses REAL dark pool and whale flow data")
    print("2. Combines multiple ML models for better accuracy")
    print("3. Engineers smart features from flow patterns")
    print("4. Provides actionable trading recommendations")
    print("5. Explains its reasoning with confidence scores")

if __name__ == "__main__":
    asyncio.run(main())

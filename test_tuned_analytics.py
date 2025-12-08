#!/usr/bin/env python3
"""
Test script for fine-tuned analytics
Demonstrates HMM, Fourier, and Prophet integration
"""

import asyncio
import requests
import json
from datetime import datetime

# API base URL (adjust for your deployment)
API_BASE = "http://localhost:8000"  # Local testing
# API_BASE = "https://api.zkalphaflow.com"  # Production

async def test_integrated_forecast():
    """Test integrated forecast with all models"""
    print("\n🔮 Testing Integrated Forecast (HMM + Fourier + Prophet)")
    print("=" * 60)
    
    response = requests.get(
        f"{API_BASE}/analytics/forecast",
        params={
            "asset": "xrp",
            "correlate_with": "equities",
            "horizon": 24,
            "tune": "all",  # Use all models
            "confidence_level": 0.95
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Accuracy: {data.get('accuracy', 0) * 100:.1f}%")
        print(f"📈 XRP Migration Score: {data.get('xrp_migration_score', 0) * 100:.1f}%")
        
        # Show top signals
        signals = data.get('signals', [])
        if signals:
            print(f"\n🎯 Top Trading Signals:")
            for signal in signals[:3]:
                print(f"  • {signal['type']}: {signal['action']} {signal['asset']}")
                print(f"    Confidence: {signal['confidence'] * 100:.1f}%")
                print(f"    Reason: {signal['reason']}")
        
        # Show sample forecast
        forecast = data.get('forecast', [])
        if forecast and len(forecast) > 0:
            sample = forecast[0]
            print(f"\n📊 Next Hour Prediction:")
            print(f"  • Price: ${sample['prediction']:.4f}")
            print(f"  • Confidence: {sample['confidence'] * 100:.1f}%")
            print(f"  • HMM State: {sample['hmm_state']}")
            print(f"  • Fourier Cycle: {sample['fourier_cycle']}")
            print(f"  • Prophet Trend: {sample['prophet_trend']}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)


async def test_hmm_flow_state():
    """Test HMM flow state analysis"""
    print("\n🔄 Testing HMM Flow State Analysis")
    print("=" * 60)
    
    response = requests.get(
        f"{API_BASE}/analytics/flow_state",
        params={
            "venue": "ripple,nyse",
            "tune": "hmm",
            "window": 100
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        venues = data.get('venues', {})
        
        for venue, state in venues.items():
            print(f"\n📍 Venue: {venue.upper()}")
            print(f"  • Current State: {state.get('current_state', 'Unknown')}")
            print(f"  • Migration Probability: {state.get('migration_probability', 0) * 100:.1f}%")
            print(f"  • Manipulation Score: {state.get('manipulation_score', 0) * 100:.1f}%")
            print(f"  • Confidence: {state.get('confidence', 0) * 100:.1f}%")
    else:
        print(f"❌ Error: {response.status_code}")


async def test_fourier_correlations():
    """Test Fourier correlation analysis"""
    print("\n🌊 Testing Fourier Correlation Analysis")
    print("=" * 60)
    
    response = requests.get(
        f"{API_BASE}/analytics/correlations",
        params={
            "assets": "xrp,btc,eth,spy",
            "tune": "fourier",
            "window": 1440  # 24 hours
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        correlations = data.get('fourier_correlations', {})
        
        print(f"📊 Frequency-Domain Correlations:")
        for pair, corr in correlations.items():
            print(f"\n  {pair}:")
            print(f"    • Magnitude Correlation: {corr.get('magnitude_correlation', 0):.3f}")
            print(f"    • Phase Coherence: {corr.get('phase_coherence', 0):.3f}")
            print(f"    • Synchronized: {'✅' if corr.get('synchronized') else '❌'}")
            
            manip_freqs = corr.get('manipulation_frequencies', [])
            if manip_freqs:
                print(f"    • Manipulation Frequencies: {manip_freqs[:3]}")
        
        # XRP metrics
        xrp_metrics = data.get('xrp_metrics', {})
        if xrp_metrics:
            print(f"\n🎯 XRP Focus Metrics:")
            print(f"  • Average Phase Coherence: {xrp_metrics.get('average_phase_coherence', 0):.3f}")
            print(f"  • Decorrelation Detected: {'✅' if xrp_metrics.get('decorrelation_detected') else '❌'}")
    else:
        print(f"❌ Error: {response.status_code}")


async def test_prophet_forecast():
    """Test Prophet-only forecast with optimization"""
    print("\n📈 Testing Prophet Forecast with Hyperparameter Tuning")
    print("=" * 60)
    
    response = requests.get(
        f"{API_BASE}/analytics/forecast",
        params={
            "asset": "xrp",
            "horizon": 24,
            "tune": "prophet",
            "confidence_level": 0.95
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        optimization = data.get('optimization', {})
        
        print(f"🔧 Optimization Results:")
        print(f"  • Best Score: {optimization.get('best_score', 0):.4f}")
        print(f"  • Metric: {optimization.get('metric', 'unknown')}")
        
        best_params = optimization.get('best_params', {})
        if best_params:
            print(f"\n📐 Best Parameters:")
            for param, value in best_params.items():
                print(f"  • {param}: {value}")
        
        # Show forecast sample
        forecast = data.get('forecast', [])
        if forecast and len(forecast) > 0:
            print(f"\n📊 24-Hour Forecast Summary:")
            prices = [f['prediction'] for f in forecast]
            print(f"  • Min Price: ${min(prices):.4f}")
            print(f"  • Max Price: ${max(prices):.4f}")
            print(f"  • Avg Price: ${sum(prices)/len(prices):.4f}")
    else:
        print(f"❌ Error: {response.status_code}")


async def test_realtime_signals():
    """Test real-time signal generation"""
    print("\n⚡ Testing Real-Time Trading Signals")
    print("=" * 60)
    
    response = requests.get(
        f"{API_BASE}/analytics/signals/realtime",
        params={
            "tune": "all",
            "min_confidence": 0.7
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"📡 Real-Time Signal Status:")
        print(f"  • Total Signals: {data.get('total_signals', 0)}")
        print(f"  • Model Accuracy: {data.get('accuracy', 0) * 100:.1f}%")
        print(f"  • XRP Migration Score: {data.get('xrp_migration_score', 0) * 100:.1f}%")
        
        signals = data.get('signals', [])
        if signals:
            print(f"\n🎯 Active Signals:")
            for signal in signals:
                print(f"\n  📍 {signal['type']}")
                print(f"    • Asset: {signal['asset']}")
                print(f"    • Action: {signal['action']}")
                print(f"    • Confidence: {signal['confidence'] * 100:.1f}%")
                print(f"    • Risk Level: {signal['risk_level']}")
                print(f"    • Reason: {signal['reason']}")
        else:
            print("\n  ℹ️ No signals above confidence threshold")
    else:
        print(f"❌ Error: {response.status_code}")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🚀 TESTING FINE-TUNED MARKOV, FOURIER & PROPHET ANALYTICS")
    print("=" * 60)
    print(f"📍 API Endpoint: {API_BASE}")
    print(f"🕐 Timestamp: {datetime.now().isoformat()}")
    
    # Run tests sequentially
    await test_integrated_forecast()
    await test_hmm_flow_state()
    await test_fourier_correlations()
    await test_prophet_forecast()
    await test_realtime_signals()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

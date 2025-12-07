"""
Wallet Analysis API - Trace Institutional Wallet Activity

Exposes endpoints to analyze wallets from fingerprinted algorithms
for potential wrapped securities, FTD patterns, and suspicious timing.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, HTTPException

router = APIRouter()


@router.get("/wallet/analyze/{address}")
async def analyze_wallet(
    address: str,
    include_tokens: bool = Query(True, description="Include token transfers"),
    include_internal: bool = Query(True, description="Include internal transactions"),
) -> Dict[str, Any]:
    """
    Analyze an Ethereum wallet for suspicious patterns.
    
    Detects:
    - Wrapped securities tokens (synthetic stocks)
    - Settlement timing patterns (T+2 correlation)
    - Options expiry timing
    - Large stablecoin movements
    """
    if not address.startswith("0x") or len(address) != 42:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")
    
    try:
        from services.wallet_tracker import wallet_tracker
        result = await wallet_tracker.analyze_wallet(
            address, 
            include_tokens=include_tokens,
            include_internal=include_internal
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/wallet/fingerprint/{algo_name}")
async def analyze_fingerprint_wallets(
    algo_name: str,
) -> Dict[str, Any]:
    """
    Analyze all known wallets for a fingerprinted algorithm.
    
    Returns analysis for each known wallet associated with the algorithm.
    """
    try:
        from api.dashboard import ALGO_PROFILES
        from services.wallet_tracker import wallet_tracker
        
        profile = ALGO_PROFILES.get(algo_name)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Algorithm '{algo_name}' not found")
        
        wallets = profile.get("known_wallets", [])
        if not wallets:
            return {
                "algo_name": algo_name,
                "display_name": profile.get("display_name"),
                "message": "No known wallets for this algorithm",
                "wallets": [],
            }
        
        # Analyze each ETH wallet
        results = []
        for wallet in wallets:
            if wallet.startswith("0x"):
                try:
                    result = await wallet_tracker.analyze_wallet(wallet)
                    result["algo_name"] = algo_name
                    results.append(result)
                except Exception as e:
                    results.append({
                        "address": wallet,
                        "error": str(e),
                    })
        
        # Aggregate flags
        total_flags = sum(r.get("flags", {}).get("total_flags", 0) for r in results if "flags" in r)
        
        return {
            "algo_name": algo_name,
            "display_name": profile.get("display_name"),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "wallet_count": len(results),
            "total_flags": total_flags,
            "wallets": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/wallet/flags/summary")
async def get_all_flagged_activity() -> Dict[str, Any]:
    """
    Get summary of all flagged activity across known institutional wallets.
    """
    try:
        from api.dashboard import ALGO_PROFILES
        from services.wallet_tracker import wallet_tracker
        
        all_flags = []
        analyzed_wallets = 0
        
        for algo_name, profile in ALGO_PROFILES.items():
            wallets = profile.get("known_wallets", [])
            for wallet in wallets:
                if wallet.startswith("0x"):
                    try:
                        result = await wallet_tracker.analyze_wallet(wallet, include_internal=False)
                        analyzed_wallets += 1
                        
                        # Collect flags with algo attribution
                        for flag in result.get("flags", {}).get("wrapped_securities", []):
                            flag["algo"] = algo_name
                            flag["algo_display"] = profile.get("display_name")
                            all_flags.append(flag)
                        
                        for flag in result.get("flags", {}).get("settlement_timing", []):
                            flag["algo"] = algo_name
                            flag["algo_display"] = profile.get("display_name")
                            all_flags.append(flag)
                    except Exception:
                        pass
        
        # Sort by timestamp (most recent first)
        all_flags.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "wallets_analyzed": analyzed_wallets,
            "total_flags": len(all_flags),
            "flags": all_flags[:50],  # Top 50 most recent
            "flag_breakdown": {
                "wrapped_securities": len([f for f in all_flags if f.get("flag") in ["POTENTIAL_WRAPPED_SECURITY", "LARGE_STABLECOIN_MOVEMENT"]]),
                "timing_suspicious": len([f for f in all_flags if f.get("flag") in ["MARKET_HOURS_TIMING", "OPTIONS_EXPIRY_TIMING"]]),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary failed: {str(e)}")

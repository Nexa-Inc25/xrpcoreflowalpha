"""
Outcome Checker Worker

Runs periodically to check signal outcomes at various intervals (1h, 4h, 12h, 24h).
Fetches current prices and compares to entry prices to determine if predictions were correct.
"""
import asyncio
from typing import List

from db.signals import get_signals_pending_outcome, store_outcome
from utils.price import get_price_usd

# Intervals to check (in hours)
CHECK_INTERVALS = [1, 4, 12, 24]

# How often to run the checker (seconds)
CHECK_FREQUENCY = 300  # 5 minutes


async def check_outcomes_for_interval(interval_hours: int) -> int:
    """
    Check outcomes for all signals pending at this interval.
    Returns number of outcomes processed.
    """
    signals = await get_signals_pending_outcome(interval_hours, limit=50)
    
    if not signals:
        return 0
    
    # Get current prices once for all signals
    try:
        current_xrp = await get_price_usd("xrp")
        current_eth = await get_price_usd("eth")
    except Exception as e:
        print(f"[OutcomeChecker] Failed to get prices: {e}")
        return 0
    
    processed = 0
    for signal in signals:
        try:
            success = await store_outcome(
                signal_id=signal["signal_id"],
                interval_hours=interval_hours,
                price_xrp=current_xrp,
                price_eth=current_eth,
                entry_price_xrp=signal.get("entry_price_xrp") or 0,
                entry_price_eth=signal.get("entry_price_eth") or 0,
                predicted_direction=signal.get("predicted_direction", "neutral"),
                predicted_move_pct=signal.get("predicted_move_pct") or 0
            )
            if success:
                processed += 1
        except Exception as e:
            print(f"[OutcomeChecker] Error processing signal {signal.get('signal_id')}: {e}")
    
    return processed


async def run_outcome_checker():
    """
    Main worker loop. Continuously checks for pending outcomes.
    """
    print("[OutcomeChecker] Starting outcome checker worker")
    
    while True:
        try:
            total_processed = 0
            
            for interval in CHECK_INTERVALS:
                processed = await check_outcomes_for_interval(interval)
                total_processed += processed
                
                if processed > 0:
                    print(f"[OutcomeChecker] Processed {processed} outcomes for {interval}h interval")
            
            if total_processed > 0:
                print(f"[OutcomeChecker] Total outcomes processed: {total_processed}")
            
        except Exception as e:
            print(f"[OutcomeChecker] Worker error: {e}")
        
        await asyncio.sleep(CHECK_FREQUENCY)


async def start_outcome_checker():
    """Entry point to start the outcome checker as a background task."""
    asyncio.create_task(run_outcome_checker())
    print("[OutcomeChecker] Worker started")

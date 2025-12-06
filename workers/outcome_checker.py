"""
Outcome Checker Worker

Runs periodically to check signal outcomes at various intervals (1h, 4h, 12h, 24h).
Fetches current prices and compares to entry prices to determine if predictions were correct.
"""
import asyncio
from typing import List, Optional, Tuple

from db.signals import get_signals_pending_outcome, store_outcome
from utils.price import get_price_usd

# Intervals to check (in hours)
CHECK_INTERVALS = [1, 4, 12, 24]

# How often to run the checker (seconds)
CHECK_FREQUENCY = 300  # 5 minutes

# Error backoff
MAX_CONSECUTIVE_ERRORS = 5
ERROR_BACKOFF_SECONDS = 60


async def fetch_prices_with_retry(max_retries: int = 3) -> Optional[Tuple[float, float]]:
    """Fetch prices with retry logic."""
    for attempt in range(max_retries):
        try:
            xrp = await get_price_usd("xrp")
            eth = await get_price_usd("eth")
            if xrp > 0 and eth > 0:
                return (xrp, eth)
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[OutcomeChecker] Price fetch failed after {max_retries} attempts: {e}")
            else:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return None


async def check_outcomes_for_interval(interval_hours: int) -> int:
    """
    Check outcomes for all signals pending at this interval.
    Returns number of outcomes processed.
    """
    signals = await get_signals_pending_outcome(interval_hours, limit=50)
    
    if not signals:
        return 0
    
    # Get current prices with retry
    prices = await fetch_prices_with_retry()
    if not prices:
        return 0
    
    current_xrp, current_eth = prices
    
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
    Includes error backoff to prevent runaway loops on persistent failures.
    """
    print("[OutcomeChecker] Starting outcome checker worker")
    consecutive_errors = 0
    
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
            
            # Reset error count on success
            consecutive_errors = 0
            
        except Exception as e:
            consecutive_errors += 1
            print(f"[OutcomeChecker] Worker error ({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): {e}")
            
            # Backoff on repeated errors
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                print(f"[OutcomeChecker] Too many errors, backing off for {ERROR_BACKOFF_SECONDS}s")
                await asyncio.sleep(ERROR_BACKOFF_SECONDS)
                consecutive_errors = 0
        
        await asyncio.sleep(CHECK_FREQUENCY)


async def start_outcome_checker():
    """Entry point to start the outcome checker as a background task."""
    asyncio.create_task(run_outcome_checker())
    print("[OutcomeChecker] Worker started")

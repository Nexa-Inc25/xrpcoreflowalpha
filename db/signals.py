"""
Signal storage and retrieval service.
Handles persisting signals with entry prices and fetching for analytics.
"""
import json
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db.connection import execute, fetch, fetchrow, fetchval, is_sqlite
from utils.price import get_price_usd


async def store_signal(signal: Dict[str, Any]) -> Optional[str]:
    """
    Store a signal with current entry prices.
    Returns the signal_id if successful, None otherwise.
    """
    try:
        # Generate unique signal ID
        raw_id = signal.get("tx_hash") or signal.get("id") or str(uuid.uuid4())
        signal_id = str(raw_id)
        # PostgreSQL schema uses VARCHAR(64) for signal_id.
        # Some sources (e.g. 0x + 64 hex chars) are 66 chars; hash to a stable 64.
        if len(signal_id) > 64:
            signal_id = hashlib.sha256(signal_id.encode("utf-8")).hexdigest()
        
        # Get current prices for entry snapshot
        try:
            entry_xrp = await get_price_usd("xrp")
            entry_eth = await get_price_usd("eth")
        except Exception:
            entry_xrp = 0.0
            entry_eth = 0.0
        
        # Extract signal fields
        sig_type = signal.get("type", "unknown")
        sub_type = signal.get("sub_type")
        network = signal.get("network") or signal.get("blockchain", "eth")
        summary = signal.get("summary", "")
        confidence = signal.get("confidence") or signal.get("iso_confidence") or 50
        predicted_dir = signal.get("direction") or signal.get("iso_direction", "neutral")
        predicted_move = signal.get("iso_expected_move_pct", 0.0)
        
        # USD value - check multiple field names used by different scanners
        amount_usd = (
            signal.get("amount_usd") or 
            signal.get("usd_value") or 
            signal.get("iso_amount_usd") or 
            0.0
        )
        
        # Native amount - check multiple field names
        amount_native = (
            signal.get("amount") or
            signal.get("amount_xrp") or 
            signal.get("amount_eth") or 
            0.0
        )
        
        # Determine native symbol
        symbol = signal.get("symbol", "")
        native_symbol = symbol if symbol else ("XRP" if "xrp" in sig_type.lower() else "ETH")
        
        # Source/destination addresses
        source = signal.get("source") or signal.get("from_address") or signal.get("from_owner", "")
        dest = signal.get("destination") or signal.get("to_address") or signal.get("to_owner", "")
        tx_hash = signal.get("tx_hash", "")
        tags = signal.get("tags", [])
        features = signal.get("features", {})
        
        # Insert into database - use appropriate syntax for SQLite vs PostgreSQL
        tags_str = json.dumps(tags) if isinstance(tags, list) else str(tags)
        features_str = json.dumps(features) if isinstance(features, dict) else str(features)
        
        if is_sqlite():
            await execute(
                """
                INSERT OR IGNORE INTO signals (
                    signal_id, type, sub_type, network, summary, confidence,
                    predicted_direction, predicted_move_pct, amount_usd, amount_native,
                    native_symbol, entry_price_xrp, entry_price_eth, entry_price_btc,
                    source_address, dest_address, tx_hash, tags, features
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                signal_id, sig_type, sub_type, network, summary, confidence,
                predicted_dir, predicted_move, amount_usd, amount_native,
                native_symbol, entry_xrp, entry_eth, 0.0,
                source, dest, tx_hash, tags_str, features_str
            )
        else:
            await execute(
                """
                INSERT INTO signals (
                    signal_id, type, sub_type, network, summary, confidence,
                    predicted_direction, predicted_move_pct, amount_usd, amount_native,
                    native_symbol, entry_price_xrp, entry_price_eth, entry_price_btc,
                    source_address, dest_address, tx_hash, tags, features
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19
                )
                ON CONFLICT (signal_id) DO NOTHING
                """,
                signal_id, sig_type, sub_type, network, summary, confidence,
                predicted_dir, predicted_move, amount_usd, amount_native,
                native_symbol, entry_xrp, entry_eth, 0.0,
                source, dest, tx_hash, tags, features_str
            )
        
        print(f"[DB] Stored signal {signal_id[:16]}... type={sig_type} conf={confidence}")
        return signal_id
        
    except Exception as e:
        print(f"[DB] Failed to store signal: {e}")
        return None


async def get_signals_pending_outcome(interval_hours: int, limit: int = 100) -> List[Dict]:
    """
    Get signals that need outcome checking for a specific interval.
    Returns signals where:
    - detected_at is at least `interval_hours` ago
    - no outcome exists for that interval yet
    """
    try:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=interval_hours)
        cutoff_sqlite = cutoff_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if using SQLite (different query syntax)
        if is_sqlite():
            rows = await fetch(
                """
                SELECT s.* FROM signals s
                LEFT JOIN signal_outcomes o 
                    ON s.signal_id = o.signal_id AND o.interval_hours = ?
                WHERE datetime(s.detected_at) <= datetime(?)
                    AND o.id IS NULL
                ORDER BY s.detected_at ASC
                LIMIT ?
                """,
                interval_hours, cutoff_sqlite, limit
            )
        else:
            rows = await fetch(
                """
                SELECT s.* FROM signals s
                LEFT JOIN signal_outcomes o 
                    ON s.signal_id = o.signal_id AND o.interval_hours = $1
                WHERE s.detected_at <= $2
                    AND o.id IS NULL
                ORDER BY s.detected_at ASC
                LIMIT $3
                """,
                interval_hours, cutoff_dt, limit
            )
        
        result = [dict(r) for r in rows]
        if result:
            print(f"[OutcomeChecker] Found {len(result)} pending signals for {interval_hours}h interval")
        return result
        
    except Exception as e:
        print(f"[DB] Failed to get pending signals for {interval_hours}h: {e}")
        return []


async def store_outcome(
    signal_id: str,
    interval_hours: int,
    price_xrp: float,
    price_eth: float,
    entry_price_xrp: float,
    entry_price_eth: float,
    predicted_direction: str,
    predicted_move_pct: float
) -> bool:
    """
    Store the outcome for a signal at a specific interval.
    Calculates whether the prediction was a hit.
    """
    try:
        # Calculate actual changes
        xrp_change = ((price_xrp - entry_price_xrp) / entry_price_xrp * 100) if entry_price_xrp > 0 else 0
        eth_change = ((price_eth - entry_price_eth) / entry_price_eth * 100) if entry_price_eth > 0 else 0
        
        # Determine if prediction was correct
        # A "hit" is when direction matches and move is >= 50% of predicted
        primary_change = xrp_change  # Default to XRP for XRPL-centric tracker
        
        # Map direction aliases
        dir_up = predicted_direction in ("up", "bullish", "long")
        dir_down = predicted_direction in ("down", "bearish", "short")
        
        hit = False
        if dir_up and primary_change > 0:
            hit = primary_change >= (predicted_move_pct * 0.5)
        elif dir_down and primary_change < 0:
            hit = abs(primary_change) >= (abs(predicted_move_pct) * 0.5)
        elif predicted_direction == "neutral":
            hit = abs(primary_change) < 1.0  # Less than 1% move is correct for neutral
        
        # Use SQLite-compatible INSERT OR REPLACE
        if is_sqlite():
            await execute(
                """
                INSERT OR REPLACE INTO signal_outcomes (
                    signal_id, interval_hours, price_xrp, price_eth, price_btc,
                    xrp_change_pct, eth_change_pct, btc_change_pct, hit, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                signal_id, interval_hours, price_xrp, price_eth, 0.0,
                xrp_change, eth_change, 0.0, 1 if hit else 0
            )
        else:
            await execute(
                """
                INSERT INTO signal_outcomes (
                    signal_id, interval_hours, price_xrp, price_eth, price_btc,
                    xrp_change_pct, eth_change_pct, btc_change_pct, hit
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (signal_id, interval_hours) DO UPDATE SET
                    price_xrp = EXCLUDED.price_xrp,
                    price_eth = EXCLUDED.price_eth,
                    xrp_change_pct = EXCLUDED.xrp_change_pct,
                    eth_change_pct = EXCLUDED.eth_change_pct,
                    hit = EXCLUDED.hit,
                    checked_at = NOW()
                """,
                signal_id, interval_hours, price_xrp, price_eth, 0.0,
                xrp_change, eth_change, 0.0, hit
            )
        
        print(f"[Outcome] {signal_id[:12]}... {interval_hours}h: XRP {xrp_change:+.2f}% hit={hit}")
        return True
        
    except Exception as e:
        print(f"[DB] Failed to store outcome: {e}")
        return False


async def get_analytics_summary(days: int = 30) -> Dict[str, Any]:
    """
    Get aggregated analytics for the specified period.
    Returns win rates, daily performance, and signal breakdowns.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()  # For SQLite TEXT comparison
        
        # Use different queries for SQLite vs PostgreSQL
        use_sqlite = is_sqlite()
        
        # Total signals and outcomes
        if use_sqlite:
            total_signals = await fetchval(
                "SELECT COUNT(*) FROM signals WHERE detected_at >= ?", cutoff_str
            ) or 0
        else:
            total_signals = await fetchval(
                "SELECT COUNT(*) FROM signals WHERE detected_at >= $1", cutoff
            ) or 0
        
        # Win rates by confidence tier
        if use_sqlite:
            # SQLite uses 1/0 for boolean, not true/false
            win_rate_query = """
                SELECT 
                    CASE 
                        WHEN s.confidence >= 70 THEN 'high'
                        WHEN s.confidence >= 50 THEN 'medium'
                        ELSE 'low'
                    END as tier,
                    COUNT(DISTINCT s.signal_id) as total,
                    COUNT(DISTINCT CASE WHEN o.hit = 1 THEN s.signal_id END) as hits
                FROM signals s
                LEFT JOIN signal_outcomes o ON s.signal_id = o.signal_id AND o.interval_hours = 4
                WHERE s.detected_at >= ?
                GROUP BY tier
            """
            tier_rows = await fetch(win_rate_query, cutoff_str)
        else:
            win_rate_query = """
                SELECT 
                    CASE 
                        WHEN s.confidence >= 70 THEN 'high'
                        WHEN s.confidence >= 50 THEN 'medium'
                        ELSE 'low'
                    END as tier,
                    COUNT(DISTINCT s.signal_id) as total,
                    COUNT(DISTINCT CASE WHEN o.hit = true THEN s.signal_id END) as hits
                FROM signals s
                LEFT JOIN signal_outcomes o ON s.signal_id = o.signal_id AND o.interval_hours = 4
                WHERE s.detected_at >= $1
                GROUP BY tier
            """
            tier_rows = await fetch(win_rate_query, cutoff)
        
        win_rates = {"high": {"total": 0, "hits": 0, "rate": 0}, 
                     "medium": {"total": 0, "hits": 0, "rate": 0},
                     "low": {"total": 0, "hits": 0, "rate": 0}}
        for row in tier_rows:
            tier = row["tier"]
            total = row["total"] or 0
            hits = row["hits"] or 0
            rate = round((hits / total * 100), 1) if total > 0 else 0
            win_rates[tier] = {"total": total, "hits": hits, "rate": rate}
        
        # Daily performance
        if use_sqlite:
            daily_query = """
                SELECT 
                    DATE(s.detected_at) as date,
                    COUNT(DISTINCT s.signal_id) as signals,
                    COUNT(DISTINCT CASE WHEN o.hit = 1 THEN s.signal_id END) as hits,
                    COALESCE(SUM(s.amount_usd), 0) as total_volume,
                    COALESCE(AVG(o.xrp_change_pct), 0) as avg_impact
                FROM signals s
                LEFT JOIN signal_outcomes o ON s.signal_id = o.signal_id AND o.interval_hours = 4
                WHERE s.detected_at >= ?
                GROUP BY DATE(s.detected_at)
                ORDER BY date DESC
                LIMIT 30
            """
            daily_rows = await fetch(daily_query, cutoff_str)
        else:
            daily_query = """
                SELECT 
                    DATE(s.detected_at) as date,
                    COUNT(DISTINCT s.signal_id) as signals,
                    COUNT(DISTINCT CASE WHEN o.hit = true THEN s.signal_id END) as hits,
                    COALESCE(SUM(s.amount_usd), 0) as total_volume,
                    COALESCE(AVG(o.xrp_change_pct), 0) as avg_impact
                FROM signals s
                LEFT JOIN signal_outcomes o ON s.signal_id = o.signal_id AND o.interval_hours = 4
                WHERE s.detected_at >= $1
                GROUP BY DATE(s.detected_at)
                ORDER BY date DESC
                LIMIT 30
            """
            daily_rows = await fetch(daily_query, cutoff)
        
        daily_performance = []
        for row in daily_rows:
            signals = row["signals"] or 0
            hits = row["hits"] or 0
            date_val = row["date"]
            date_str = date_val.isoformat() if hasattr(date_val, 'isoformat') else str(date_val) if date_val else ""
            daily_performance.append({
                "date": date_str,
                "signals": signals,
                "hits": hits,
                "hitRate": round((hits / signals * 100), 1) if signals > 0 else 0,
                "totalVolume": float(row["total_volume"] or 0),
                "avgImpact": float(row["avg_impact"] or 0)
            })
        
        # Signal type breakdown
        if use_sqlite:
            type_query = """
                SELECT type, COUNT(*) as count
                FROM signals
                WHERE detected_at >= ?
                GROUP BY type
                ORDER BY count DESC
                LIMIT 10
            """
            type_rows = await fetch(type_query, cutoff_str)
        else:
            type_query = """
                SELECT type, COUNT(*) as count
                FROM signals
                WHERE detected_at >= $1
                GROUP BY type
                ORDER BY count DESC
                LIMIT 10
            """
            type_rows = await fetch(type_query, cutoff)
        type_breakdown = {row["type"]: row["count"] for row in type_rows}
        
        # Top performing signals (highest actual moves)
        if use_sqlite:
            top_query = """
                SELECT s.*, o.xrp_change_pct, o.hit
                FROM signals s
                JOIN signal_outcomes o ON s.signal_id = o.signal_id AND o.interval_hours = 4
                WHERE s.detected_at >= ? AND o.hit = 1
                ORDER BY ABS(o.xrp_change_pct) DESC
                LIMIT 5
            """
            top_rows = await fetch(top_query, cutoff_str)
        else:
            top_query = """
                SELECT s.*, o.xrp_change_pct, o.hit
                FROM signals s
                JOIN signal_outcomes o ON s.signal_id = o.signal_id AND o.interval_hours = 4
                WHERE s.detected_at >= $1 AND o.hit = true
                ORDER BY ABS(o.xrp_change_pct) DESC
                LIMIT 5
            """
            top_rows = await fetch(top_query, cutoff)
        top_signals = []
        for i, row in enumerate(top_rows):
            detected_val = row["detected_at"]
            detected_str = detected_val.isoformat() if hasattr(detected_val, 'isoformat') else str(detected_val) if detected_val else ""
            top_signals.append({
                "id": i + 1,
                "type": row["type"],
                "summary": row["summary"],
                "confidence": row["confidence"],
                "actual_move": round(row["xrp_change_pct"] or 0, 2),
                "detected_at": detected_str
            })
        
        return {
            "period_days": days,
            "total_signals": total_signals,
            "win_rates": win_rates,
            "daily_performance": daily_performance,
            "type_breakdown": type_breakdown,
            "top_signals": top_signals,
            "computed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"[DB] Failed to get analytics: {e}")
        return {
            "period_days": days,
            "total_signals": 0,
            "win_rates": {"high": {"total": 0, "hits": 0, "rate": 0}, 
                         "medium": {"total": 0, "hits": 0, "rate": 0},
                         "low": {"total": 0, "hits": 0, "rate": 0}},
            "daily_performance": [],
            "type_breakdown": {},
            "top_signals": [],
            "error": str(e)
        }

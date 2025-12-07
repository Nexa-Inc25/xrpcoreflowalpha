"""
Institutional Wallet Tracker - Detect Wrapped Securities & Suspicious Patterns

Traces transactions from fingerprinted institutional wallets to detect:
- Wrapped securities (tokens mirroring equity tickers)
- FTD hiding patterns around settlement dates
- Cross-chain obfuscation
- Suspicious timing with equity markets
"""
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import os
import re
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# API Keys
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
DUNE_API_KEY = os.getenv("DUNE_API_KEY", "")

print(f"[WalletTracker] Etherscan key loaded: {'YES' if ETHERSCAN_API_KEY else 'NO'}")
print(f"[WalletTracker] Dune key loaded: {'YES' if DUNE_API_KEY else 'NO'}")

# Known wrapped securities tokens (add more as discovered)
WRAPPED_SECURITIES = {
    # Synthetix synthetic stocks
    "0x": "Generic wrapped",
    # Mirror Protocol (Terra) - now defunct but patterns persist
    # FTX wrapped stocks - defunct
    # Known wrapper contracts
}

# Suspicious token name patterns
SUSPICIOUS_PATTERNS = [
    r"^[sw]?[A-Z]{1,5}$",  # sAAPL, wTSLA, AMZN
    r"wrapped.*stock",
    r"synthetic.*equity",
    r"mirror.*[A-Z]{2,5}",
    r"^m[A-Z]{2,5}$",  # mAAPL, mTSLA
]

# T+2 settlement - crypto moves before equity settlement
EQUITY_SETTLEMENT_DAYS = 2

# Options expiry - 3rd Friday of each month
def get_monthly_expiry(year: int, month: int) -> datetime:
    """Get the 3rd Friday of a given month (options expiry)."""
    import calendar
    cal = calendar.Calendar()
    fridays = [d for d in cal.itermonthdays2(year, month) if d[0] != 0 and d[1] == 4]
    third_friday = fridays[2][0]
    return datetime(year, month, third_friday, tzinfo=timezone.utc)


class InstitutionalWalletTracker:
    """Track institutional wallet activity for suspicious patterns."""
    
    def __init__(self):
        # Etherscan V2 API endpoint
        self.etherscan_base = "https://api.etherscan.io/v2/api"
        self.cache: Dict[str, Any] = {}
        self._rate_limit_delay = 0.25  # 4 calls/sec to stay safe
    
    async def get_wallet_transactions(
        self, 
        address: str, 
        start_block: int = 0,
        end_block: int = 99999999,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch transaction history for a wallet."""
        params = {
            "chainid": "1",  # Ethereum mainnet
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": 1,
            "offset": limit,
            "sort": "desc",
        }
        if ETHERSCAN_API_KEY:
            params["apikey"] = ETHERSCAN_API_KEY
        
        async with httpx.AsyncClient(timeout=15) as client:
            await asyncio.sleep(self._rate_limit_delay)
            resp = await client.get(self.etherscan_base, params=params)
            data = resp.json()
            
            if data.get("status") == "1":
                return data.get("result", [])
            else:
                print(f"[WalletTracker] Etherscan error: {data.get('message')}")
                return []
    
    async def get_token_transfers(
        self,
        address: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch ERC-20 token transfers for a wallet."""
        params = {
            "chainid": "1",  # Ethereum mainnet
            "module": "account",
            "action": "tokentx",
            "address": address,
            "page": 1,
            "offset": limit,
            "sort": "desc",
        }
        if ETHERSCAN_API_KEY:
            params["apikey"] = ETHERSCAN_API_KEY
        
        async with httpx.AsyncClient(timeout=15) as client:
            await asyncio.sleep(self._rate_limit_delay)
            resp = await client.get(self.etherscan_base, params=params)
            data = resp.json()
            
            if data.get("status") == "1":
                return data.get("result", [])
            return []
    
    async def get_internal_transactions(
        self,
        address: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch internal transactions (contract calls)."""
        params = {
            "chainid": "1",  # Ethereum mainnet
            "module": "account",
            "action": "txlistinternal",
            "address": address,
            "page": 1,
            "offset": limit,
            "sort": "desc",
        }
        if ETHERSCAN_API_KEY:
            params["apikey"] = ETHERSCAN_API_KEY
        
        async with httpx.AsyncClient(timeout=15) as client:
            await asyncio.sleep(self._rate_limit_delay)
            resp = await client.get(self.etherscan_base, params=params)
            data = resp.json()
            
            if data.get("status") == "1":
                return data.get("result", [])
            return []
    
    def detect_wrapped_securities(
        self, 
        token_transfers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify potential wrapped securities tokens."""
        suspicious = []
        
        for tx in token_transfers:
            token_name = tx.get("tokenName", "")
            token_symbol = tx.get("tokenSymbol", "")
            
            # Check against known patterns
            for pattern in SUSPICIOUS_PATTERNS:
                if re.match(pattern, token_symbol, re.IGNORECASE):
                    suspicious.append({
                        "tx_hash": tx.get("hash"),
                        "token_name": token_name,
                        "token_symbol": token_symbol,
                        "token_address": tx.get("contractAddress"),
                        "value": int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18))),
                        "timestamp": datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=timezone.utc).isoformat(),
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "flag": "POTENTIAL_WRAPPED_SECURITY",
                        "pattern_matched": pattern,
                    })
                    break
            
            # Check for stablecoin movements (often used to settle)
            if token_symbol in ["USDC", "USDT", "DAI", "BUSD"]:
                value = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 6)))
                if value > 100_000:  # Large stablecoin moves
                    suspicious.append({
                        "tx_hash": tx.get("hash"),
                        "token_name": token_name,
                        "token_symbol": token_symbol,
                        "token_address": tx.get("contractAddress"),
                        "value": value,
                        "timestamp": datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=timezone.utc).isoformat(),
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "flag": "LARGE_STABLECOIN_MOVEMENT",
                        "note": f"${value:,.0f} stablecoin transfer - potential settlement",
                    })
        
        return suspicious
    
    def detect_settlement_timing(
        self,
        transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect transactions timed with equity settlement (T+2)."""
        suspicious = []
        
        # Get recent trading days
        now = datetime.now(timezone.utc)
        
        for tx in transactions:
            tx_time = datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=timezone.utc)
            
            # Check if transaction is near market open/close
            hour = tx_time.hour
            if hour in [13, 14, 20, 21]:  # 9-10 AM or 4-5 PM ET
                value_eth = int(tx.get("value", 0)) / 1e18
                if value_eth > 10:  # Significant ETH movement
                    suspicious.append({
                        "tx_hash": tx.get("hash"),
                        "value_eth": value_eth,
                        "timestamp": tx_time.isoformat(),
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "flag": "MARKET_HOURS_TIMING",
                        "note": f"Large transfer during equity market hours",
                    })
            
            # Check for options expiry proximity
            year, month = tx_time.year, tx_time.month
            expiry = get_monthly_expiry(year, month)
            days_to_expiry = abs((tx_time - expiry).days)
            
            if days_to_expiry <= 3:
                value_eth = int(tx.get("value", 0)) / 1e18
                if value_eth > 5:
                    suspicious.append({
                        "tx_hash": tx.get("hash"),
                        "value_eth": value_eth,
                        "timestamp": tx_time.isoformat(),
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "flag": "OPTIONS_EXPIRY_TIMING",
                        "note": f"Transaction {days_to_expiry} days from monthly options expiry",
                        "expiry_date": expiry.isoformat(),
                    })
        
        return suspicious
    
    async def analyze_wallet(
        self,
        address: str,
        include_tokens: bool = True,
        include_internal: bool = True
    ) -> Dict[str, Any]:
        """Full analysis of a wallet for suspicious activity."""
        address = address.lower()
        
        # Fetch all data
        txs = await self.get_wallet_transactions(address)
        
        token_txs = []
        if include_tokens:
            token_txs = await self.get_token_transfers(address)
        
        internal_txs = []
        if include_internal:
            internal_txs = await self.get_internal_transactions(address)
        
        # Run detection algorithms
        wrapped_flags = self.detect_wrapped_securities(token_txs)
        timing_flags = self.detect_settlement_timing(txs)
        
        # Calculate totals
        total_eth_in = sum(int(tx.get("value", 0)) for tx in txs if tx.get("to", "").lower() == address) / 1e18
        total_eth_out = sum(int(tx.get("value", 0)) for tx in txs if tx.get("from", "").lower() == address) / 1e18
        
        # Unique tokens
        unique_tokens = list(set(tx.get("tokenSymbol") for tx in token_txs if tx.get("tokenSymbol")))
        
        return {
            "address": address,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_transactions": len(txs),
                "total_token_transfers": len(token_txs),
                "total_internal_txs": len(internal_txs),
                "total_eth_received": round(total_eth_in, 4),
                "total_eth_sent": round(total_eth_out, 4),
                "unique_tokens": unique_tokens,
            },
            "flags": {
                "wrapped_securities": wrapped_flags,
                "settlement_timing": timing_flags,
                "total_flags": len(wrapped_flags) + len(timing_flags),
            },
            "recent_transactions": txs[:10],
            "recent_token_transfers": token_txs[:10],
            "etherscan_link": f"https://etherscan.io/address/{address}",
        }


# Singleton instance
wallet_tracker = InstitutionalWalletTracker()


async def analyze_institutional_wallet(address: str) -> Dict[str, Any]:
    """Public API to analyze a wallet."""
    return await wallet_tracker.analyze_wallet(address)


async def analyze_fingerprint_wallets(algo_name: str) -> List[Dict[str, Any]]:
    """Analyze all known wallets for a fingerprinted algorithm."""
    from api.dashboard import ALGO_PROFILES
    
    profile = ALGO_PROFILES.get(algo_name, {})
    wallets = profile.get("known_wallets", [])
    
    results = []
    for wallet in wallets:
        if wallet.startswith("0x"):  # Ethereum address
            result = await wallet_tracker.analyze_wallet(wallet)
            result["algo_name"] = algo_name
            results.append(result)
    
    return results

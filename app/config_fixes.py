"""
Configuration fixes for production deployment
Handles missing Redis and incorrect Yahoo Finance symbols
"""

import os

# Fix Redis URL issues - make Redis optional in production
REDIS_URL = os.getenv('REDIS_URL', '')
if not REDIS_URL or REDIS_URL == 'None' or not REDIS_URL.startswith(('redis://', 'rediss://')):
    # Disable Redis if URL is invalid or missing
    os.environ['REDIS_URL'] = ''
    os.environ['REDIS_OPTIONAL'] = 'true'
    print("[CONFIG] Redis disabled - running in-memory mode")

# Fix Yahoo Finance symbols - use correct ETF tickers
YAHOO_SYMBOL_MAP = {
    # Original -> Correct ticker
    'ES=F': 'SPY',     # Use SPY ETF instead of ES futures
    'NQ=F': 'QQQ',     # Use QQQ ETF instead of NQ futures
    '^GSPC': 'SPY',    # S&P 500 index -> SPY ETF
    '^NDX': 'QQQ',     # Nasdaq 100 index -> QQQ ETF
    'GC=F': 'GLD',     # Gold futures -> Gold ETF
    'CL=F': 'USO',     # Oil futures -> Oil ETF
    'SI=F': 'SLV',     # Silver futures -> Silver ETF
    'ZB=F': 'TLT',     # Bond futures -> Bond ETF
    'ZN=F': 'IEF',     # 10Y Note futures -> Treasury ETF
    'VIX': '^VIX',     # Keep VIX as is (index)
}

def fix_yahoo_symbol(symbol: str) -> str:
    """Convert futures/index symbols to ETF equivalents"""
    return YAHOO_SYMBOL_MAP.get(symbol.upper(), symbol)

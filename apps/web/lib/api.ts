const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';

function apiBaseTrimmed(): string {
  return API_BASE.replace(/\/$/, '');
}

export async function fetchUI(): Promise<any> {
  const res = await fetch(apiBaseTrimmed() + '/ui', {
    headers: {
      Accept: 'application/json',
    },
  });
  if (!res.ok) {
    throw new Error('Failed to fetch /ui');
  }
  return res.json();
}

export async function fetchFlowsByTx(txHash: string): Promise<any> {
  const url =
    apiBaseTrimmed() +
    `/flows?tx_hash=${encodeURIComponent(txHash)}&page_size=10`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    throw new Error('Failed to fetch /flows');
  }
  return res.json();
}

export async function fetchXrplFlowsHistory(): Promise<any> {
  const url =
    apiBaseTrimmed() +
    '/flows?types=xrp,trustline,orderbook,rwa_amm&page_size=100&window_seconds=86400';
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    throw new Error('Failed to fetch XRPL flows');
  }
  return res.json();
}

export async function fetchEthOhlcvLatest(): Promise<{
  open: number;
  high: number;
  low: number;
  volume: number;
}> {
  const res = await fetch(apiBaseTrimmed() + '/analytics/eth_ohlcv_latest', {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error('Failed to fetch ETH OHLCV');
  }
  return res.json();
}

export async function fetchEthCloseForecast(input: {
  open: number;
  high: number;
  low: number;
  volume: number;
}): Promise<{ predicted_close: number }> {
  const params = new URLSearchParams({
    open: input.open.toString(),
    high: input.high.toString(),
    low: input.low.toString(),
    volume: input.volume.toString(),
  });
  const res = await fetch(
    apiBaseTrimmed() + '/analytics/eth_close_forecast?' + params.toString(),
    { headers: { Accept: 'application/json' } },
  );
  if (!res.ok) {
    throw new Error('Failed to fetch ETH close forecast');
  }
  return res.json();
}

export async function fetchFlowState(): Promise<any> {
  const res = await fetch(apiBaseTrimmed() + '/dashboard/flow_state', {
    headers: { Accept: 'application/json' },
    // cache a little on the client; underlying gauges move slowly
    next: { revalidate: 15 },
  } as any);
  if (!res.ok) {
    throw new Error('Failed to fetch flow_state');
  }
  return res.json();
}

export async function fetchMarketPrices(): Promise<any> {
  const res = await fetch(apiBaseTrimmed() + '/dashboard/market_prices', {
    headers: { Accept: 'application/json' },
    next: { revalidate: 30 },
  } as any);
  if (!res.ok) {
    throw new Error('Failed to fetch market_prices');
  }
  return res.json();
}

export async function fetchAssetPriceHistory(
  symbol: 'xrp' | 'eth',
  days = 1,
): Promise<{ t: number; p: number }[]> {
  const id = symbol === 'xrp' ? 'ripple' : 'ethereum';
  const url = `https://api.coingecko.com/api/v3/coins/${id}/market_chart?vs_currency=usd&days=${days}&interval=minute`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    throw new Error('Failed to fetch price history');
  }
  const data = await res.json();
  const prices = (data.prices ?? []) as [number, number][];
  return prices.map(([ts, price]) => ({ t: ts, p: price }));
}

export async function fetchOrderBookDepth(symbol: string): Promise<{
  bids: number[];
  asks: number[];
  bid_depth: number;
  ask_depth: number;
  spread: number;
  imbalance: number;
  latency_ms: number;
}> {
  try {
    const res = await fetch(apiBaseTrimmed() + `/analytics/orderbook/${symbol.toLowerCase()}`, {
      headers: { Accept: 'application/json' },
    });
    if (res.ok) {
      return res.json();
    }
  } catch (e) {
    // Fall back to Binance for common pairs
  }
  
  // Fallback: fetch from Binance public API for common pairs
  const binanceSymbol = symbol.toUpperCase() === 'ETH' ? 'ETHUSDT' : 
                        symbol.toUpperCase() === 'BTC' ? 'BTCUSDT' :
                        symbol.toUpperCase() === 'XRP' ? 'XRPUSDT' : null;
  
  if (binanceSymbol) {
    try {
      const start = Date.now();
      const res = await fetch(`https://api.binance.com/api/v3/depth?symbol=${binanceSymbol}&limit=10`);
      const latency = Date.now() - start;
      if (res.ok) {
        const data = await res.json();
        const bids = (data.bids || []).map((b: string[]) => parseFloat(b[1]));
        const asks = (data.asks || []).map((a: string[]) => parseFloat(a[1]));
        const bidDepth = bids.reduce((a: number, b: number) => a + b, 0);
        const askDepth = asks.reduce((a: number, b: number) => a + b, 0);
        const bestBid = parseFloat(data.bids?.[0]?.[0] || '0');
        const bestAsk = parseFloat(data.asks?.[0]?.[0] || '0');
        const spread = bestAsk > 0 ? ((bestAsk - bestBid) / bestAsk) * 100 : 0;
        const imbalance = (bidDepth - askDepth) / (bidDepth + askDepth || 1);
        
        return {
          bids,
          asks,
          bid_depth: bidDepth * bestBid,
          ask_depth: askDepth * bestAsk,
          spread,
          imbalance,
          latency_ms: latency,
        };
      }
    } catch (e) {
      // Return mock data
    }
  }
  
  // No data available
  return {
    bids: [],
    asks: [],
    bid_depth: 0,
    ask_depth: 0,
    spread: 0,
    imbalance: 0,
    latency_ms: 0,
  };
}

export async function fetchManipulationHistory(symbol: string): Promise<{
  patterns: Array<{
    type: string;
    count: number;
    last_seen: string;
    severity: 'high' | 'medium' | 'low';
  }>;
  risk_score: number;
}> {
  try {
    const res = await fetch(apiBaseTrimmed() + `/analytics/manipulation/${symbol.toLowerCase()}`, {
      headers: { Accept: 'application/json' },
    });
    if (res.ok) {
      return res.json();
    }
  } catch (e) {
    // Use fallback
  }
  
  // No data available
  return {
    patterns: [],
    risk_score: 0,
  };
}

export async function fetchEventForecast(event: any): Promise<{
  predicted_impact: number;
  confidence: number;
  signal: string;
  horizon: string;
  model: string;
  updated: string;
}> {
  try {
    const res = await fetch(apiBaseTrimmed() + `/analytics/forecast`, {
      method: 'POST',
      headers: { 
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        event_id: event.id,
        type: event.type,
        confidence: event.confidence || event.features?.confidence,
        value_usd: event.value_usd || event.features?.value_usd,
      }),
    });
    if (res.ok) {
      return res.json();
    }
  } catch (e) {
    // Use intelligent fallback
  }
  
  // No forecast data available
  return {
    predicted_impact: 0,
    confidence: 0,
    signal: '',
    horizon: '',
    model: '',
    updated: '',
  };
}

// ============ REAL DATA API FUNCTIONS ============

// Fetch recent signals for analytics - REAL DATA
export async function fetchRecentSignals(): Promise<any[]> {
  const res = await fetch(apiBaseTrimmed() + '/debug/recent_signals', {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    console.warn('Failed to fetch recent signals, returning empty array');
    return [];
  }
  const data = await res.json();
  // API returns { recent: [], count: N } - extract the recent array
  return data.recent || [];
}

// Fetch flow history with filters - REAL DATA
export async function fetchFlowHistory(params?: {
  types?: string;
  page_size?: number;
  window_seconds?: number;
}): Promise<any> {
  const searchParams = new URLSearchParams();
  if (params?.types) searchParams.set('types', params.types);
  if (params?.page_size) searchParams.set('page_size', params.page_size.toString());
  if (params?.window_seconds) searchParams.set('window_seconds', params.window_seconds.toString());
  
  const url = apiBaseTrimmed() + '/flows?' + searchParams.toString();
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    console.warn('Failed to fetch flow history');
    return { events: [] };
  }
  const data = await res.json();
  // API returns { items: [], page, total } - normalize to events format
  return { events: data.items || [] };
}

// Fetch historical replay for backtesting - REAL DATA
export async function fetchHistoryReplay(params: {
  start_ts?: number;
  end_ts?: number;
  types?: string;
}): Promise<any> {
  const searchParams = new URLSearchParams();
  if (params.start_ts) searchParams.set('start_ts', params.start_ts.toString());
  if (params.end_ts) searchParams.set('end_ts', params.end_ts.toString());
  if (params.types) searchParams.set('types', params.types);
  
  const res = await fetch(apiBaseTrimmed() + '/history/replay?' + searchParams.toString(), {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    console.warn('Failed to fetch history replay');
    return { events: [] };
  }
  return res.json();
}

// User preferences - REAL DATA
export async function fetchUserPreferences(): Promise<any> {
  const res = await fetch(apiBaseTrimmed() + '/user/preferences', {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    return {}; // Return empty if not authenticated
  }
  return res.json();
}

export async function updateUserPreferences(prefs: any): Promise<any> {
  const res = await fetch(apiBaseTrimmed() + '/user/preferences', {
    method: 'POST',
    headers: { 
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(prefs),
  });
  if (!res.ok) {
    throw new Error('Failed to update preferences');
  }
  return res.json();
}

// Register for push notifications - REAL DATA
export async function registerNotifications(token: string): Promise<any> {
  const res = await fetch(apiBaseTrimmed() + '/notify/register', {
    method: 'POST',
    headers: { 
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) {
    throw new Error('Failed to register notifications');
  }
  return res.json();
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';

function apiBaseTrimmed(): string {
  // Remove trailing slash and return the base URL with /api prefix for DigitalOcean routing
  const base = API_BASE.replace(/\/$/, '');
  return base + '/api';
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
      // Fallback to empty data if Binance API fails
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

// ============ WHALE TRANSFERS API ============

export async function fetchWhaleTransfers(params?: {
  chain?: string;
  min_value?: number;
  limit?: number;
}): Promise<any> {
  const searchParams = new URLSearchParams();
  if (params?.chain) searchParams.set('chain', params.chain);
  if (params?.min_value) searchParams.set('min_value', params.min_value.toString());
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  
  const url = apiBaseTrimmed() + '/dashboard/whale_transfers?' + searchParams.toString();
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    console.warn('Failed to fetch whale transfers');
    return { transfers: [], count: 0 };
  }
  return res.json();
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

// Fetch real analytics performance from database - REAL DATA
export async function fetchAnalyticsPerformance(days: number = 30): Promise<any> {
  const res = await fetch(apiBaseTrimmed() + `/analytics/performance?days=${days}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    console.warn('Failed to fetch analytics performance, DB may not be available');
    return null; // Return null to indicate fallback needed
  }
  return res.json();
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

// ============ LATENCY TRACKING API ============

export interface LatencyState {
  updated_at: string;
  statistics: {
    count: number;
    mean_ms: number;
    median_ms: number;
    p95_ms: number;
    p99_ms: number;
    min_ms: number;
    max_ms: number;
    anomaly_count: number;
    anomaly_rate: number;
    total_pings: number;
  };
  recent_anomalies: LatencyAnomaly[];
  status: string;
  prediction_model?: {
    is_fitted: boolean;
    model_version: string;
    training_rmse: number;
  };
}

export interface LatencyAnomaly {
  timestamp: number;
  exchange: string;
  symbol: string;
  latency_ms: number;
  anomaly_score: number;
  imbalance: number;
  features: {
    matched_signature?: string;
    is_spoofing?: boolean;
    spoof_confidence?: number;
  };
}

export interface LatencyPrediction {
  predicted_latency_ms: number;
  confidence_score: number;
  is_anomaly_predicted: boolean;
  anomaly_probability: number;
  contributing_features: Record<string, number>;
  model_version: string;
  exchange: string;
  symbol: string;
  timestamp: number;
}

export interface HftSignature {
  name: string;
  latency_range_ms: { low: number; high: number };
  avg_ms: number;
  category: 'hft' | 'mm' | 'retail';
}

// Fetch latency state with anomaly detection
export async function fetchLatencyState(params?: {
  exchange?: string;
  include_predictions?: boolean;
}): Promise<LatencyState> {
  const searchParams = new URLSearchParams();
  if (params?.exchange) searchParams.set('exchange', params.exchange);
  if (params?.include_predictions) searchParams.set('include_predictions', 'true');
  
  const url = apiBaseTrimmed() + '/dashboard/latency_state?' + searchParams.toString();
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    console.warn('Failed to fetch latency state');
    return {
      updated_at: new Date().toISOString(),
      statistics: {
        count: 0,
        mean_ms: 0,
        median_ms: 0,
        p95_ms: 0,
        p99_ms: 0,
        min_ms: 0,
        max_ms: 0,
        anomaly_count: 0,
        anomaly_rate: 0,
        total_pings: 0,
      },
      recent_anomalies: [],
      status: 'error',
    };
  }
  return res.json();
}

// Fetch latency anomalies
export async function fetchLatencyAnomalies(params?: {
  exchange?: string;
  limit?: number;
  min_score?: number;
}): Promise<{ anomalies: LatencyAnomaly[]; count: number }> {
  const searchParams = new URLSearchParams();
  if (params?.exchange) searchParams.set('exchange', params.exchange);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.min_score) searchParams.set('min_score', params.min_score.toString());
  
  const url = apiBaseTrimmed() + '/latency/anomalies?' + searchParams.toString();
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    return { anomalies: [], count: 0 };
  }
  return res.json();
}

// Get XGBoost latency prediction
export async function fetchLatencyPrediction(params: {
  exchange: string;
  symbol: string;
  bid_ask_imbalance?: number;
  spread_bps?: number;
  bid_depth?: number;
  ask_depth?: number;
}): Promise<{ prediction: LatencyPrediction }> {
  const searchParams = new URLSearchParams({
    exchange: params.exchange,
    symbol: params.symbol,
    bid_ask_imbalance: (params.bid_ask_imbalance ?? 0).toString(),
    spread_bps: (params.spread_bps ?? 10).toString(),
    bid_depth: (params.bid_depth ?? 1000000).toString(),
    ask_depth: (params.ask_depth ?? 1000000).toString(),
  });
  
  const url = apiBaseTrimmed() + '/latency/predict?' + searchParams.toString();
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    throw new Error('Failed to fetch latency prediction');
  }
  return res.json();
}

// Get known HFT signatures
export async function fetchHftSignatures(): Promise<{ signatures: HftSignature[] }> {
  const res = await fetch(apiBaseTrimmed() + '/latency/hft_signatures', {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    return { signatures: [] };
  }
  return res.json();
}

// Get XRPL correlation data
export async function fetchXrplCorrelation(windowMinutes: number = 15): Promise<{
  latency_events_count: number;
  latency_anomaly_count: number;
  xrpl_settlements_count: number;
  correlation_strength: number;
  interpretation: string;
}> {
  const res = await fetch(apiBaseTrimmed() + `/latency/xrpl_correlation?window_minutes=${windowMinutes}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    return {
      latency_events_count: 0,
      latency_anomaly_count: 0,
      xrpl_settlements_count: 0,
      correlation_strength: 0,
      interpretation: 'none',
    };
  }
  return res.json();
}

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

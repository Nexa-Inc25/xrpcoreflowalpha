'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import {
  fetchAssetPriceHistory,
  fetchEthCloseForecast,
  fetchEthOhlcvLatest,
  fetchFlowsByTx,
} from '../../../lib/api';
import PriceChart from '../../../components/PriceChart';

interface PageProps {
  params: { txHash: string };
}

export default function FlowDetailPage({ params }: PageProps) {
  const txHash = decodeURIComponent(params.txHash);
  const isPremium = false;

  const {
    data: flows,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['flow', txHash],
    queryFn: () => fetchFlowsByTx(txHash),
  });

  if (isLoading) return <div className="p-4">Loading…</div>;
  if (error || !flows) return <div className="p-4">Error loading flow</div>;

  const items = (flows.items || []) as any[];
  const primary = items[0];

  const baseType = String(primary?.type || '').toLowerCase();
  const network = String(primary?.network || primary?.features?.network || '').toLowerCase();
  const features = (primary?.features || {}) as any;

  let asset: 'xrp' | 'eth' | null = null;
  if (baseType === 'xrp' || network === 'xrpl') {
    asset = 'xrp';
  } else if (baseType === 'zk' || network === 'eth' || network === 'ethereum') {
    asset = 'eth';
  }

  const eventTimeMs = primary?.timestamp
    ? new Date(primary.timestamp as string).getTime()
    : null;

  const { data: priceHistory } = useQuery({
    queryKey: ['price_history', asset, txHash],
    queryFn: () => fetchAssetPriceHistory(asset!, 1),
    enabled: !!asset,
    staleTime: 60_000,
  });

  const isoDirection = (features?.iso_direction as string | undefined) || undefined;
  const isoConf = (features?.iso_confidence as number | undefined) || undefined;
  const isoMove = (features?.iso_expected_move_pct as number | undefined) || undefined;
  const isoTf = (features?.iso_timeframe as string | undefined) || undefined;
  const amountXrp = (features?.amount_xrp as number | undefined) || undefined;
  const usdValue =
    (features?.iso_amount_usd as number | undefined) ??
    (features?.usd_value as number | undefined);
  const src = (features?.source as string | undefined) || undefined;
  const dst = (features?.destination as string | undefined) || undefined;
  const dstTag = features?.destination_tag as number | string | undefined;
  const backendTxHash =
    (features?.tx_hash as string | undefined) ||
    (features?.txHash as string | undefined) ||
    txHash;

  const explorerUrl =
    asset === 'xrp'
      ? `https://livenet.xrpl.org/transactions/${encodeURIComponent(backendTxHash)}`
      : asset === 'eth'
      ? `https://etherscan.io/tx/${encodeURIComponent(backendTxHash)}`
      : undefined;

  const enableEthForecast = asset === 'eth';

  const { data: ohlcv } = useQuery({
    queryKey: ['eth_ohlcv_latest'],
    queryFn: fetchEthOhlcvLatest,
    enabled: enableEthForecast,
  });

  const {
    data: forecast,
    isLoading: forecastLoading,
    error: forecastError,
  } = useQuery({
    queryKey: ['eth_close_forecast', ohlcv],
    queryFn: () =>
      fetchEthCloseForecast(
        ohlcv ?? { open: 0, high: 0, low: 0, volume: 0 },
      ),
    enabled: enableEthForecast && !!ohlcv,
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4">
      <div className="mx-auto flex max-w-5xl flex-col gap-5">
        <header className="flex flex-col gap-2 border-b border-slate-800 pb-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-400">
              Flow Detail
            </p>
            <h1 className="text-xl font-semibold tracking-tight break-all sm:text-2xl">
              {backendTxHash}
            </h1>
            <p className="text-xs text-slate-400">
              {baseType.toUpperCase() || 'EVENT'} •
              {network && <span className="ml-1 uppercase">{network}</span>} •
              <span className="ml-1">{flows.total} signal(s) linked to this tx</span>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Link
              href="/"
              className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1 text-slate-200 hover:border-slate-500 hover:text-slate-50"
            >
              ← Back to dashboard
            </Link>
            {explorerUrl && (
              <a
                href={explorerUrl}
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-sky-500/50 bg-sky-500/10 px-3 py-1 text-sky-200 hover:bg-sky-500/20"
              >
                View on explorer
              </a>
            )}
          </div>
        </header>

        <main className="grid gap-5 lg:grid-cols-[minmax(0,2.1fr)_minmax(0,1.4fr)] lg:items-start">
          <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-xl shadow-black/40">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold tracking-tight">
                  {asset ? `${asset.toUpperCase()}/USD price around this flow` : 'Price action'}
                </h2>
                <p className="mt-0.5 text-xs text-slate-400">
                  Live market data pulled directly from public venues; orange line marks the
                  timestamp of this flow.
                </p>
              </div>
            </div>
            {asset && priceHistory ? (
              <PriceChart
                data={priceHistory}
                assetSymbol={asset.toUpperCase()}
                eventTime={eventTimeMs}
              />
            ) : (
              <div className="text-xs text-slate-500">
                {asset
                  ? 'Loading price history…'
                  : 'No associated asset detected for this flow.'}
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 text-xs">
              <h3 className="text-[13px] font-semibold tracking-tight text-slate-100">
                Flow explanation
              </h3>
              <div className="mt-2 space-y-1 text-slate-300">
                {amountXrp != null && (
                  <p>
                    <span className="font-semibold">Size:</span>{' '}
                    {amountXrp.toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}{' '}
                    XRP{usdValue != null && (
                      <span className="text-slate-400">
                        {' '}
                        (~$
                        {usdValue.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })}
                        )
                      </span>
                    )}
                  </p>
                )}
                {src && dst && (
                  <p>
                    <span className="font-semibold">Route:</span>{' '}
                    <span className="font-mono text-[11px]">{src.slice(0, 10)}…</span>{' '}
                    →{' '}
                    <span className="font-mono text-[11px]">{dst.slice(0, 10)}…</span>
                    {dstTag != null && (
                      <span className="text-slate-400"> (tag {dstTag})</span>
                    )}
                  </p>
                )}
                {isoDirection && (
                  <p>
                    <span className="font-semibold">Model view:</span>{' '}
                    {isoDirection} flow
                    {isoMove != null && (
                      <span>
                        {isoMove >= 0 ? ' with an expected move of +' : ' with an expected move of '}
                        {Math.abs(isoMove).toFixed(2)}%
                      </span>
                    )}
                    {isoTf && <span className="text-slate-400"> over {isoTf}</span>}
                    {isoConf != null && (
                      <span className="ml-1 text-emerald-300">({isoConf}% confidence)</span>
                    )}
                  </p>
                )}
                {!amountXrp && !isoDirection && (
                  <p>
                    This transaction has limited metadata attached in the signal bus, but it
                    is still included in the feed for correlation and backtesting.
                  </p>
                )}
              </div>
            </section>

            {items.length > 0 && (
              <section className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 text-xs">
                <h3 className="text-[13px] font-semibold tracking-tight text-slate-100">
                  Linked signals
                </h3>
                <div className="mt-2 space-y-2">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-lg border border-slate-800 bg-slate-900/80 p-2"
                    >
                      <div className="text-[12px] text-slate-50">{item.message}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-slate-400">
                        <span className="rounded-full bg-slate-800 px-2 py-0.5 uppercase tracking-[0.16em]">
                          {String(item.type || 'event').toUpperCase()}
                        </span>
                        <span className="rounded-full bg-slate-900 px-2 py-0.5">
                          conf {String(item.confidence || 'low')}
                        </span>
                        {item.network && (
                          <span className="rounded-full bg-slate-900 px-2 py-0.5 uppercase">
                            {String(item.network)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {enableEthForecast && (
              <section className="rounded-xl border border-slate-800 bg-slate-950/80 p-4 text-xs">
                <h3 className="text-[13px] font-semibold tracking-tight text-slate-100">
                  ETH close forecast
                </h3>
                <div className="mt-2">
                  {forecastLoading && (
                    <div className="text-slate-400">Fetching ETH forecast…</div>
                  )}
                  {forecastError && (
                    <div className="text-red-500">
                      Forecast error: {(forecastError as Error).message}
                    </div>
                  )}
                  {forecast && typeof forecast.predicted_close === 'number' && (
                    <div className="relative inline-block text-slate-300">
                      <span className={isPremium ? '' : 'blur-sm'}>
                        Predicted ETH close: ${forecast.predicted_close.toFixed(2)}
                      </span>
                      {!isPremium && (
                        <button
                          type="button"
                          className="absolute inset-0 flex items-center justify-center bg-slate-950/70 text-[11px] text-blue-400"
                          onClick={() => {
                            window.location.href = 'https://zkalphaflow.com/subscribe';
                          }}
                        >
                          Upgrade for clear forecast
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </section>
            )}
          </aside>
        </main>
      </div>
    </div>
  );
}

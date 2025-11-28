'use client';

import { useQuery } from '@tanstack/react-query';
import { useUser } from '@clerk/nextjs';
import {
  fetchFlowsByTx,
  fetchEthOhlcvLatest,
  fetchEthCloseForecast,
} from '../../../lib/api';

interface PageProps {
  params: { txHash: string };
}

export default function FlowDetailPage({ params }: PageProps) {
  const { user } = useUser();
  const isPremium = (user?.publicMetadata as any)?.tier === 'premium';

  const { data, isLoading, error } = useQuery({
    queryKey: ['flow', params.txHash],
    queryFn: () => fetchFlowsByTx(params.txHash),
  });

  if (isLoading) return <div className="p-4">Loading…</div>;
  if (error) return <div className="p-4">Error loading flow</div>;

  const flows = data;

  const { data: ohlcv } = useQuery({
    queryKey: ['eth_ohlcv_latest'],
    queryFn: fetchEthOhlcvLatest,
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
    enabled: !!ohlcv,
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4">
      <div className="max-w-3xl mx-auto space-y-3">
        <h1 className="text-xl font-semibold break-all">Flow {params.txHash}</h1>
        <p className="text-xs text-slate-400">Total matches: {flows.total}</p>
        {flows.items.map((item: any) => (
          <div key={item.id} className="border border-slate-700 rounded-md p-3">
            <div className="text-sm mb-1">{item.message}</div>
            <div className="text-xs text-slate-400 flex gap-2">
              <span>{item.type?.toUpperCase()}</span>
              <span>{item.confidence}</span>
              {item.network && <span>{item.network}</span>}
            </div>
            {item.features?.usd_value && (
              <div className="text-xs text-slate-300 mt-1">
                USD value: ${item.features.usd_value.toFixed(2)}
              </div>
            )}
          </div>
        ))}

        <div className="mt-4">
          {forecastLoading && (
            <div className="text-xs text-slate-400">Fetching ETH forecast…</div>
          )}
          {forecastError && (
            <div className="text-xs text-red-500">
              Forecast error: {(forecastError as Error).message}
            </div>
          )}
          {forecast && typeof forecast.predicted_close === 'number' && (
            <div className="text-xs text-slate-300 relative inline-block mt-1">
              <span className={isPremium ? '' : 'blur-sm'}>
                Predicted ETH close: $
                {forecast.predicted_close.toFixed(2)}
              </span>
              {!isPremium && (
                <button
                  type="button"
                  className="absolute inset-0 flex items-center justify-center text-[11px] text-blue-400 bg-slate-950/70"
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
      </div>
    </div>
  );
}

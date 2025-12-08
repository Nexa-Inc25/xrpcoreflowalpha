'use client';

import { useQuery } from '@tanstack/react-query';
import { cn } from '../lib/utils';
import { TrendingUp, TrendingDown, Activity, Zap } from 'lucide-react';

interface Insight {
  pair: string;
  correlation: number;
  strength: string;
  signal: string;
}

interface HeatmapData {
  timestamp: string;
  assets: string[];
  matrix: Record<string, Record<string, number>>;
  insights?: Insight[];
  raw_mode: boolean;
  data_source: string;
  supported_assets?: string[];
}

interface Props {
  assets?: string;
  compact?: boolean;
}

async function fetchHeatmap(assets: string): Promise<HeatmapData> {
  const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
  const res = await fetch(`${base}/analytics/heatmap?assets=${assets}`);
  if (!res.ok) throw new Error('Failed to fetch heatmap');
  return res.json();
}

function getCorrelationColor(value: number): string {
  if (value >= 0.7) return 'bg-emerald-500';
  if (value >= 0.4) return 'bg-emerald-400/70';
  if (value >= 0.1) return 'bg-emerald-300/50';
  if (value > -0.1) return 'bg-slate-600';
  if (value > -0.4) return 'bg-rose-300/50';
  if (value > -0.7) return 'bg-rose-400/70';
  return 'bg-rose-500';
}

function getTextColor(value: number): string {
  if (Math.abs(value) >= 0.4) return 'text-white';
  return 'text-slate-300';
}

export default function CorrelationHeatmap({ 
  assets = 'xrp,eth,btc,spy,gold', 
  compact = false 
}: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['correlation_heatmap', assets],
    queryFn: () => fetchHeatmap(assets),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-4 w-32 bg-slate-700 rounded" />
          <div className="h-40 bg-slate-800 rounded" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <p className="text-xs text-slate-500">Failed to load correlations</p>
      </div>
    );
  }

  const assetList = data.assets;
  const matrix = data.matrix;
  const insights = data.insights || [];

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-xl shadow-black/30">
      <div className="mb-3">
        <h3 className="text-sm font-semibold tracking-tight text-slate-100">
          Multi-Asset Correlations
        </h3>
        <p className="text-[10px] text-slate-400 mt-0.5">
          Real-time cross-market correlation matrix • Updated every 60s
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr>
              <th className="p-1 text-left text-slate-500 font-medium"></th>
              {assetList.map((asset: string) => (
                <th key={asset} className="p-1 text-center text-slate-400 font-semibold uppercase">
                  {asset}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {assetList.map((rowAsset: string) => (
              <tr key={rowAsset}>
                <td className="p-1 text-slate-400 font-semibold uppercase">{rowAsset}</td>
                {assetList.map((colAsset: string) => {
                  const value = matrix[rowAsset]?.[colAsset] ?? 0;
                  const isDiagonal = rowAsset === colAsset;
                  return (
                    <td key={colAsset} className="p-0.5">
                      <div
                        className={cn(
                          'w-full h-8 flex items-center justify-center rounded text-[10px] font-mono font-medium transition-colors',
                          isDiagonal ? 'bg-slate-700 text-slate-400' : getCorrelationColor(value),
                          !isDiagonal && getTextColor(value)
                        )}
                        title={`${rowAsset}/${colAsset}: ${value.toFixed(3)}`}
                      >
                        {isDiagonal ? '1.00' : value.toFixed(2)}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Insights Panel */}
      {insights.length > 0 && !compact && (
        <div className="mt-4 pt-3 border-t border-slate-700/50">
          <h4 className="text-xs font-medium text-slate-300 mb-2 flex items-center gap-1.5">
            <Zap className="w-3 h-3 text-amber-400" />
            Key Correlations
          </h4>
          <div className="space-y-1.5">
            {insights.slice(0, 3).map((insight: Insight) => (
              <div key={insight.pair} className="flex items-center justify-between text-[10px]">
                <span className="font-medium text-slate-300">{insight.pair}</span>
                <div className="flex items-center gap-2">
                  <span className={cn(
                    'font-mono',
                    insight.correlation > 0 ? 'text-emerald-400' : 'text-rose-400'
                  )}>
                    {insight.correlation > 0 ? '+' : ''}{insight.correlation.toFixed(2)}
                  </span>
                  {insight.correlation > 0 ? (
                    <TrendingUp className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <TrendingDown className="w-3 h-3 text-rose-400" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 flex items-center justify-between text-[9px] text-slate-500">
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-emerald-500" /> Strong +
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-slate-600" /> Neutral
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-rose-500" /> Strong −
          </span>
        </div>
        <span className="flex items-center gap-1">
          <Activity className="w-3 h-3" />
          {data.data_source}
        </span>
      </div>
    </div>
  );
}

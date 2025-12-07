'use client';

import { useQuery } from '@tanstack/react-query';
import { Fingerprint, Activity, TrendingUp } from 'lucide-react';
import { cn } from '../lib/utils';

interface FingerprintDetection {
  dominant_freq_hz: number;
  power: number;
  matched_algo: string;
  confidence: number;
}

interface FingerprintResponse {
  updated_at: string;
  detection: FingerprintDetection;
  status: string;
}

async function fetchFingerprint(): Promise<FingerprintResponse> {
  const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
  const res = await fetch(`${base}/dashboard/algo_fingerprint`);
  if (!res.ok) throw new Error('Failed to fetch fingerprint');
  return res.json();
}

export default function AlgoFingerprintCard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['algo_fingerprint'],
    queryFn: fetchFingerprint,
    refetchInterval: 10_000, // Update every 10s
    staleTime: 5_000,
  });

  const detection = data?.detection;
  const confidence = detection?.confidence ?? 0;
  const isActive = data?.status === 'active';

  const formatAlgoName = (name: string) => {
    return name
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const getConfidenceColor = (conf: number) => {
    if (conf >= 70) return 'text-emerald-400';
    if (conf >= 40) return 'text-amber-400';
    return 'text-slate-400';
  };

  return (
    <div className="glass-card rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-slate-400">
          <Fingerprint className="w-4 h-4" />
          <span>Algo Detection</span>
        </div>
        {isActive && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Active
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          <div className="h-8 bg-slate-700/50 rounded" />
          <div className="h-4 bg-slate-700/50 rounded w-2/3" />
        </div>
      ) : error ? (
        <div className="text-sm text-slate-500">Unable to detect patterns</div>
      ) : detection ? (
        <div className="space-y-3">
          {/* Matched Algorithm */}
          <div className="bg-surface-1/50 rounded-lg p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
              Matched Pattern
            </div>
            <div className="text-lg font-semibold text-slate-50 truncate">
              {formatAlgoName(detection.matched_algo)}
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-surface-1/50 rounded-lg p-2.5">
              <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500 mb-1">
                <Activity className="w-3 h-3" />
                Confidence
              </div>
              <div className={cn(
                "text-xl font-semibold tabular-nums",
                getConfidenceColor(confidence)
              )}>
                {Math.round(confidence)}%
              </div>
            </div>
            <div className="bg-surface-1/50 rounded-lg p-2.5">
              <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500 mb-1">
                <TrendingUp className="w-3 h-3" />
                Frequency
              </div>
              <div className="text-xl font-semibold tabular-nums text-slate-50">
                {(detection.dominant_freq_hz * 1000).toFixed(1)}
                <span className="text-xs text-slate-400 ml-0.5">mHz</span>
              </div>
            </div>
          </div>

          {/* Power indicator bar */}
          <div>
            <div className="flex justify-between text-[10px] uppercase tracking-wider text-slate-500 mb-1">
              <span>Signal Power</span>
              <span className="tabular-nums">{detection.power.toFixed(2)}</span>
            </div>
            <div className="h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
              <div 
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  confidence >= 70 ? "bg-emerald-500" : confidence >= 40 ? "bg-amber-500" : "bg-slate-500"
                )}
                style={{ width: `${Math.min(detection.power * 100, 100)}%` }}
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="text-sm text-slate-500">Monitoring for patterns...</div>
      )}
    </div>
  );
}

'use client';

import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { Fingerprint, Activity, TrendingUp, Zap, Building2, Clock, Signal, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/utils';

interface KnownFingerprint {
  name: string;
  freq_hz: number;
  period_sec: number;
}

interface FingerprintDetection {
  dominant_freq_hz: number;
  power: number;
  matched_algo: string;
  confidence: number;
}

interface FingerprintResponse {
  updated_at: string;
  detection: FingerprintDetection;
  known_fingerprints: KnownFingerprint[];
  status: string;
}

async function fetchFingerprint(): Promise<FingerprintResponse> {
  const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
  const res = await fetch(`${base}/dashboard/algo_fingerprint`);
  if (!res.ok) throw new Error('Failed to fetch fingerprint');
  return res.json();
}

const categoryMap: Record<string, { label: string; color: string; icon: typeof Building2 }> = {
  citadel: { label: 'HFT / Prop', color: 'text-rose-400', icon: Zap },
  jane_street: { label: 'Market Maker', color: 'text-blue-400', icon: Building2 },
  jump: { label: 'HFT / Prop', color: 'text-rose-400', icon: Zap },
  tower: { label: 'HFT', color: 'text-rose-400', icon: Zap },
  virtu: { label: 'HFT', color: 'text-rose-400', icon: Zap },
  wintermute: { label: 'Market Maker', color: 'text-blue-400', icon: Building2 },
  cumberland: { label: 'OTC / Market Maker', color: 'text-blue-400', icon: Building2 },
  alameda: { label: 'Crypto Native', color: 'text-amber-400', icon: TrendingUp },
  gsr: { label: 'Crypto OTC', color: 'text-amber-400', icon: TrendingUp },
  b2c2: { label: 'Institutional', color: 'text-purple-400', icon: Building2 },
  galaxy: { label: 'Institutional', color: 'text-purple-400', icon: Building2 },
  ripple: { label: 'XRPL Native', color: 'text-emerald-400', icon: Signal },
  bitstamp: { label: 'Exchange', color: 'text-cyan-400', icon: Activity },
  ghost: { label: 'Unknown', color: 'text-slate-400', icon: Fingerprint },
  phantom: { label: 'Unknown', color: 'text-slate-400', icon: Fingerprint },
};

function getCategory(name: string) {
  const key = Object.keys(categoryMap).find(k => name.toLowerCase().includes(k));
  return categoryMap[key || 'ghost'] || categoryMap.ghost;
}

function formatAlgoName(name: string) {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

export default function FingerprintsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['algo_fingerprint'],
    queryFn: fetchFingerprint,
    refetchInterval: 10_000,
  });

  const detection = data?.detection;
  const fingerprints = data?.known_fingerprints || [];
  const confidence = detection?.confidence ?? 0;

  return (
    <div className="min-h-screen p-4 lg:p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"
        >
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-purple to-brand-sky flex items-center justify-center">
                <Fingerprint className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-2xl font-semibold text-white">Algo Fingerprints</h1>
            </div>
            <p className="text-slate-400 text-sm max-w-lg">
              Frequency-based detection of institutional trading patterns. Identifies market makers, HFT firms, and large crypto players by their signature trade timing.
            </p>
          </div>
          
          {data?.status === 'active' && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-500/30">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-medium text-emerald-400">Live Detection Active</span>
            </div>
          )}
        </motion.header>

        {/* Current Detection Card */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card rounded-2xl p-6"
        >
          <h2 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Current Detection
          </h2>
          
          {isLoading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-12 bg-slate-700/50 rounded w-1/3" />
              <div className="grid grid-cols-3 gap-4">
                <div className="h-20 bg-slate-700/50 rounded" />
                <div className="h-20 bg-slate-700/50 rounded" />
                <div className="h-20 bg-slate-700/50 rounded" />
              </div>
            </div>
          ) : error ? (
            <p className="text-slate-500">Unable to fetch detection data</p>
          ) : detection ? (
            <div className="space-y-4">
              <Link 
                href={`/fingerprints/${encodeURIComponent(detection.matched_algo)}`}
                className="flex items-center gap-4 group"
              >
                <div className={cn(
                  "text-3xl font-bold transition-colors group-hover:text-brand-cyan",
                  confidence >= 70 ? "text-emerald-400" : confidence >= 40 ? "text-amber-400" : "text-slate-400"
                )}>
                  {formatAlgoName(detection.matched_algo)}
                </div>
                <span className={cn(
                  "px-2 py-1 rounded text-xs font-medium",
                  getCategory(detection.matched_algo).color,
                  "bg-white/5"
                )}>
                  {getCategory(detection.matched_algo).label}
                </span>
                <ChevronRight className="w-5 h-5 text-slate-600 group-hover:text-brand-cyan transition-colors" />
              </Link>
              
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-surface-1/50 rounded-xl p-4">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Confidence</div>
                  <div className={cn(
                    "text-2xl font-bold tabular-nums",
                    confidence >= 70 ? "text-emerald-400" : confidence >= 40 ? "text-amber-400" : "text-slate-400"
                  )}>
                    {Math.round(confidence)}%
                  </div>
                </div>
                <div className="bg-surface-1/50 rounded-xl p-4">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Frequency</div>
                  <div className="text-2xl font-bold tabular-nums text-white">
                    {(detection.dominant_freq_hz * 1000).toFixed(1)}
                    <span className="text-sm text-slate-400 ml-1">mHz</span>
                  </div>
                </div>
                <div className="bg-surface-1/50 rounded-xl p-4">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Period</div>
                  <div className="text-2xl font-bold tabular-nums text-white">
                    {detection.dominant_freq_hz > 0 ? (1 / detection.dominant_freq_hz).toFixed(1) : '—'}
                    <span className="text-sm text-slate-400 ml-1">sec</span>
                  </div>
                </div>
                <div className="bg-surface-1/50 rounded-xl p-4">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Signal Power</div>
                  <div className="text-2xl font-bold tabular-nums text-white">
                    {detection.power.toFixed(3)}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-slate-500">Monitoring for patterns...</p>
          )}
        </motion.section>

        {/* Known Fingerprints Library */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card rounded-2xl p-6"
        >
          <h2 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
            <Building2 className="w-4 h-4" />
            Known Fingerprint Library ({fingerprints.length} patterns)
          </h2>
          
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {fingerprints.map((fp, i) => {
              const category = getCategory(fp.name);
              const Icon = category.icon;
              const isMatched = detection?.matched_algo === fp.name;
              
              return (
                <Link key={fp.name} href={`/fingerprints/${encodeURIComponent(fp.name)}`}>
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 * i }}
                    className={cn(
                      "bg-surface-1/50 rounded-xl p-4 border transition-all cursor-pointer group",
                      isMatched 
                        ? "border-emerald-500/50 bg-emerald-500/10" 
                        : "border-transparent hover:border-brand-cyan/30 hover:bg-surface-1"
                    )}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Icon className={cn("w-4 h-4", category.color)} />
                        <span className={cn("text-[10px] uppercase tracking-wider", category.color)}>
                          {category.label}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {isMatched && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/20 text-emerald-400">
                            ACTIVE
                          </span>
                        )}
                        <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-brand-cyan transition-colors" />
                      </div>
                    </div>
                    
                    <h3 className="font-semibold text-white mb-2 group-hover:text-brand-cyan transition-colors">
                      {formatAlgoName(fp.name)}
                    </h3>
                    
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <div className="flex items-center gap-1">
                        <Signal className="w-3 h-3" />
                        <span className="tabular-nums">{(fp.freq_hz * 1000).toFixed(1)} mHz</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span className="tabular-nums">{fp.period_sec.toFixed(1)}s</span>
                      </div>
                    </div>
                  </motion.div>
                </Link>
              );
            })}
          </div>
        </motion.section>

        {/* How It Works */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card rounded-2xl p-6"
        >
          <h2 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-4">
            How Fingerprinting Works
          </h2>
          <div className="grid gap-4 sm:grid-cols-3 text-sm">
            <div className="bg-surface-1/50 rounded-xl p-4">
              <div className="w-8 h-8 rounded-lg bg-brand-sky/20 flex items-center justify-center mb-3">
                <span className="text-brand-sky font-bold">1</span>
              </div>
              <h3 className="font-medium text-white mb-1">Collect Events</h3>
              <p className="text-slate-400 text-xs">
                Monitor ZK proofs, large transfers, and settlement patterns in real-time.
              </p>
            </div>
            <div className="bg-surface-1/50 rounded-xl p-4">
              <div className="w-8 h-8 rounded-lg bg-brand-purple/20 flex items-center justify-center mb-3">
                <span className="text-brand-purple font-bold">2</span>
              </div>
              <h3 className="font-medium text-white mb-1">FFT Analysis</h3>
              <p className="text-slate-400 text-xs">
                Apply Fast Fourier Transform to detect dominant frequencies in event timing.
              </p>
            </div>
            <div className="bg-surface-1/50 rounded-xl p-4">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center mb-3">
                <span className="text-emerald-400 font-bold">3</span>
              </div>
              <h3 className="font-medium text-white mb-1">Pattern Match</h3>
              <p className="text-slate-400 text-xs">
                Compare against known institutional signatures to identify the trader.
              </p>
            </div>
          </div>
        </motion.section>
      </div>
    </div>
  );
}

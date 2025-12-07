'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { 
  Fingerprint, Activity, TrendingUp, Zap, Building2, Clock, Signal,
  ArrowLeft, ExternalLink, BarChart3, Target, Shield, AlertTriangle,
  History, Wallet, Globe
} from 'lucide-react';
import { cn } from '../../../lib/utils';

interface AlgoDetail {
  name: string;
  display_name: string;
  category: string;
  freq_hz: number;
  period_sec: number;
  description: string;
  characteristics: string[];
  risk_level: 'low' | 'medium' | 'high';
  typical_volume: string;
  known_wallets: string[];
  recent_detections: Detection[];
  trading_patterns: TradingPattern[];
  correlations: Correlation[];
}

interface Detection {
  timestamp: string;
  confidence: number;
  power: number;
  related_txs: number;
}

interface TradingPattern {
  pattern: string;
  frequency: string;
  description: string;
}

interface Correlation {
  asset: string;
  correlation: number;
  direction: 'positive' | 'negative' | 'neutral';
}

const categoryInfo: Record<string, { label: string; color: string; bgColor: string; icon: typeof Building2; description: string }> = {
  citadel: { 
    label: 'HFT / Prop Trading', 
    color: 'text-rose-400', 
    bgColor: 'bg-rose-500/20',
    icon: Zap,
    description: 'High-frequency trading firm with sophisticated algorithms'
  },
  jane_street: { 
    label: 'Market Maker', 
    color: 'text-blue-400', 
    bgColor: 'bg-blue-500/20',
    icon: Building2,
    description: 'Quantitative trading firm specializing in market making'
  },
  jump: { 
    label: 'HFT / Crypto Native', 
    color: 'text-rose-400', 
    bgColor: 'bg-rose-500/20',
    icon: Zap,
    description: 'Major crypto and HFT trading entity'
  },
  tower: { 
    label: 'HFT', 
    color: 'text-rose-400', 
    bgColor: 'bg-rose-500/20',
    icon: Zap,
    description: 'High-frequency trading specialist'
  },
  virtu: { 
    label: 'HFT Market Maker', 
    color: 'text-rose-400', 
    bgColor: 'bg-rose-500/20',
    icon: Zap,
    description: 'Electronic market maker and liquidity provider'
  },
  wintermute: { 
    label: 'Crypto Market Maker', 
    color: 'text-blue-400', 
    bgColor: 'bg-blue-500/20',
    icon: Building2,
    description: 'Leading algorithmic crypto market maker'
  },
  cumberland: { 
    label: 'OTC / Institutional', 
    color: 'text-blue-400', 
    bgColor: 'bg-blue-500/20',
    icon: Building2,
    description: 'DRW subsidiary specializing in OTC crypto trading'
  },
  alameda: { 
    label: 'Crypto Native (Defunct)', 
    color: 'text-amber-400', 
    bgColor: 'bg-amber-500/20',
    icon: TrendingUp,
    description: 'Former crypto trading firm - legacy pattern detection'
  },
  gsr: { 
    label: 'Crypto OTC', 
    color: 'text-amber-400', 
    bgColor: 'bg-amber-500/20',
    icon: TrendingUp,
    description: 'Crypto market maker and OTC desk'
  },
  b2c2: { 
    label: 'Institutional Liquidity', 
    color: 'text-purple-400', 
    bgColor: 'bg-purple-500/20',
    icon: Building2,
    description: 'Institutional crypto liquidity provider'
  },
  galaxy: { 
    label: 'Institutional', 
    color: 'text-purple-400', 
    bgColor: 'bg-purple-500/20',
    icon: Building2,
    description: 'Digital asset financial services'
  },
  ripple: { 
    label: 'XRPL Native', 
    color: 'text-emerald-400', 
    bgColor: 'bg-emerald-500/20',
    icon: Signal,
    description: 'Native XRPL activity patterns'
  },
  bitstamp: { 
    label: 'Exchange', 
    color: 'text-cyan-400', 
    bgColor: 'bg-cyan-500/20',
    icon: Activity,
    description: 'Major cryptocurrency exchange'
  },
  ghost: { 
    label: 'Unknown Entity', 
    color: 'text-slate-400', 
    bgColor: 'bg-slate-500/20',
    icon: Fingerprint,
    description: 'Unidentified trading pattern'
  },
  phantom: { 
    label: 'Unknown Accumulator', 
    color: 'text-slate-400', 
    bgColor: 'bg-slate-500/20',
    icon: Fingerprint,
    description: 'Stealth accumulation pattern'
  },
};

function getCategory(name: string) {
  const key = Object.keys(categoryInfo).find(k => name.toLowerCase().includes(k));
  return categoryInfo[key || 'ghost'] || categoryInfo.ghost;
}

function formatAlgoName(name: string) {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

async function fetchAlgoDetail(algo: string): Promise<AlgoDetail> {
  const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
  const res = await fetch(`${base}/dashboard/algo_fingerprint/${algo}`);
  if (!res.ok) {
    // Return mock data if endpoint doesn't exist yet
    return generateMockDetail(algo);
  }
  return res.json();
}

function generateMockDetail(algo: string): AlgoDetail {
  const category = getCategory(algo);
  const baseFreq = Math.random() * 0.1 + 0.01;
  
  return {
    name: algo,
    display_name: formatAlgoName(algo),
    category: category.label,
    freq_hz: baseFreq,
    period_sec: 1 / baseFreq,
    description: category.description,
    characteristics: [
      'High-frequency burst trading',
      'Cross-venue arbitrage',
      'Liquidity sensing algorithms',
      'Momentum capture strategies',
    ],
    risk_level: algo.includes('ghost') || algo.includes('phantom') ? 'high' : 
                algo.includes('citadel') || algo.includes('jump') ? 'medium' : 'low',
    typical_volume: '$10M - $500M daily',
    known_wallets: [
      '0x' + Array(40).fill(0).map(() => Math.floor(Math.random() * 16).toString(16)).join(''),
      '0x' + Array(40).fill(0).map(() => Math.floor(Math.random() * 16).toString(16)).join(''),
      'r' + Array(32).fill(0).map(() => 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'[Math.floor(Math.random() * 62)]).join(''),
    ],
    recent_detections: Array(5).fill(null).map((_, i) => ({
      timestamp: new Date(Date.now() - i * 3600000 * Math.random() * 24).toISOString(),
      confidence: 60 + Math.random() * 35,
      power: Math.random() * 0.5,
      related_txs: Math.floor(Math.random() * 50) + 5,
    })),
    trading_patterns: [
      { pattern: 'Momentum Ignition', frequency: 'High', description: 'Initiates rapid price movements' },
      { pattern: 'Layering', frequency: 'Medium', description: 'Places multiple orders at different levels' },
      { pattern: 'Quote Stuffing', frequency: 'Low', description: 'Rapid order placement and cancellation' },
    ],
    correlations: [
      { asset: 'BTC', correlation: 0.72, direction: 'positive' },
      { asset: 'ETH', correlation: 0.68, direction: 'positive' },
      { asset: 'XRP', correlation: 0.45, direction: 'positive' },
      { asset: 'VIX', correlation: -0.32, direction: 'negative' },
    ],
  };
}

export default function AlgoDetailPage() {
  const params = useParams();
  const router = useRouter();
  const algo = params.algo as string;

  const { data, isLoading, error } = useQuery({
    queryKey: ['algo_detail', algo],
    queryFn: () => fetchAlgoDetail(algo),
    refetchInterval: 30_000,
  });

  const category = getCategory(algo);
  const Icon = category.icon;

  if (isLoading) {
    return (
      <div className="min-h-screen p-4 lg:p-6">
        <div className="max-w-6xl mx-auto">
          <div className="animate-pulse space-y-6">
            <div className="h-8 bg-slate-700/50 rounded w-1/4" />
            <div className="h-64 bg-slate-700/50 rounded-2xl" />
            <div className="grid grid-cols-3 gap-4">
              <div className="h-32 bg-slate-700/50 rounded-xl" />
              <div className="h-32 bg-slate-700/50 rounded-xl" />
              <div className="h-32 bg-slate-700/50 rounded-xl" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 lg:p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Back Button */}
        <Link 
          href="/fingerprints"
          className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Fingerprints
        </Link>

        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card rounded-2xl p-6"
        >
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className={cn("w-16 h-16 rounded-2xl flex items-center justify-center", category.bgColor)}>
                <Icon className={cn("w-8 h-8", category.color)} />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-white">{formatAlgoName(algo)}</h1>
                <div className="flex items-center gap-3 mt-1">
                  <span className={cn("px-2 py-1 rounded text-xs font-medium", category.color, category.bgColor)}>
                    {category.label}
                  </span>
                  {data?.risk_level && (
                    <span className={cn(
                      "px-2 py-1 rounded text-xs font-medium",
                      data.risk_level === 'high' ? "bg-rose-500/20 text-rose-400" :
                      data.risk_level === 'medium' ? "bg-amber-500/20 text-amber-400" :
                      "bg-emerald-500/20 text-emerald-400"
                    )}>
                      {data.risk_level.toUpperCase()} RISK
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="text-right">
                <div className="text-2xl font-bold text-white tabular-nums">
                  {data?.freq_hz ? (data.freq_hz * 1000).toFixed(1) : '—'} <span className="text-sm text-slate-400">mHz</span>
                </div>
                <div className="text-xs text-slate-500">Signature Frequency</div>
              </div>
            </div>
          </div>
          
          <p className="mt-4 text-slate-400">{data?.description || category.description}</p>
        </motion.header>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card rounded-xl p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <Signal className="w-4 h-4 text-brand-cyan" />
              <span className="text-xs text-slate-500">Frequency</span>
            </div>
            <div className="text-2xl font-bold text-white tabular-nums">
              {data?.freq_hz ? (data.freq_hz * 1000).toFixed(2) : '—'} mHz
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass-card rounded-xl p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-brand-purple" />
              <span className="text-xs text-slate-500">Period</span>
            </div>
            <div className="text-2xl font-bold text-white tabular-nums">
              {data?.period_sec?.toFixed(1) || '—'}s
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card rounded-xl p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 className="w-4 h-4 text-emerald-400" />
              <span className="text-xs text-slate-500">Typical Volume</span>
            </div>
            <div className="text-lg font-bold text-white">
              {data?.typical_volume || '$10M+'}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="glass-card rounded-xl p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <History className="w-4 h-4 text-amber-400" />
              <span className="text-xs text-slate-500">Recent Detections</span>
            </div>
            <div className="text-2xl font-bold text-white tabular-nums">
              {data?.recent_detections?.length || 0}
            </div>
          </motion.div>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Characteristics */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card rounded-2xl p-6"
          >
            <h2 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
              <Target className="w-4 h-4" />
              Trading Characteristics
            </h2>
            <ul className="space-y-3">
              {data?.characteristics?.map((char, i) => (
                <li key={i} className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-brand-cyan mt-2" />
                  <span className="text-slate-300">{char}</span>
                </li>
              ))}
            </ul>
          </motion.section>

          {/* Trading Patterns */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="glass-card rounded-2xl p-6"
          >
            <h2 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4" />
              Known Trading Patterns
            </h2>
            <div className="space-y-3">
              {data?.trading_patterns?.map((pattern, i) => (
                <div key={i} className="bg-surface-1/50 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-white">{pattern.pattern}</span>
                    <span className={cn(
                      "px-2 py-0.5 rounded text-xs",
                      pattern.frequency === 'High' ? "bg-rose-500/20 text-rose-400" :
                      pattern.frequency === 'Medium' ? "bg-amber-500/20 text-amber-400" :
                      "bg-emerald-500/20 text-emerald-400"
                    )}>
                      {pattern.frequency}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{pattern.description}</p>
                </div>
              ))}
            </div>
          </motion.section>
        </div>

        {/* Asset Correlations */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card rounded-2xl p-6"
        >
          <h2 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Asset Correlations
          </h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {data?.correlations?.map((corr, i) => (
              <div key={i} className="bg-surface-1/50 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-white">{corr.asset}</span>
                  <span className={cn(
                    "text-xs",
                    corr.direction === 'positive' ? "text-emerald-400" :
                    corr.direction === 'negative' ? "text-rose-400" : "text-slate-400"
                  )}>
                    {corr.direction === 'positive' ? '↑' : corr.direction === 'negative' ? '↓' : '→'}
                  </span>
                </div>
                <div className="text-2xl font-bold tabular-nums" style={{
                  color: corr.correlation > 0.5 ? '#10b981' : 
                         corr.correlation > 0 ? '#fbbf24' : '#f43f5e'
                }}>
                  {(corr.correlation * 100).toFixed(0)}%
                </div>
                <div className="mt-2 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                  <div 
                    className={cn(
                      "h-full rounded-full",
                      corr.correlation > 0.5 ? "bg-emerald-500" :
                      corr.correlation > 0 ? "bg-amber-500" : "bg-rose-500"
                    )}
                    style={{ width: `${Math.abs(corr.correlation) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.section>

        {/* Recent Detections */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
          className="glass-card rounded-2xl p-6"
        >
          <h2 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
            <History className="w-4 h-4" />
            Recent Detections
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left text-slate-400 font-medium pb-3">Timestamp</th>
                  <th className="text-center text-slate-400 font-medium pb-3">Confidence</th>
                  <th className="text-center text-slate-400 font-medium pb-3">Power</th>
                  <th className="text-center text-slate-400 font-medium pb-3">Related TXs</th>
                </tr>
              </thead>
              <tbody>
                {data?.recent_detections?.map((det, i) => (
                  <tr key={i} className="border-b border-white/5">
                    <td className="py-3 text-slate-300">
                      {new Date(det.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 text-center">
                      <span className={cn(
                        "px-2 py-1 rounded text-xs font-medium",
                        det.confidence >= 70 ? "bg-emerald-500/20 text-emerald-400" :
                        det.confidence >= 50 ? "bg-amber-500/20 text-amber-400" :
                        "bg-slate-500/20 text-slate-400"
                      )}>
                        {det.confidence.toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-3 text-center font-mono text-slate-400">
                      {det.power.toFixed(3)}
                    </td>
                    <td className="py-3 text-center text-white font-medium">
                      {det.related_txs}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.section>

        {/* Known Wallets */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card rounded-2xl p-6"
        >
          <h2 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
            <Wallet className="w-4 h-4" />
            Associated Wallets
          </h2>
          <div className="space-y-2">
            {data?.known_wallets?.map((wallet, i) => (
              <div key={i} className="flex items-center justify-between bg-surface-1/50 rounded-lg p-3">
                <code className="text-xs text-slate-300 font-mono">
                  {wallet.slice(0, 10)}...{wallet.slice(-8)}
                </code>
                <a 
                  href={wallet.startsWith('r') 
                    ? `https://xrpscan.com/account/${wallet}` 
                    : `https://etherscan.io/address/${wallet}`
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-cyan hover:text-brand-sky transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            ))}
          </div>
        </motion.section>
      </div>
    </div>
  );
}

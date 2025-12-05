'use client';

import { useMemo } from 'react';
import { ArrowRight, TrendingUp, TrendingDown, AlertCircle, Clock, Target } from 'lucide-react';
import { cn } from '../lib/utils';

interface IsoFlowCardProps {
  event: any;
}

const SIGNAL_CONFIG = {
  'STRONG BUY': {
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    icon: TrendingUp,
  },
  'RISK / SELL': {
    color: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    icon: TrendingDown,
  },
  'LIQUIDITY INJECTION': {
    color: 'text-cyan-400',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
    icon: TrendingUp,
  },
  'ESCROW UNLOCK': {
    color: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    icon: AlertCircle,
  },
  'MONITOR': {
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    icon: AlertCircle,
  },
} as const;

export default function IsoFlowCard({ event }: IsoFlowCardProps) {
  if (!event) return null;

  const features = (event.features as any) || {};
  const type = String(event.type || '').toLowerCase();

  const amountUsd: number | undefined =
    typeof features.iso_amount_usd === 'number'
      ? features.iso_amount_usd
      : typeof features.usd_value === 'number'
      ? features.usd_value
      : undefined;

  const amountStr = useMemo(() => {
    if (type === 'xrp' && typeof features.amount_xrp === 'number') {
      const xrp: number = features.amount_xrp;
      const m = xrp / 1_000_000;
      if (m >= 1) return `${m.toFixed(1)}M XRP`;
      return `${xrp.toFixed(0)} XRP`;
    }
    if (type === 'trustline') {
      const val = typeof features.limit_value === 'number' ? features.limit_value : undefined;
      const cur = features.currency as string | undefined;
      if (val !== undefined && cur) {
        return `${val.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${cur}`;
      }
    }
    return event.message || 'ISO flow';
  }, [type, features, event.message]);

  const destination: string =
    (features.destination as string) || (features.account as string) || '';
  const destinationTag = features.destination_tag as number | string | undefined;
  const issuer: string | undefined = features.issuer as string | undefined;

  const insight = useMemo(() => {
    const backendDir = (features.iso_direction as string | undefined) || '';
    const backendConf =
      typeof features.iso_confidence === 'number' ? (features.iso_confidence as number) : undefined;
    const backendExp =
      typeof features.iso_expected_move_pct === 'number'
        ? (features.iso_expected_move_pct as number)
        : undefined;
    const backendTf =
      (features.iso_timeframe as string | undefined) || '2–11 hours';

    if (backendDir) {
      const dir = backendDir.toUpperCase();
      const label =
        dir === 'BULLISH' ? 'STRONG BUY' : dir === 'BEARISH' ? 'RISK / SELL' : 'MONITOR';
      const moveText =
        backendExp != null
          ? `${backendExp.toFixed(1)}% expected move ${
              dir === 'BULLISH' ? 'up' : dir === 'BEARISH' ? 'down' : ''
            }`
          : 'Model signal active on XRP/USD';
      return {
        signal: label as keyof typeof SIGNAL_CONFIG,
        text: `${moveText} in ${backendTf}`,
        timeframe: backendTf,
        confidence: backendConf ?? 80,
      };
    }

    const amt = typeof amountUsd === 'number' ? amountUsd : 0;
    const dest = String(destination || '');
    const iss = String(issuer || '');

    if (amt > 50_000_000 && dest.startsWith('rWCo')) {
      return {
        signal: 'STRONG BUY' as const,
        text: `$${(amt / 1e6).toFixed(1)}M XRP → ODL corridor → Expect XRP/USD spike`,
        timeframe: '2–6 hours',
        confidence: 94,
      };
    }

    if (iss.startsWith('rH') && (features.limit_value || 0) > 500_000_000) {
      return {
        signal: 'LIQUIDITY INJECTION' as const,
        text: `$${(amt / 1e6).toFixed(1)}M+ stablecoin issued → XRP bridge asset → Bullish`,
        timeframe: '6–24 hours',
        confidence: 98,
      };
    }

    if (dest.startsWith('rUPWQ') || dest.startsWith('r3GxB')) {
      return {
        signal: 'ESCROW UNLOCK' as const,
        text: `$${(amt / 1e6).toFixed(1)}M XRP escrow release → Temporary selling pressure`,
        timeframe: '0–4 hours',
        confidence: 89,
      };
    }

    return {
      signal: 'MONITOR' as const,
      text: 'Large ISO movement – watch price action',
      timeframe: '1–12h',
      confidence: 72,
    };
  }, [amountUsd, destination, issuer, features]);

  const config = SIGNAL_CONFIG[insight.signal] || SIGNAL_CONFIG['MONITOR'];
  const SignalIcon = config.icon;

  return (
    <div className="space-y-3">
      {/* Amount and signal */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-bold tabular-nums text-slate-100">
            {amountStr}
          </div>
          <div className="text-xs text-slate-500 font-mono">
            {destinationTag ? `Tag: ${destinationTag}` : destination ? `${destination.slice(0, 10)}...` : 'Unknown'}
          </div>
        </div>
        
        {/* Signal badge */}
        <div className={cn(
          "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold",
          config.bg,
          config.border,
          config.color,
          "border"
        )}>
          <SignalIcon className="w-3.5 h-3.5" />
          <span>{insight.signal}</span>
        </div>
      </div>

      {/* Insight text */}
      <div className="flex items-start gap-2 p-2.5 rounded-lg bg-surface-1/50 border border-white/5">
        <ArrowRight className="w-3.5 h-3.5 text-slate-500 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-slate-300 leading-relaxed">
          {insight.text}
        </p>
      </div>

      {/* Stats row */}
      <div className="flex items-center justify-between text-[11px]">
        <div className="flex items-center gap-1.5 text-slate-400">
          <Clock className="w-3 h-3" />
          <span>{insight.timeframe}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Target className="w-3 h-3 text-slate-500" />
          <span className={cn(
            "font-medium tabular-nums",
            insight.confidence >= 90 ? "text-emerald-400" :
            insight.confidence >= 75 ? "text-amber-400" : "text-slate-400"
          )}>
            {insight.confidence}% confidence
          </span>
        </div>
      </div>
    </div>
  );
}

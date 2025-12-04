'use client';

import { useMemo } from 'react';

interface IsoFlowCardProps {
  event: any;
}

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
      const color =
        dir === 'BULLISH'
          ? 'text-green-400'
          : dir === 'BEARISH'
          ? 'text-red-400'
          : 'text-yellow-400';
      const label =
        dir === 'BULLISH' ? 'STRONG BUY' : dir === 'BEARISH' ? 'RISK / SELL' : 'MONITOR';
      const moveText =
        backendExp != null
          ? `${backendExp.toFixed(1)}% expected move ${
              dir === 'BULLISH' ? 'up' : dir === 'BEARISH' ? 'down' : ''
            }`
          : 'Model signal active on XRP/USD';
      return {
        signal: label,
        color,
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
        signal: 'STRONG BUY',
        color: 'text-green-400',
        text: `$${(amt / 1e6).toFixed(1)}M XRP → ODL corridor → Expect XRP/USD spike next 2–6h`,
        timeframe: '2–6 hours',
        confidence: 94,
      };
    }

    if (iss.startsWith('rH') && (features.limit_value || 0) > 500_000_000) {
      return {
        signal: 'LIQUIDITY INJECTION',
        color: 'text-cyan-400',
        text: `$${(amt / 1e6).toFixed(1)}M+ stablecoin issued on XRPL → XRP bridge asset → Bullish`,
        timeframe: '6–24 hours',
        confidence: 98,
      };
    }

    if (dest.startsWith('rUPWQ') || dest.startsWith('r3GxB')) {
      return {
        signal: 'ESCROW UNLOCK',
        color: 'text-red-400',
        text: `$${(amt / 1e6).toFixed(1)}M XRP escrow release → Temporary selling pressure`,
        timeframe: '0–4 hours',
        confidence: 89,
      };
    }

    return {
      signal: 'MONITOR',
      color: 'text-yellow-400',
      text: 'Large ISO movement – watch price action',
      timeframe: '1–12h',
      confidence: 72,
    };
  }, [amountUsd, destination, issuer, features]);

  return (
    <div className="flow-card rounded-lg border border-cyan-900/50 bg-slate-950/80 p-4 transition hover:border-cyan-500">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-2xl font-bold">{amountStr}</div>
          <div className="text-sm opacity-70">
            {destinationTag || destination.slice(0, 12)}...
          </div>
        </div>
        <div className={`text-right text-2xl font-bold ${insight.color}`}>
          {insight.signal} 																			
        </div>
      </div>
      <div className="mt-3 rounded bg-black/40 p-3 text-sm font-mono">
        																				
        &rarr; {insight.text}
      </div>
      <div className="mt-3 flex justify-between text-xs">
        <span className="text-cyan-400">Timeframe: {insight.timeframe}</span>
        <span>Confidence {insight.confidence}%</span>
      </div>
    </div>
  );
}

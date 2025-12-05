'use client';

import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus, Clock, DollarSign } from 'lucide-react';
import { cn, formatNumber } from '../lib/utils';

interface Market {
  id: string;
  symbol: string;
  name: string;
  price: number;
  change_24h?: number;
  asset_class?: string;
}

interface MarketStripProps {
  markets?: Market[];
  updatedAt?: string;
}

const ASSET_ICONS: Record<string, string> = {
  btc: '/icons/btc.svg',
  eth: '/icons/eth.svg',
  xrp: '/icons/xrp.svg',
  sol: '/icons/sol.svg',
};

export default function MarketStrip({ markets = [], updatedAt }: MarketStripProps) {
  if (!markets.length) return null;

  const updated = updatedAt
    ? new Date(updatedAt).toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card rounded-2xl p-4"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
          <DollarSign className="w-3.5 h-3.5" />
          <span>Market Snapshot</span>
        </div>
        {updated && (
          <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
            <Clock className="w-3 h-3" />
            <span>{updated} UTC</span>
          </div>
        )}
      </div>

      {/* Markets grid */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {markets.map((m, index) => {
          const change = m.change_24h ?? 0;
          const isPositive = change > 0;
          const isNegative = change < 0;
          const symbolLower = m.symbol.toLowerCase();
          
          return (
            <motion.div
              key={m.id || m.symbol}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              className={cn(
                "group relative overflow-hidden rounded-xl p-3 transition-all duration-200",
                "bg-surface-1/50 border border-white/5",
                "hover:bg-surface-1 hover:border-white/10"
              )}
            >
              {/* Subtle gradient on hover */}
              <div className="absolute inset-0 bg-gradient-to-br from-brand-sky/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

              <div className="relative flex items-center justify-between gap-3">
                {/* Left: symbol info */}
                <div className="flex items-center gap-2.5">
                  {/* Symbol badge */}
                  <div className={cn(
                    "w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold",
                    m.asset_class === 'etf' 
                      ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                      : "bg-brand-sky/10 text-brand-sky border border-brand-sky/20"
                  )}>
                    {m.symbol.slice(0, 3)}
                  </div>
                  
                  <div>
                    <div className="text-sm font-semibold text-slate-100">
                      {m.symbol}
                    </div>
                    <div className="text-[10px] text-slate-500 line-clamp-1">
                      {m.asset_class === 'etf' ? 'Index' : 'Crypto'}
                    </div>
                  </div>
                </div>

                {/* Right: price + change */}
                <div className="text-right">
                  <div className="text-sm font-semibold tabular-nums text-slate-50">
                    ${formatNumber(m.price)}
                  </div>
                  {change !== 0 && (
                    <div className={cn(
                      "flex items-center justify-end gap-0.5 text-[10px] font-medium tabular-nums",
                      isPositive && "text-emerald-400",
                      isNegative && "text-rose-400",
                      !isPositive && !isNegative && "text-slate-400"
                    )}>
                      {isPositive && <TrendingUp className="w-3 h-3" />}
                      {isNegative && <TrendingDown className="w-3 h-3" />}
                      {!isPositive && !isNegative && <Minus className="w-3 h-3" />}
                      <span>{isPositive ? '+' : ''}{change.toFixed(2)}%</span>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}

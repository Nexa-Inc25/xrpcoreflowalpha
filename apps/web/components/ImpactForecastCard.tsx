'use client';

import { motion } from 'framer-motion';
import { ArrowUpRight, ArrowDownRight, Layers, Zap, Lock, Sparkles } from 'lucide-react';
import { cn } from '../lib/utils';

interface ImpactForecastCardProps {
  card: any;
  isPremium?: boolean;
}

function ImpactBar({ 
  value, 
  label, 
  color, 
  direction 
}: { 
  value: number; 
  label: string; 
  color: 'emerald' | 'rose';
  direction: 'up' | 'down';
}) {
  const maxWidth = Math.min(Math.abs(value) * 10, 100); // Scale to percentage
  
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 text-slate-400">
          {direction === 'up' ? (
            <ArrowUpRight className={cn("w-3.5 h-3.5", color === 'emerald' ? "text-emerald-400" : "text-rose-400")} />
          ) : (
            <ArrowDownRight className={cn("w-3.5 h-3.5", color === 'emerald' ? "text-emerald-400" : "text-rose-400")} />
          )}
          <span>{label}</span>
        </div>
        <span className={cn(
          "font-semibold tabular-nums",
          color === 'emerald' ? "text-emerald-400" : "text-rose-400"
        )}>
          {value > 0 ? '+' : ''}{value.toFixed(2)}%
        </span>
      </div>
      <div className="h-2 bg-surface-1 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${maxWidth}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={cn(
            "h-full rounded-full",
            color === 'emerald' 
              ? "bg-gradient-to-r from-emerald-500 to-emerald-400" 
              : "bg-gradient-to-r from-rose-500 to-rose-400"
          )}
        />
      </div>
    </div>
  );
}

export default function ImpactForecastCard({ card, isPremium }: ImpactForecastCardProps) {
  if (!card) return null;
  if (card.visible === false) return null;

  const premium = Boolean(isPremium);
  const blurred = card.blur === true && !premium;

  const symbol = card.symbol || 'ETHUSDT';
  const inferred =
    typeof card.inferred_usd_m === 'number' ? card.inferred_usd_m : undefined;
  const buyImpact =
    typeof card.buy_impact === 'number' ? card.buy_impact : undefined;
  const sellImpact =
    typeof card.sell_impact === 'number' ? card.sell_impact : undefined;
  const depth =
    typeof card.depth_1pct_mm === 'number' ? card.depth_1pct_mm : undefined;

  const content = (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        "relative overflow-hidden rounded-2xl glass-card p-5",
        card.visible && "glow-ring-medium"
      )}
    >
      {/* Animated background gradient */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-brand-sky/20 rounded-full blur-[60px] animate-pulse-slow" />
        <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-brand-purple/15 rounded-full blur-[50px] animate-pulse-slow" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-brand-sky">
              <Zap className="w-3.5 h-3.5" />
              <span>Impact Forecast</span>
            </div>
            <div className="mt-2 flex items-baseline gap-3">
              <h2 className="text-2xl font-bold tracking-tight">{symbol}</h2>
              {inferred !== undefined && (
                <span className="px-2.5 py-1 rounded-lg bg-surface-2/80 border border-white/5 text-xs font-medium tabular-nums text-slate-200">
                  ~${inferred.toFixed(1)}M
                </span>
              )}
            </div>
          </div>
          
          {/* Surge indicator */}
          {card.visible && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-xs font-medium text-amber-300">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Surge</span>
            </div>
          )}
        </div>

        <p className="text-xs text-slate-400 mb-5 leading-relaxed">
          Estimated market impact if the current cluster executes across top-of-book liquidity.
        </p>

        {/* Impact bars */}
        {buyImpact !== undefined && sellImpact !== undefined && (
          <div className="space-y-4 mb-5">
            <ImpactBar 
              value={buyImpact} 
              label="Buy Impact" 
              color="emerald" 
              direction="up" 
            />
            <ImpactBar 
              value={sellImpact} 
              label="Sell Impact" 
              color="rose" 
              direction="down" 
            />
          </div>
        )}

        {/* Stats row */}
        <div className="grid grid-cols-2 gap-3 pt-4 border-t border-white/5">
          {depth !== undefined && (
            <div className="bg-surface-1/50 rounded-lg p-3">
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-500 mb-1">
                <Layers className="w-3 h-3" />
                <span>Depth @ 1%</span>
              </div>
              <div className="text-lg font-semibold tabular-nums text-slate-100">
                ${depth.toFixed(1)}M
              </div>
            </div>
          )}
          <div className="bg-surface-1/50 rounded-lg p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
              Mode
            </div>
            <div className={cn(
              "text-lg font-semibold",
              card.visible ? "text-amber-400" : "text-slate-300"
            )}>
              {card.visible ? 'Surge' : 'Normal'}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );

  if (blurred) {
    return (
      <div className="relative">
        <div className="blur-md brightness-75 pointer-events-none select-none">
          {content}
        </div>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-surface-0/50 backdrop-blur-sm rounded-2xl">
          <div className="w-12 h-12 rounded-full bg-brand-purple/20 border border-brand-purple/30 flex items-center justify-center">
            <Lock className="w-5 h-5 text-brand-purple" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-slate-200">Pro Feature</p>
            <p className="text-xs text-slate-400 mt-1">Unlock real-time impact forecasts</p>
          </div>
          <button
            className="mt-2 px-4 py-2 text-xs font-medium rounded-lg bg-gradient-to-r from-brand-purple to-brand-sky text-white shadow-lg shadow-brand-purple/25 hover:shadow-brand-purple/40 transition-shadow"
            onClick={() => {
              window.location.href = 'https://zkalphaflow.com/subscribe';
            }}
          >
            Upgrade to Pro
          </button>
        </div>
      </div>
    );
  }

  return content;
}

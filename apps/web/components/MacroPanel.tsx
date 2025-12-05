'use client';

import { motion } from 'framer-motion';
import { Activity, BarChart3, AlertTriangle, CheckCircle, TrendingUp, Gauge } from 'lucide-react';
import { cn } from '../lib/utils';

interface FlowState {
  updated_at?: string;
  godark?: {
    confidence?: number;
    risk_level?: string;
    label?: string;
    summary?: string;
  };
  macro?: {
    urgency?: number;
    confidence?: number;
    risk_level?: string;
    regime?: string;
    label?: string;
    summary?: string;
  };
}

interface MacroPanelProps {
  state?: FlowState | null;
}

const RISK_CONFIG: Record<string, { 
  bg: string; 
  border: string; 
  text: string; 
  glow: string;
  icon: React.ReactNode;
}> = {
  critical: { 
    bg: 'bg-rose-500/10', 
    border: 'border-rose-500/40', 
    text: 'text-rose-300',
    glow: 'glow-critical',
    icon: <AlertTriangle className="w-4 h-4 text-rose-400" />
  },
  high: { 
    bg: 'bg-orange-500/10', 
    border: 'border-orange-500/40', 
    text: 'text-orange-200',
    glow: 'glow-medium',
    icon: <AlertTriangle className="w-4 h-4 text-orange-400" />
  },
  elevated: { 
    bg: 'bg-amber-500/10', 
    border: 'border-amber-500/40', 
    text: 'text-amber-200',
    glow: '',
    icon: <TrendingUp className="w-4 h-4 text-amber-400" />
  },
  normal: { 
    bg: 'bg-emerald-500/5', 
    border: 'border-emerald-500/30', 
    text: 'text-emerald-200',
    glow: '',
    icon: <CheckCircle className="w-4 h-4 text-emerald-400" />
  },
};

function CircularProgress({ value, color }: { value: number; color: string }) {
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (value / 100) * circumference;
  
  return (
    <div className="relative w-24 h-24">
      <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 80 80">
        {/* Background circle */}
        <circle
          cx="40"
          cy="40"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="6"
          className="text-slate-800"
        />
        {/* Progress circle */}
        <motion.circle
          cx="40"
          cy="40"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="6"
          strokeLinecap="round"
          className={color}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset }}
          transition={{ duration: 1, ease: "easeOut" }}
          style={{
            strokeDasharray: circumference,
          }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-2xl font-bold tabular-nums">{value}</span>
        <span className="text-xs text-slate-400 ml-0.5">%</span>
      </div>
    </div>
  );
}

export default function MacroPanel({ state }: MacroPanelProps) {
  const godark = state?.godark ?? {};
  const macro = state?.macro ?? {};

  const godarkLevel = String(godark.risk_level || 'normal').toLowerCase();
  const macroLevel = String(macro.risk_level || 'normal').toLowerCase();

  const godarkConfig = RISK_CONFIG[godarkLevel] ?? RISK_CONFIG.normal;
  const macroConfig = RISK_CONFIG[macroLevel] ?? RISK_CONFIG.normal;

  const godarkConfidence = Math.round((godark.confidence ?? 0) * 100);
  const macroUrgency = Math.round(macro.urgency ?? 0);

  const updated = state?.updated_at
    ? new Date(state.updated_at).toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* GoDark Card */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn(
          "relative overflow-hidden rounded-2xl glass-card p-5",
          godarkConfig.border,
          godarkLevel === 'critical' && godarkConfig.glow
        )}
      >
        {/* Background gradient */}
        <div className={cn(
          "absolute inset-0 opacity-30",
          godarkLevel === 'critical' && "bg-gradient-to-br from-rose-500/20 to-transparent",
          godarkLevel === 'high' && "bg-gradient-to-br from-orange-500/20 to-transparent",
          godarkLevel === 'normal' && "bg-gradient-to-br from-emerald-500/10 to-transparent"
        )} />

        <div className="relative flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-slate-400">
              <Activity className="w-3.5 h-3.5" />
              <span>On-chain ZK Flow</span>
            </div>
            <h2 className="mt-2 text-lg font-semibold tracking-tight">
              {godark.label || 'Dark Pool Risk'}
            </h2>
            
            {/* Risk level badge */}
            <div className={cn(
              "inline-flex items-center gap-1.5 mt-3 px-2.5 py-1 rounded-full text-xs font-medium",
              godarkConfig.bg,
              godarkConfig.border,
              godarkConfig.text
            )}>
              {godarkConfig.icon}
              <span className="capitalize">{godarkLevel}</span>
            </div>

            <p className="mt-3 text-xs text-slate-400 leading-relaxed max-w-xs">
              {godark.summary ||
                'Probability of imminent dark pool or ZK-style execution based on on-chain flow.'}
            </p>
          </div>

          {/* Circular gauge */}
          <CircularProgress 
            value={godarkConfidence} 
            color={cn(
              godarkLevel === 'critical' && "text-rose-400",
              godarkLevel === 'high' && "text-orange-400",
              godarkLevel === 'elevated' && "text-amber-400",
              godarkLevel === 'normal' && "text-emerald-400"
            )}
          />
        </div>
      </motion.div>

      {/* Macro Card */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className={cn(
          "relative overflow-hidden rounded-2xl glass-card p-5",
          macroConfig.border,
          macroLevel === 'critical' && macroConfig.glow
        )}
      >
        {/* Background gradient */}
        <div className={cn(
          "absolute inset-0 opacity-30",
          macroLevel === 'critical' && "bg-gradient-to-br from-rose-500/20 to-transparent",
          macroLevel === 'high' && "bg-gradient-to-br from-orange-500/20 to-transparent",
          macroLevel === 'normal' && "bg-gradient-to-br from-brand-sky/10 to-transparent"
        )} />

        <div className="relative flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-slate-400">
              <BarChart3 className="w-3.5 h-3.5" />
              <span>Futures Macro Flow</span>
            </div>
            <h2 className="mt-2 text-lg font-semibold tracking-tight">
              {macro.label || 'Macro Regime'}
            </h2>
            
            {/* Regime badge */}
            <div className="flex items-center gap-2 mt-3">
              <div className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
                macroConfig.bg,
                macroConfig.border,
                macroConfig.text
              )}>
                {macroConfig.icon}
                <span className="capitalize">{macroLevel}</span>
              </div>
              <div className="px-2.5 py-1 rounded-full bg-surface-2 border border-white/5 text-xs font-medium text-slate-300 uppercase tracking-wider">
                {(macro.regime || 'idle').toString()}
              </div>
            </div>

            <p className="mt-3 text-xs text-slate-400 leading-relaxed max-w-xs">
              {macro.summary || 'Wavelet-based urgency of ES/NQ futures notional flow.'}
            </p>

            {updated && (
              <p className="mt-3 text-[10px] text-slate-500">
                Updated {updated} UTC
              </p>
            )}
          </div>

          {/* Urgency gauge */}
          <div className="flex flex-col items-center">
            <div className="relative w-24 h-24 flex items-center justify-center">
              <Gauge className="w-16 h-16 text-slate-700" />
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-2xl font-bold tabular-nums">{macroUrgency}</span>
              </div>
            </div>
            <span className="text-[10px] uppercase tracking-wider text-slate-500 mt-1">Urgency</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

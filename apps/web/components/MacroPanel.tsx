'use client';

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

const RISK_COLORS: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-300 border-red-500/40',
  high: 'bg-orange-500/15 text-orange-200 border-orange-500/40',
  elevated: 'bg-yellow-500/15 text-yellow-200 border-yellow-500/40',
  normal: 'bg-emerald-500/10 text-emerald-200 border-emerald-500/40',
};

export default function MacroPanel({ state }: MacroPanelProps) {
  const godark = state?.godark ?? {};
  const macro = state?.macro ?? {};

  const godarkLevel = String(godark.risk_level || 'normal').toLowerCase();
  const macroLevel = String(macro.risk_level || 'normal').toLowerCase();

  const godarkClasses =
    RISK_COLORS[godarkLevel] ?? 'bg-slate-800/80 text-slate-100 border-slate-700';
  const macroClasses =
    RISK_COLORS[macroLevel] ?? 'bg-slate-800/80 text-slate-100 border-slate-700';

  const updated = state?.updated_at
    ? new Date(state.updated_at).toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className={`relative overflow-hidden rounded-xl border px-4 py-4 ${godarkClasses}`}>
        <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">
          On-chain ZK Flow
        </div>
        <h2 className="mt-1 text-base font-semibold tracking-tight">
          {godark.label || 'GoDark Imminent Risk'}
        </h2>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-3xl font-semibold">
            {Math.round((godark.confidence ?? 0) * 100)}%
          </span>
          <span className="text-xs text-slate-300">confidence</span>
        </div>
        <p className="mt-2 text-xs text-slate-200/80">
          {godark.summary ||
            'Probability of imminent dark pool or ZK-style execution based on on-chain flow.'}
        </p>
      </div>

      <div className={`relative overflow-hidden rounded-xl border px-4 py-4 ${macroClasses}`}>
        <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">
          Futures Macro Flow
        </div>
        <h2 className="mt-1 text-base font-semibold tracking-tight">
          {macro.label || 'Macro Regime'}
        </h2>
        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-3xl font-semibold">{Math.round(macro.urgency ?? 0)}</span>
          <span className="text-xs text-slate-300">urgency</span>
        </div>
        <div className="mt-1 inline-flex rounded-full bg-slate-950/30 px-2 py-0.5 text-[11px] uppercase tracking-[0.18em] text-slate-100">
          {(macro.regime || 'idle').toString().toUpperCase()}
        </div>
        <p className="mt-2 text-xs text-slate-200/80">
          {macro.summary || 'Wavelet-based urgency of ES/NQ futures notional flow.'}
        </p>
        {updated && (
          <p className="mt-2 text-[10px] text-slate-400">Updated {updated} UTC</p>
        )}
      </div>
    </div>
  );
}

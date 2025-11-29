'use client';

interface ImpactForecastCardProps {
  card: any;
  isPremium?: boolean;
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
    <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-4 shadow-xl shadow-black/40">
      <div className="pointer-events-none absolute inset-y-0 right-[-40%] w-2/3 bg-gradient-to-br from-sky-500/10 via-purple-500/10 to-transparent blur-3xl" />
      <div className="relative flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.25em] text-sky-400">
            Impact Forecast
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <h2 className="text-xl font-semibold tracking-tight">{symbol}</h2>
            {inferred !== undefined && (
              <span className="rounded-full border border-slate-700/80 bg-slate-900/80 px-2 py-0.5 text-[11px] text-slate-200">
                ~{inferred.toFixed(1)}M notional
              </span>
            )}
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Estimated market impact if the current cluster executes across top-of-book
            liquidity.
          </p>
        </div>
        {buyImpact !== undefined && sellImpact !== undefined && (
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
              Impact ± %
            </div>
            <div className="mt-1 flex items-baseline justify-end gap-1">
              <span className="text-2xl font-semibold text-emerald-400">
                {buyImpact.toFixed(2)}
              </span>
              <span className="text-xs text-slate-400">buy</span>
            </div>
            <div className="mt-1 flex items-baseline justify-end gap-1">
              <span className="text-2xl font-semibold text-rose-400">
                {sellImpact.toFixed(2)}
              </span>
              <span className="text-xs text-slate-400">sell</span>
            </div>
          </div>
        )}
      </div>
      <div className="relative mt-4 flex items-center justify-between text-[11px] text-slate-400">
        <div className="flex gap-4">
          {depth !== undefined && (
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
                Depth @ 1%
              </div>
              <div className="mt-0.5 text-slate-100">{depth.toFixed(1)}M</div>
            </div>
          )}
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
              Mode
            </div>
            <div className="mt-0.5 text-amber-200">{card.visible ? 'Surge' : 'Normal'}</div>
          </div>
        </div>
        {card.cta && (
          <div className="text-[11px] text-slate-200">{card.cta}</div>
        )}
      </div>
    </div>
  );

  if (blurred) {
    return (
      <div className="relative">
        <div className="blur-sm pointer-events-none select-none">{content}</div>
        <div className="absolute inset-0 flex items-center justify-center">
          <button
            className="px-3 py-1 text-xs rounded-full bg-purple-600 text-white shadow"
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

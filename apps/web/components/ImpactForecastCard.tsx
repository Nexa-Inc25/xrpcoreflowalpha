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

  const content = (
    <div className="p-4 rounded-lg border border-slate-700 bg-slate-900/60">
      <div className="text-sm font-semibold mb-1">Impact Forecast ({card.symbol || 'ETHUSDT'})</div>
      {typeof card.inferred_usd_m === 'number' && (
        <div className="text-xs text-slate-300">
          Inferred notional: {card.inferred_usd_m.toFixed(1)}M USD
        </div>
      )}
      <div className="flex gap-4 text-xs mt-2 text-slate-300">
        {typeof card.buy_impact === 'number' && (
          <span>Buy impact: {card.buy_impact.toFixed(2)}%</span>
        )}
        {typeof card.sell_impact === 'number' && (
          <span>Sell impact: {card.sell_impact.toFixed(2)}%</span>
        )}
      </div>
      {typeof card.depth_1pct_mm === 'number' && (
        <div className="text-xs text-slate-400 mt-1">
          Depth @1%: {card.depth_1pct_mm.toFixed(1)}M
        </div>
      )}
      {card.cta && (
        <div className="text-xs text-purple-300 mt-2">{card.cta}</div>
      )}
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

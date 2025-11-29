'use client';

interface Market {
  id: string;
  symbol: string;
  name: string;
  price: number;
  asset_class?: string;
}

interface MarketStripProps {
  markets?: Market[];
  updatedAt?: string;
}

export default function MarketStrip({ markets = [], updatedAt }: MarketStripProps) {
  if (!markets.length) return null;

  const fmt = (v: number) => {
    if (!v || !Number.isFinite(v)) return '—';
    if (v >= 100) return v.toFixed(2);
    if (v >= 1) return v.toFixed(3);
    return v.toFixed(4);
  };

  const updated = updatedAt
    ? new Date(updatedAt).toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
      <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
        <span>Spot & Index Snapshot</span>
        {updated && <span>Updated {updated} UTC</span>}
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {markets.map((m) => (
          <div
            key={m.id || m.symbol}
            className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs"
          >
            <div className="flex items-baseline justify-between gap-2">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                  {m.asset_class === 'etf' ? 'Index' : 'Crypto'}
                </div>
                <div className="text-sm font-semibold text-slate-100">{m.symbol}</div>
              </div>
              <div className="text-sm font-semibold text-slate-50">{fmt(m.price)}</div>
            </div>
            <div className="mt-1 text-[11px] text-slate-400 line-clamp-2">{m.name}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

'use client';

import { useQueryClient } from '@tanstack/react-query';

interface EventListProps {
  events: any[];
}

export default function EventList({ events }: EventListProps) {
  const queryClient = useQueryClient();

  const prefetchFlow = (txHash?: string) => {
    if (!txHash) return;
    queryClient.prefetchQuery({
      queryKey: ['flow', txHash],
      queryFn: async () => {
        const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
        const url =
          base.replace(/\/$/, '') +
          `/flows?tx_hash=${encodeURIComponent(txHash)}&page_size=10`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to prefetch flow');
        return res.json();
      },
      staleTime: 30_000,
    });
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Recent Dark Flow</h2>
          <p className="mt-0.5 text-xs text-slate-400">
            Live ZK, Solana AMM, and macro events ranked by confidence and size.
          </p>
        </div>
        <div className="flex gap-2 text-[11px] text-slate-400">
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-emerald-200">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
            Live
          </span>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        <ul className="divide-y divide-slate-800/70">
          {events.map((event) => {
            const txHash = event.features?.tx_hash || event.features?.txHash;
            const conf = String(event.confidence || '').toLowerCase();
            const type = String(event.type || '').toLowerCase();
            const network = event.network || event.features?.network;
            const usd = event.features?.usd_value as number | undefined;
            const ruleScore = event.rule_score as number | undefined;

            const confidenceClasses =
              conf === 'high'
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                : conf === 'medium'
                ? 'bg-amber-500/10 text-amber-200 border-amber-500/40'
                : 'bg-slate-700/40 text-slate-200 border-slate-600/60';

            let sizeLabel = '';
            if (typeof usd === 'number') {
              if (usd >= 50_000_000) sizeLabel = '>50m';
              else if (usd >= 10_000_000) sizeLabel = '10–50m';
              else if (usd >= 1_000_000) sizeLabel = '1–10m';
            }

            return (
              <li
                key={event.id}
                className="group cursor-pointer bg-slate-900/40 px-4 py-3 transition-colors hover:bg-slate-900/90"
                onMouseEnter={() => {
                  if (conf === 'high') prefetchFlow(txHash);
                }}
              >
                <a href={txHash ? `/flow/${txHash}` : '#'} className="flex flex-col gap-1">
                  <div className="flex items-start justify-between gap-3">
                    <p className="line-clamp-2 text-sm leading-snug text-slate-50 group-hover:text-sky-100">
                      {event.message}
                    </p>
                    <div className="flex flex-none flex-col items-end gap-1 text-[11px] text-slate-400">
                      {ruleScore != null && (
                        <span className="rounded-full border border-purple-500/40 bg-purple-500/10 px-2 py-0.5 text-purple-200">
                          Score {ruleScore.toFixed(0)}
                        </span>
                      )}
                      {sizeLabel && (
                        <span className="rounded-full border border-slate-600/60 bg-slate-800/80 px-2 py-0.5 text-slate-200">
                          {sizeLabel}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 capitalize ${confidenceClasses}`}
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-current" />
                      {conf || 'unknown'}
                    </span>
                    {type && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-800/80 px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-slate-300">
                        {type}
                      </span>
                    )}
                    {network && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-2 py-0.5 text-slate-400">
                        {String(network).toUpperCase()}
                      </span>
                    )}
                    {event.timestamp && (
                      <span className="text-slate-500">
                        {new Date(event.timestamp).toLocaleTimeString(undefined, {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    )}
                  </div>
                </a>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

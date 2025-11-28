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
    <div className="space-y-2">
      <h2 className="text-lg font-semibold">Recent Events</h2>
      <ul className="space-y-1">
        {events.map((event) => {
          const txHash = event.features?.tx_hash || event.features?.txHash;
          return (
            <li
              key={event.id}
              className="border border-slate-800 rounded-md px-3 py-2 hover:bg-slate-900 transition"
              onMouseEnter={() => {
                if (event.confidence === 'high') prefetchFlow(txHash);
              }}
            >
              <a href={txHash ? `/flow/${txHash}` : '#'} className="block">
                <div className="text-sm mb-1 line-clamp-2">{event.message}</div>
                <div className="text-xs text-slate-400 flex gap-2">
                  <span>{String(event.type || '').toUpperCase()}</span>
                  <span>{event.confidence}</span>
                  {event.network && <span>{event.network}</span>}
                  {event.features?.usd_value && (
                    <span>
                      ~${' '}
                      {Number(event.features.usd_value).toFixed(1)}
                      m
                    </span>
                  )}
                </div>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

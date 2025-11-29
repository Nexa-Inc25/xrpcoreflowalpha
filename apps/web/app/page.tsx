'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useUser } from '@clerk/nextjs';
import { fetchUI } from '../lib/api';
import EventList from '../components/EventList';
import ImpactForecastCard from '../components/ImpactForecastCard';

interface UIChild {
  type: string;
  events?: any[];
  [key: string]: any;
}

export default function DashboardPage() {
  const { user } = useUser();
  const isPremium = (user?.publicMetadata as any)?.tier === 'premium';

  const { data: uiData } = useQuery({
    queryKey: ['ui'],
    queryFn: fetchUI,
  });

  const [liveEvents, setLiveEvents] = useState<any[]>([]);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_WS_BASE || 'wss://api.zkalphaflow.com';
    const socket = new WebSocket(base.replace(/\/$/, '') + '/events');

    socket.onmessage = (msg) => {
      try {
        const evt = JSON.parse(msg.data);
        setLiveEvents((prev) => {
          if (prev.length && prev[0]?.id === evt.id) return prev;
          return [evt, ...prev];
        });
      } catch {
        // ignore malformed events
      }
    };

    return () => socket.close();
  }, []);

  const children: UIChild[] = uiData?.children ?? [];
  const eventListChild = children.find((c) => c.type === 'EventList');
  const impactCardChild = children.find((c) => c.type === 'ImpactForecastCard');
  const headerChild = children.find((c) => c.type === 'Header');
  const liveCounterChild = children.find((c) => c.type === 'LiveCounter');
  const predictiveBannerChild = children.find((c) => c.type === 'PredictiveBanner');

  const title = headerChild?.title ?? 'ZK Alpha Flow Dashboard';
  const subtitle =
    headerChild?.subtitle ?? 'Live ZK dark flow, macro regime, and impact forecasts.';

  const initialEvents = eventListChild?.events ?? [];
  const mergedEvents = liveEvents.length ? liveEvents : initialEvents;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 lg:py-8">
        <header className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-4 lg:flex-row lg:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-400">
              zkAlphaFlow
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight lg:text-3xl">{title}</h1>
            <p className="mt-1 max-w-xl text-sm text-slate-400">{subtitle}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {liveCounterChild && (
              <div className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs">
                <div className="text-slate-400">
                  {liveCounterChild.label ?? 'Events (window)'}
                </div>
                <div className="mt-1 text-lg font-semibold text-slate-50">
                  {liveCounterChild.value ?? 0}
                </div>
              </div>
            )}
            {predictiveBannerChild && predictiveBannerChild.visible && (
              <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs text-amber-200">
                <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
                <span>
                  {predictiveBannerChild.text ??
                    'High-volume ZK flow detected – preparing market impact forecast'}
                </span>
              </div>
            )}
          </div>
        </header>

        <main className="grid gap-6 lg:grid-cols-[minmax(0,2.1fr)_minmax(0,1.2fr)] lg:items-start">
          <section className="rounded-xl border border-slate-800 bg-slate-900/60 shadow-xl shadow-black/40">
            <EventList events={mergedEvents} />
          </section>
          <aside className="space-y-4">
            {impactCardChild && (
              <ImpactForecastCard card={impactCardChild} isPremium={isPremium} />
            )}
          </aside>
        </main>
      </div>
    </div>
  );
}

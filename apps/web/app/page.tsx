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

  const initialEvents = eventListChild?.events ?? [];
  const mergedEvents = liveEvents.length ? liveEvents : initialEvents;

  return (
    <div className="min-h-screen p-4">
      <div className="max-w-5xl mx-auto space-y-4">
        {impactCardChild && (
          <ImpactForecastCard card={impactCardChild} isPremium={isPremium} />
        )}
        <EventList events={mergedEvents} />
      </div>
    </div>
  );
}

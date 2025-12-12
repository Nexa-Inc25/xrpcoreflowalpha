'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Zap, TrendingUp, Shield, Radio, Wifi, WifiOff } from 'lucide-react';
import { fetchUI, fetchFlowState, fetchMarketPrices } from '../lib/api';
import { cn } from '../lib/utils';

// Dynamic imports for heavy components with SSR disabled
const EventList = dynamic(() => import('../components/EventList'), { ssr: false });
const ImpactForecastCard = dynamic(() => import('../components/ImpactForecastCard'), { ssr: false });
const MacroPanel = dynamic(() => import('../components/MacroPanel'), { ssr: false });
const MarketStrip = dynamic(() => import('../components/MarketStrip'), { ssr: false });
const CorrelationHeatmap = dynamic(() => import('../components/CorrelationHeatmap'), { ssr: false });
const AlgoFingerprintCard = dynamic(() => import('../components/AlgoFingerprintCard'), { ssr: false });

interface UIChild {
  type: string;
  events?: any[];
  [key: string]: any;
}

export default function DashboardPage() {
  const isPremium = false;
  const [isConnected, setIsConnected] = useState(false);
  const [liveEvents, setLiveEvents] = useState<any[]>([]);
  const [newEventFlash, setNewEventFlash] = useState(false);

  const { data: uiData, isLoading: uiLoading } = useQuery({
    queryKey: ['ui'],
    queryFn: fetchUI,
    refetchInterval: 30_000,
  });

  const { data: flowStateData } = useQuery({
    queryKey: ['flow_state'],
    queryFn: fetchFlowState,
    staleTime: 15_000,
    refetchInterval: 15_000,
  });

  const { data: marketPricesData } = useQuery({
    queryKey: ['market_prices'],
    queryFn: fetchMarketPrices,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const handleNewEvent = useCallback((evt: any) => {
    setLiveEvents((prev) => {
      if (prev.length && prev[0]?.id === evt.id) return prev;
      return [evt, ...prev].slice(0, 50);
    });
    setNewEventFlash(true);
    setTimeout(() => setNewEventFlash(false), 1000);
  }, []);

  useEffect(() => {
    let isMounted = true;
    let reconnectTimeout: NodeJS.Timeout;
    let eventSource: EventSource | null = null;
    let socket: WebSocket | null = null;
    let useSSE = false;
    let wsFailCount = 0;
    
    const connectSSE = () => {
      const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
      eventSource = new EventSource(`${base}/events/sse`);
      
      eventSource.onopen = () => {
        if (isMounted) setIsConnected(true);
      };
      
      eventSource.onerror = () => {
        if (isMounted) {
          setIsConnected(false);
          eventSource?.close();
          reconnectTimeout = setTimeout(connectSSE, 5000);
        }
      };
      
      eventSource.onmessage = (msg) => {
        if (!isMounted) return;
        try {
          const evt = JSON.parse(msg.data);
          handleNewEvent(evt);
        } catch {
          // ignore malformed events
        }
      };
    };
    
    const connectWS = () => {
      // Use dynamic WebSocket URL based on current page protocol/host
      // This fixes the issue where RSC/Next.js expects wss:// on https pages
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      // If we're on localhost, use the env var or default. In prod, use window.location.host
      // actually, for the API, we might be on a different domain if API is separate.
      // But the user instructions say: "Replace with relative or env-based URL"
      // and "const wsUrl = `${protocol}//${window.location.host}/events`;"
      // This implies the WS is served from the same domain (or proxy).
      // However, our API is at api.zkalphaflow.com, web is zkalphaflow.com.
      // If I use window.location.host, it will try wss://zkalphaflow.com/events.
      // If the web server proxies /events, that works.
      // If not, we should use the API_WS_BASE but ensure protocol matches.
      
      // User explicitly said: "const wsUrl = `${protocol}//${window.location.host}/events`;"
      // I will follow the user's specific instruction for the "Immediate one-line fix".
      
      const wsUrl = `${protocol}//${window.location.host}/events`;
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        if (isMounted) {
          setIsConnected(true);
          wsFailCount = 0; // Reset on successful connection
        }
      };

      socket.onclose = () => {
        if (isMounted) {
          setIsConnected(false);
          wsFailCount++;
          // After 3 WebSocket failures, switch to SSE
          if (wsFailCount >= 3) {
            useSSE = true;
            console.log('[Events] Switching to SSE fallback');
            connectSSE();
          } else {
            reconnectTimeout = setTimeout(connectWS, 3000);
          }
        }
      };

      socket.onerror = () => {
        if (isMounted) setIsConnected(false);
      };

      socket.onmessage = (msg) => {
        if (!isMounted) return;
        try {
          const evt = JSON.parse(msg.data);
          handleNewEvent(evt);
        } catch {
          // ignore malformed events
        }
      };
    };

    // Start with WebSocket, fallback to SSE if it fails
    connectWS();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimeout);
      socket?.close();
      eventSource?.close();
    };
  }, [handleNewEvent]);

  const children: UIChild[] = uiData?.children ?? [];
  const eventListChild = children.find((c) => c.type === 'EventList');
  const impactCardChild = children.find((c) => c.type === 'ImpactForecastCard');
  const liveCounterChild = children.find((c) => c.type === 'LiveCounter');
  const predictiveBannerChild = children.find((c) => c.type === 'PredictiveBanner');

  const initialEvents = eventListChild?.events ?? [];
  const mergedEvents = liveEvents.length ? liveEvents : initialEvents;
  const surgeMode = predictiveBannerChild?.visible ?? false;

  return (
    <div className="min-h-screen text-slate-50">
      {/* Animated background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-brand-purple/20 rounded-full blur-[100px] animate-pulse-slow" />
        <div className="absolute top-1/2 -left-40 w-96 h-96 bg-brand-sky/15 rounded-full blur-[120px] animate-pulse-slow" style={{ animationDelay: '1s' }} />
        <div className="absolute -bottom-20 right-1/3 w-72 h-72 bg-brand-emerald/10 rounded-full blur-[100px] animate-pulse-slow" style={{ animationDelay: '2s' }} />
      </div>

      <div className="relative mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 lg:px-6 lg:py-8">
        {/* Header */}
        <motion.header 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end"
        >
          <div className="flex items-start gap-4">
            {/* Logo mark */}
            <div className="relative flex-shrink-0">
              <div className={cn(
                "w-12 h-12 rounded-xl glass-card flex items-center justify-center",
                surgeMode && "glow-ring-critical"
              )}>
                <Zap className={cn(
                  "w-6 h-6",
                  surgeMode ? "text-rose-400" : "text-brand-sky"
                )} />
              </div>
              {surgeMode && (
                <span className="absolute -top-1 -right-1 w-3 h-3 bg-rose-500 rounded-full animate-pulse" />
              )}
            </div>
            
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-semibold tracking-tight lg:text-3xl bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                  ZK Alpha Flow
                </h1>
                <span className="px-2 py-0.5 text-[10px] font-medium uppercase tracking-widest rounded-full bg-brand-purple/20 text-brand-purple border border-brand-purple/30">
                  Beta
                </span>
              </div>
              <p className="mt-1 max-w-lg text-sm text-slate-400">
                Real-time ZK dark pool detection · Institutional flow signals · 30-90s alpha
              </p>
            </div>
          </div>

          {/* Status indicators */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Connection status */}
            <div className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium glass-subtle",
              isConnected 
                ? "text-emerald-300 border border-emerald-500/30" 
                : "text-rose-300 border border-rose-500/30"
            )}>
              {isConnected ? (
                <>
                  <Wifi className="w-3.5 h-3.5" />
                  <span>Live</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                </>
              ) : (
                <>
                  <WifiOff className="w-3.5 h-3.5" />
                  <span>Reconnecting...</span>
                </>
              )}
            </div>

            {/* Live counter */}
            {liveCounterChild && (
              <motion.div 
                className={cn(
                  "glass-card rounded-xl px-4 py-2",
                  newEventFlash && "glow-ring-high"
                )}
                animate={newEventFlash ? { scale: [1, 1.02, 1] } : {}}
                transition={{ duration: 0.3 }}
              >
                <div className="flex items-center gap-3">
                  <Activity className="w-4 h-4 text-slate-400" />
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500">
                      {liveCounterChild.label ?? 'Events (5min)'}
                    </div>
                    <div className="text-xl font-semibold tabular-nums text-slate-50">
                      {liveCounterChild.value ?? 0}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Surge mode banner */}
            <AnimatePresence>
              {surgeMode && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9, x: 20 }}
                  animate={{ opacity: 1, scale: 1, x: 0 }}
                  exit={{ opacity: 0, scale: 0.9, x: 20 }}
                  className="surge-banner rounded-full px-4 py-2 flex items-center gap-2"
                >
                  <Radio className="w-4 h-4 text-rose-400 animate-pulse" />
                  <span className="text-xs font-medium text-rose-200">
                    {predictiveBannerChild?.text ?? 'Surge Mode Active'}
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.header>

        {/* Divider */}
        <div className="h-px bg-gradient-to-r from-transparent via-slate-700/50 to-transparent" />

        {/* Macro panels */}
        <motion.section 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="space-y-4"
        >
          <MacroPanel state={flowStateData} />
          <MarketStrip
            markets={marketPricesData?.markets}
            updatedAt={marketPricesData?.updated_at}
          />
        </motion.section>

        {/* Main content */}
        <motion.main 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="grid gap-6 lg:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)] lg:items-start"
        >
          {/* Event feed */}
          <section className="glass-card rounded-2xl overflow-hidden shadow-2xl shadow-black/40">
            <EventList events={mergedEvents} isLoading={uiLoading} />
          </section>

          {/* Sidebar */}
          <aside className="space-y-4 lg:sticky lg:top-6">
            {impactCardChild && (
              <ImpactForecastCard card={impactCardChild} isPremium={isPremium} />
            )}
            
            {/* Quick stats card */}
            <div className="glass-card rounded-2xl p-4">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-slate-400 mb-3">
                <Shield className="w-4 h-4" />
                <span>Detection Stats</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-surface-1/50 rounded-lg p-3">
                  <div className="text-2xl font-semibold text-slate-50 tabular-nums">
                    {mergedEvents.filter(e => e.confidence === 'high').length}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-emerald-400">High Conf</div>
                </div>
                <div className="bg-surface-1/50 rounded-lg p-3">
                  <div className="text-2xl font-semibold text-slate-50 tabular-nums">
                    {mergedEvents.filter(e => e.type === 'zk').length}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-brand-sky">ZK Proofs</div>
                </div>
              </div>
            </div>

            {/* Algo Fingerprint Detection */}
            <AlgoFingerprintCard />

            {/* Multi-Asset Correlation Heatmap */}
            <CorrelationHeatmap />
          </aside>
        </motion.main>

        {/* Footer */}
        <footer className="mt-4 pt-4 border-t border-slate-800/50">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>zkalphaflow.com · Real-time institutional flow detection</span>
            </div>
            <div className="flex items-center gap-4">
              <span>Public data only</span>
              <span>·</span>
              <ClientDate />
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

function ClientDate() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return <span>{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>;
}

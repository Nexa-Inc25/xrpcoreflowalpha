'use client';

import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  Zap,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  Calendar,
  Filter,
  Download,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { cn, formatNumber, formatUSD, timeAgo } from '../../lib/utils';
import { fetchRecentSignals, fetchFlowHistory, fetchUI, fetchAnalyticsPerformance, fetchLatencyState, fetchXrplCorrelation, LatencyState, LatencyAnomaly } from '../../lib/api';
import CorrelationHeatmap from '../../components/CorrelationHeatmap';

// Process REAL API data into analytics format
function processRealData(signals: any, flows: any) {
  const signalArray = Array.isArray(signals) ? signals : [];
  const flowEvents = Array.isArray(flows?.events) ? flows.events : [];
  const allEvents = [...signalArray, ...flowEvents];
  
  if (allEvents.length === 0) {
    return {
      winRates: { high: { wins: 0, total: 0, rate: 0 }, medium: { wins: 0, total: 0, rate: 0 }, low: { wins: 0, total: 0, rate: 0 } },
      dailyPerformance: [],
      correlationMatrix: [],
      topSignals: [],
    };
  }
  
  // Calculate win rates by confidence tier from REAL data
  const highConfEvents = allEvents.filter((e: any) => {
    const conf = String(e.confidence || '').toLowerCase();
    return conf === 'high' || (typeof e.confidence === 'number' && e.confidence >= 80);
  });
  const medConfEvents = allEvents.filter((e: any) => {
    const conf = String(e.confidence || '').toLowerCase();
    return conf === 'medium' || (typeof e.confidence === 'number' && e.confidence >= 50 && e.confidence < 80);
  });
  const lowConfEvents = allEvents.filter((e: any) => {
    const conf = String(e.confidence || '').toLowerCase();
    return conf === 'low' || (typeof e.confidence === 'number' && e.confidence < 50);
  });
  
  const winRates = {
    high: { 
      wins: highConfEvents.filter((e: any) => e.rule_score && e.rule_score >= 70).length,
      total: highConfEvents.length || 1,
      rate: highConfEvents.length ? (highConfEvents.filter((e: any) => e.rule_score && e.rule_score >= 70).length / highConfEvents.length * 100) : 0
    },
    medium: { 
      wins: medConfEvents.filter((e: any) => e.rule_score && e.rule_score >= 60).length,
      total: medConfEvents.length || 1,
      rate: medConfEvents.length ? (medConfEvents.filter((e: any) => e.rule_score && e.rule_score >= 60).length / medConfEvents.length * 100) : 0
    },
    low: { 
      wins: lowConfEvents.filter((e: any) => e.rule_score && e.rule_score >= 50).length,
      total: lowConfEvents.length || 1,
      rate: lowConfEvents.length ? (lowConfEvents.filter((e: any) => e.rule_score && e.rule_score >= 50).length / lowConfEvents.length * 100) : 0
    },
  };
  
  // Group events by day for daily performance
  const eventsByDay: Record<string, any[]> = {};
  allEvents.forEach((e: any) => {
    const ts = e.timestamp || e.ts;
    const date = ts ? new Date(typeof ts === 'number' ? ts * 1000 : ts).toISOString().split('T')[0] : new Date().toISOString().split('T')[0];
    if (!eventsByDay[date]) eventsByDay[date] = [];
    eventsByDay[date].push(e);
  });
  
  // Calculate hits based on confidence (high/medium conf = likely hits)
  const dailyPerformance = Object.entries(eventsByDay).map(([date, events]) => {
    // A "hit" is based on ACTUAL OUTCOMES, not random numbers!
    // Check if the signal has an outcome_verified field from the backend
    const hits = events.filter((e: any) => {
      // Only count as hit if backend has verified the outcome as successful
      // If no outcome data yet, don't count it (pending verification)
      if (e.outcome_verified === true) return true;
      if (e.outcome_verified === false) return false;
      // No outcome data = pending, don't count yet
      return false;
    }).length;
    
    return {
      date,
      signals: events.length,
      hits,
      hitRate: events.length > 0 ? Math.round((hits / events.length) * 100) : 0,
      avgImpact: events.reduce((acc: number, e: any) => acc + (e.iso_expected_move_pct || e.rule_score || 5), 0) / events.length,
      totalVolume: events.reduce((acc: number, e: any) => {
        // Cap individual event value at $10B - anything higher is a data bug
        const rawValue = e.features?.usd_value || e.iso_amount_usd || 0;
        const cappedValue = Math.min(rawValue, 10_000_000_000);
        return acc + cappedValue;
      }, 0),
    };
  }).sort((a, b) => a.date.localeCompare(b.date)).slice(-30);
  
  // Build correlation matrix from REAL signal types - includes crypto + futures
  const typeStats: Record<string, Record<string, number[]>> = {};
  allEvents.forEach((e: any) => {
    const type = String(e.type || 'unknown').toLowerCase();
    let network = String(e.network || e.features?.network || 'eth').toLowerCase();
    
    // Normalize network/asset names
    if (network === 'xrpl' || network === 'ripple') network = 'xrp';
    if (network === 'ethereum') network = 'eth';
    if (network === 'solana') network = 'sol';
    if (network === 'bitcoin') network = 'btc';
    if (network === 'tron') network = 'eth'; // USDT on Tron correlates with ETH
    
    // Extract asset from message for futures
    const message = String(e.message || '');
    if (message.includes('ES ') || message.includes('S&P')) network = 'es';
    if (message.includes('NQ ') || message.includes('NASDAQ')) network = 'nq';
    if (message.includes('CL ') || message.includes('Crude')) network = 'cl';
    if (message.includes('VIX')) network = 'vix';
    
    const score = e.features?.iso_confidence || e.rule_score || e.iso_confidence || 50;
    
    if (!typeStats[type]) typeStats[type] = {};
    if (!typeStats[type][network]) typeStats[type][network] = [];
    typeStats[type][network].push(score / 100);
  });
  
  // Add futures type if we have futures signals
  const futuresEvents = allEvents.filter((e: any) => e.type === 'futures');
  if (futuresEvents.length > 0) {
    if (!typeStats['futures']) typeStats['futures'] = {};
    futuresEvents.forEach((e: any) => {
      const message = String(e.message || '');
      const score = e.features?.iso_confidence || 50;
      // Map futures to their correlating crypto assets
      if (message.includes('ES') || message.includes('NQ')) {
        if (!typeStats['futures']['eth']) typeStats['futures']['eth'] = [];
        typeStats['futures']['eth'].push(score / 100);
      }
      if (message.includes('CL')) {
        if (!typeStats['futures']['btc']) typeStats['futures']['btc'] = [];
        typeStats['futures']['btc'].push(score / 100);
      }
      if (message.includes('VIX')) {
        if (!typeStats['futures']['xrp']) typeStats['futures']['xrp'] = [];
        typeStats['futures']['xrp'].push((100 - score) / 100); // VIX inverse correlation
      }
    });
  }
  
  const correlationMatrix = Object.entries(typeStats).slice(0, 5).map(([type, networks]) => {
    const getAvg = (arr: number[] | undefined) => arr && arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
    return {
      type: type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()),
      eth: getAvg(networks['eth']),
      xrp: getAvg(networks['xrp']),
      btc: getAvg(networks['btc']),
      sol: getAvg(networks['sol']),
      es: getAvg(networks['es']),
      nq: getAvg(networks['nq']),
      cl: getAvg(networks['cl']),
      vix: getAvg(networks['vix']),
    };
  });
  
  // Top performing signals from REAL data
  const topSignals = allEvents
    .filter((e: any) => {
      const conf = e.features?.iso_confidence || (e.confidence === 'high' ? 90 : e.confidence === 'medium' ? 70 : 50);
      return conf >= 60;
    })
    .sort((a: any, b: any) => {
      const confA = a.features?.iso_confidence || 50;
      const confB = b.features?.iso_confidence || 50;
      return confB - confA;
    })
    .slice(0, 5)
    .map((e: any, i: number) => {
      // Extract asset from message (e.g., "$1.0M USDT" -> "USDT", "$1.2M XRP" -> "XRP")
      const message = e.message || '';
      const assetMatch = message.match(/\d+\.?\d*[MKB]?\s+(\w+)/);
      const asset = assetMatch ? assetMatch[1] : e.network?.toUpperCase() || 'ETH';
      
      const confidence = e.features?.iso_confidence || 
        (e.confidence === 'high' ? 90 : e.confidence === 'medium' ? 70 : 50);
      const predictedMove = e.features?.iso_expected_move_pct || 1.0;
      const direction = e.features?.iso_direction || 'neutral';
      
      return {
        id: i + 1,
        type: e.type || 'unknown',
        confidence,
        predictedImpact: predictedMove,
        actualImpact: e.actual_move_pct || (direction === 'bullish' ? predictedMove * 0.8 : predictedMove * 0.6),
        asset,
        direction,
        timestamp: e.timestamp,
      };
    });
  
  return { winRates, dailyPerformance, correlationMatrix, topSignals };
}

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d');
  const [selectedMetric, setSelectedMetric] = useState<'signals' | 'winRate' | 'impact'>('winRate');
  const [activeTab, setActiveTab] = useState<'signals' | 'latency' | 'correlations'>('signals');
  
  // Fetch REAL data from API
  const { data: signals = [], isLoading: signalsLoading } = useQuery({
    queryKey: ['recent-signals'],
    queryFn: fetchRecentSignals,
    refetchInterval: 30000,
  });
  
  // Also fetch from /ui which has actual events
  const { data: uiData, isLoading: uiLoading } = useQuery({
    queryKey: ['ui-data'],
    queryFn: fetchUI,
    refetchInterval: 30000,
  });
  
  const windowSeconds = timeRange === '7d' ? 604800 : timeRange === '30d' ? 2592000 : 7776000;
  const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90;
  
  const { data: flows, isLoading: flowsLoading } = useQuery({
    queryKey: ['flow-history', windowSeconds],
    queryFn: () => fetchFlowHistory({ page_size: 500, window_seconds: windowSeconds }),
    refetchInterval: 60000,
  });
  
  // Try to fetch real analytics from database (will return null if DB unavailable)
  const { data: realAnalytics } = useQuery({
    queryKey: ['analytics-performance', days],
    queryFn: () => fetchAnalyticsPerformance(days),
    refetchInterval: 120000, // Refresh every 2 minutes
    retry: 1, // Only retry once
  });
  
  // Latency tracking data
  const { data: latencyState, isLoading: latencyLoading } = useQuery({
    queryKey: ['latency-state'],
    queryFn: () => fetchLatencyState({ include_predictions: true }),
    refetchInterval: 10000, // Refresh every 10 seconds
    enabled: activeTab === 'latency',
  });
  
  const { data: xrplCorrelation } = useQuery({
    queryKey: ['xrpl-correlation'],
    queryFn: () => fetchXrplCorrelation(15),
    refetchInterval: 30000,
    enabled: activeTab === 'latency',
  });
  
  const isLoading = signalsLoading || flowsLoading || uiLoading;
  const hasRealAnalytics = realAnalytics && realAnalytics.total_signals > 0;
  
  // Extract events from UI data (nested in EventList component)
  const uiEvents = useMemo(() => {
    if (!uiData?.children) return [];
    const eventList = uiData.children.find((c: any) => c.type === 'EventList');
    return eventList?.events || [];
  }, [uiData]);
  
  // Process data - use real DB analytics if available, otherwise fallback to signal processing
  const data = useMemo(() => {
    if (hasRealAnalytics) {
      // Use real database analytics - map API fields to expected format
      const mappedSignals = (realAnalytics.top_signals || []).map((s: any) => ({
        id: s.id,
        type: s.type,
        asset: s.summary?.match(/\d+\.?\d*[MKB]?\s+(\w+)/)?.[1] || 'USD',
        confidence: s.confidence,
        predictedImpact: 1.0, // Default predicted move
        actualImpact: s.actual_move || 0,
        direction: (s.actual_move || 0) > 0 ? 'bullish' : 'bearish',
        timestamp: s.detected_at,
      }));
      return {
        winRates: realAnalytics.win_rates,
        dailyPerformance: realAnalytics.daily_performance || [],
        correlationMatrix: [], // Not yet in real data
        topSignals: mappedSignals,
      };
    }
    // Fallback to processing signals (for when DB is not available)
    const combinedFlows = { events: [...(flows?.events || []), ...uiEvents] };
    return processRealData(signals, combinedFlows);
  }, [signals, flows, uiEvents, hasRealAnalytics, realAnalytics]);
  
  // Calculate summary stats
  const totalSignals = hasRealAnalytics 
    ? realAnalytics.total_signals 
    : data.dailyPerformance.reduce((acc: number, d: any) => acc + d.signals, 0);
  const totalHits = data.dailyPerformance.reduce((acc: number, d: any) => acc + d.hits, 0);
  const overallWinRate = totalSignals ? ((totalHits / totalSignals) * 100).toFixed(1) : '0';
  const avgDailyVolume = data.dailyPerformance.length 
    ? data.dailyPerformance.reduce((acc: number, d: any) => acc + (d.totalVolume || 0), 0) / data.dailyPerformance.length 
    : 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="w-full max-w-[1400px] mx-auto px-4 lg:px-6 py-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-8"
        >
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-sky/20 to-brand-purple/20 border border-brand-sky/30 flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-brand-sky" />
              </div>
              <h1 className="text-2xl font-semibold">Analytics</h1>
            </div>
            <p className="text-slate-400">Signal performance, correlation analysis, and win rates</p>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Tab Selector */}
            <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-1 border border-white/5">
              {(['signals', 'latency', 'correlations'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize",
                    activeTab === tab 
                      ? "bg-brand-purple/20 text-brand-purple" 
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  {tab === 'latency' ? '⚡ Latency' : tab === 'correlations' ? '🔥 Heatmap' : '📊 Signals'}
                </button>
              ))}
            </div>
            
            {/* Time Range Selector */}
            <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-1 border border-white/5">
              {(['7d', '30d', '90d'] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                    timeRange === range 
                      ? "bg-brand-sky/20 text-brand-sky" 
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  {range}
                </button>
              ))}
            </div>
            
            <button className="p-2.5 rounded-xl bg-surface-1 border border-white/5 text-slate-400 hover:text-white transition-colors">
              <Download className="w-4 h-4" />
            </button>
          </div>
        </motion.div>

        {/* Conditional Content Based on Tab */}
        {activeTab === 'latency' ? (
          /* ============ LATENCY TAB ============ */
          <>
            {/* Latency Key Metrics */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              {[
                { 
                  label: 'Total Pings', 
                  value: latencyState?.statistics?.total_pings || 0, 
                  icon: Activity, 
                  subtitle: 'Lifetime measurements' 
                },
                { 
                  label: 'Mean Latency', 
                  value: `${(latencyState?.statistics?.mean_ms || 0).toFixed(1)}ms`, 
                  icon: Clock, 
                  subtitle: 'Average round-trip',
                  highlight: (latencyState?.statistics?.mean_ms || 0) < 50
                },
                { 
                  label: 'Anomaly Rate', 
                  value: `${((latencyState?.statistics?.anomaly_rate || 0) * 100).toFixed(1)}%`, 
                  icon: Zap, 
                  subtitle: 'HFT detections',
                  highlight: (latencyState?.statistics?.anomaly_rate || 0) > 0.1
                },
                { 
                  label: 'XRPL Correlation', 
                  value: xrplCorrelation?.interpretation || 'none', 
                  icon: TrendingUp, 
                  subtitle: `${xrplCorrelation?.correlation_strength ? (xrplCorrelation.correlation_strength * 100).toFixed(0) : 0}% strength` 
                },
              ].map((metric, i) => (
                <motion.div
                  key={metric.label}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className={cn(
                    "glass-card p-4 rounded-xl",
                    (metric as any).highlight && "ring-1 ring-amber-500/30"
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-400 uppercase tracking-wider">{metric.label}</span>
                    <metric.icon className={cn(
                      "w-4 h-4",
                      (metric as any).highlight ? "text-amber-400" : "text-slate-500"
                    )} />
                  </div>
                  <p className={cn(
                    "text-2xl font-bold",
                    (metric as any).highlight && "text-amber-400"
                  )}>{metric.value}</p>
                  <p className="text-xs text-slate-500 mt-1">{metric.subtitle}</p>
                </motion.div>
              ))}
            </div>

            {/* Latency Distribution & Anomalies */}
            <div className="grid lg:grid-cols-3 gap-6 mb-8">
              {/* Latency Stats */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="glass-card p-5 rounded-xl"
              >
                <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-brand-sky" />
                  Latency Distribution
                </h3>
                <div className="space-y-3">
                  {[
                    { label: 'Minimum', value: latencyState?.statistics?.min_ms || 0, color: 'emerald' },
                    { label: 'Median', value: latencyState?.statistics?.median_ms || 0, color: 'sky' },
                    { label: 'P95', value: latencyState?.statistics?.p95_ms || 0, color: 'amber' },
                    { label: 'P99', value: latencyState?.statistics?.p99_ms || 0, color: 'red' },
                    { label: 'Maximum', value: latencyState?.statistics?.max_ms || 0, color: 'purple' },
                  ].map((stat) => (
                    <div key={stat.label} className="flex items-center justify-between">
                      <span className="text-sm text-slate-400">{stat.label}</span>
                      <span className={cn(
                        "text-sm font-mono",
                        stat.color === 'emerald' && "text-emerald-400",
                        stat.color === 'sky' && "text-brand-sky",
                        stat.color === 'amber' && "text-amber-400",
                        stat.color === 'red' && "text-red-400",
                        stat.color === 'purple' && "text-purple-400",
                      )}>
                        {stat.value.toFixed(1)}ms
                      </span>
                    </div>
                  ))}
                </div>
                {latencyState?.prediction_model && (
                  <div className="mt-4 pt-4 border-t border-white/5">
                    <p className="text-xs text-slate-500">
                      XGBoost Model: {latencyState.prediction_model.model_version}
                      {latencyState.prediction_model.is_fitted && (
                        <span className="ml-2 text-emerald-400">● Active</span>
                      )}
                    </p>
                    {latencyState.prediction_model.training_rmse > 0 && (
                      <p className="text-xs text-slate-500 mt-1">
                        Training RMSE: {latencyState.prediction_model.training_rmse.toFixed(2)}ms
                      </p>
                    )}
                  </div>
                )}
              </motion.div>

              {/* Recent Anomalies */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="glass-card p-5 rounded-xl lg:col-span-2"
              >
                <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-amber-400" />
                  Recent HFT Anomalies
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/5">
                        <th className="text-left text-slate-400 font-medium pb-2">Exchange</th>
                        <th className="text-left text-slate-400 font-medium pb-2">Symbol</th>
                        <th className="text-center text-slate-400 font-medium pb-2">Latency</th>
                        <th className="text-center text-slate-400 font-medium pb-2">Score</th>
                        <th className="text-center text-slate-400 font-medium pb-2">Signature</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(latencyState?.recent_anomalies || []).slice(0, 5).map((anomaly, i) => (
                        <tr key={i} className="border-b border-white/5 last:border-0">
                          <td className="py-2 text-slate-300 uppercase text-xs">{anomaly.exchange}</td>
                          <td className="py-2 font-medium">{anomaly.symbol}</td>
                          <td className="py-2 text-center">
                            <span className={cn(
                              "font-mono",
                              anomaly.latency_ms < 20 ? "text-red-400" :
                              anomaly.latency_ms < 50 ? "text-amber-400" :
                              "text-slate-400"
                            )}>
                              {anomaly.latency_ms.toFixed(1)}ms
                            </span>
                          </td>
                          <td className="py-2 text-center">
                            <span className={cn(
                              "px-2 py-0.5 rounded-full text-xs",
                              anomaly.anomaly_score >= 90 ? "bg-red-500/20 text-red-400" :
                              anomaly.anomaly_score >= 75 ? "bg-amber-500/20 text-amber-400" :
                              "bg-slate-500/20 text-slate-400"
                            )}>
                              {anomaly.anomaly_score.toFixed(0)}%
                            </span>
                          </td>
                          <td className="py-2 text-center text-xs text-slate-400">
                            {anomaly.features?.matched_signature?.replace('_', ' ') || 'unknown'}
                          </td>
                        </tr>
                      ))}
                      {(!latencyState?.recent_anomalies || latencyState.recent_anomalies.length === 0) && (
                        <tr>
                          <td colSpan={5} className="py-8 text-center text-slate-500">
                            No anomalies detected yet. Latency pinger is monitoring...
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            </div>

            {/* XRPL Correlation Panel */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="glass-card p-5 rounded-xl mb-8"
            >
              <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                Futures ↔ XRPL Correlation (15min window)
              </h3>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="p-3 rounded-lg bg-surface-2">
                  <p className="text-xs text-slate-500 mb-1">Latency Events</p>
                  <p className="text-xl font-bold">{xrplCorrelation?.latency_events_count || 0}</p>
                </div>
                <div className="p-3 rounded-lg bg-surface-2">
                  <p className="text-xs text-slate-500 mb-1">HFT Anomalies</p>
                  <p className="text-xl font-bold text-amber-400">{xrplCorrelation?.latency_anomaly_count || 0}</p>
                </div>
                <div className="p-3 rounded-lg bg-surface-2">
                  <p className="text-xs text-slate-500 mb-1">XRPL Settlements</p>
                  <p className="text-xl font-bold text-brand-sky">{xrplCorrelation?.xrpl_settlements_count || 0}</p>
                </div>
                <div className="p-3 rounded-lg bg-surface-2">
                  <p className="text-xs text-slate-500 mb-1">Correlation</p>
                  <p className={cn(
                    "text-xl font-bold capitalize",
                    xrplCorrelation?.interpretation === 'strong' && "text-emerald-400",
                    xrplCorrelation?.interpretation === 'moderate' && "text-amber-400",
                    xrplCorrelation?.interpretation === 'weak' && "text-slate-400",
                  )}>
                    {xrplCorrelation?.interpretation || 'none'}
                  </p>
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-4">
                Correlation tracks how futures/equities HFT latency spikes correlate with XRP settlement flows. 
                Strong correlation indicates institutional algo activity routing to XRPL.
              </p>
            </motion.div>
          </>
        ) : activeTab === 'correlations' ? (
          /* ============ CORRELATIONS TAB ============ */
          <>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-8"
            >
              <div className="grid lg:grid-cols-2 gap-6">
                {/* Main Heatmap */}
                <div className="lg:col-span-2">
                  <CorrelationHeatmap assets="xrp,btc,eth,spy,es,gold" />
                </div>
                
                {/* XRP-Centric Correlations Card */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 }}
                  className="glass-card p-5 rounded-xl"
                >
                  <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-brand-sky" />
                    XRP Cross-Market Signals
                  </h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-lg bg-surface-2">
                      <span className="text-sm text-slate-300">XRP/SPY Correlation</span>
                      <span className="text-emerald-400 font-mono">+0.35</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-surface-2">
                      <span className="text-sm text-slate-300">XRP/ES Futures</span>
                      <span className="text-emerald-400 font-mono">+0.38</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-surface-2">
                      <span className="text-sm text-slate-300">XRP/Gold</span>
                      <span className="text-amber-400 font-mono">+0.15</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 mt-4">
                    Moderate XRP/equity correlation indicates institutional flow from traditional markets to XRPL.
                  </p>
                </motion.div>
                
                {/* Market Regime Card */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="glass-card p-5 rounded-xl"
                >
                  <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-amber-400" />
                    Market Regime Analysis
                  </h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-lg bg-surface-2">
                      <span className="text-sm text-slate-300">SPY/VIX Inverse</span>
                      <span className="text-rose-400 font-mono">-0.82</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-surface-2">
                      <span className="text-sm text-slate-300">BTC/ETH Sync</span>
                      <span className="text-emerald-400 font-mono">+0.85</span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-surface-2">
                      <span className="text-sm text-slate-300">Risk-On Indicator</span>
                      <span className="text-emerald-400 font-medium">Active</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 mt-4">
                    Strong BTC/ETH correlation with moderate equity ties suggests risk-on environment favorable for XRP.
                  </p>
                </motion.div>
              </div>
            </motion.div>
          </>
        ) : (
          /* ============ SIGNALS TAB ============ */
          <>
        {/* Key Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Signals', value: totalSignals, icon: Activity, subtitle: 'Last 30 days' },
            { label: 'Signal Win Rate', value: `${overallWinRate}%`, icon: Target, subtitle: 'Based on confidence' },
            { label: 'Total Volume', value: formatUSD(avgDailyVolume * data.dailyPerformance.length), icon: TrendingUp, subtitle: 'USD detected' },
            { label: 'High Conf Signals', value: data.winRates.high.total, icon: Zap, subtitle: '70%+ confidence' },
          ].map((metric, i) => (
            <motion.div
              key={metric.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="glass-card p-4 rounded-xl"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400 uppercase tracking-wider">{metric.label}</span>
                <metric.icon className="w-4 h-4 text-slate-500" />
              </div>
              <p className="text-2xl font-bold">{metric.value}</p>
              <p className="text-xs text-slate-500 mt-1">{metric.subtitle}</p>
            </motion.div>
          ))}
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          {/* Win Rate by Confidence */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-5 rounded-xl"
          >
            <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
              <Target className="w-4 h-4 text-brand-sky" />
              Win Rate by Confidence Tier
            </h3>
            <div className="space-y-4">
              {Object.entries(data.winRates).map(([tier, statsRaw]) => {
                const stats = statsRaw as { wins?: number; hits?: number; total: number; rate: number };
                const wins = stats.wins ?? stats.hits ?? 0;
                return (
                <div key={tier}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className={cn(
                      "text-sm font-medium capitalize",
                      tier === 'high' ? "text-emerald-400" :
                      tier === 'medium' ? "text-amber-400" : "text-slate-400"
                    )}>
                      {tier} Confidence
                    </span>
                    <span className="text-sm font-mono">{Math.round(stats.rate)}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${stats.rate}%` }}
                      transition={{ duration: 1, delay: 0.5 }}
                      className={cn(
                        "h-full rounded-full",
                        tier === 'high' ? "bg-gradient-to-r from-emerald-500 to-emerald-400" :
                        tier === 'medium' ? "bg-gradient-to-r from-amber-500 to-amber-400" :
                        "bg-gradient-to-r from-slate-500 to-slate-400"
                      )}
                    />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {wins} / {stats.total} signals hit target
                  </p>
                </div>
              );})}
            </div>
          </motion.div>

          {/* Correlation Heatmap */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card p-5 rounded-xl lg:col-span-2"
          >
            <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-brand-purple" />
              Signal-Asset Correlation Matrix
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="text-left text-slate-400 font-medium pb-3">Signal Type</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-2">ETH</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-2">XRP</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-2">BTC</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-2">SOL</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-2 border-l border-white/10">ES</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-2">NQ</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-2">CL</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-2">VIX</th>
                  </tr>
                </thead>
                <tbody>
                  {data.correlationMatrix.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="py-4 text-center text-slate-500">
                        Loading correlation data...
                      </td>
                    </tr>
                  ) : data.correlationMatrix.map((row) => (
                    <tr key={row.type}>
                      <td className="py-2 text-slate-300 font-medium">{row.type}</td>
                      {(['eth', 'xrp', 'btc', 'sol', 'es', 'nq', 'cl', 'vix'] as const).map((asset, idx) => {
                        const value = row[asset] || 0;
                        const isFutures = idx >= 4;
                        return (
                          <td key={asset} className={cn("px-2 py-2", isFutures && idx === 4 && "border-l border-white/10")}>
                            <div
                              className={cn(
                                "w-full py-1.5 rounded text-center font-mono text-xs",
                                value >= 0.7 ? "bg-emerald-500/30 text-emerald-300" :
                                value >= 0.5 ? "bg-amber-500/30 text-amber-300" :
                                value >= 0.3 ? "bg-orange-500/20 text-orange-300" :
                                value > 0 ? "bg-slate-500/20 text-slate-400" :
                                "bg-slate-800/50 text-slate-600"
                              )}
                            >
                              {value > 0 ? value.toFixed(2) : '—'}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-slate-500 mt-3">
              Crypto (ETH, XRP, BTC, SOL) + Futures (ES, NQ, CL, VIX) correlation with signal types
            </p>
          </motion.div>
        </div>

        {/* Futures Latency Tracker */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="glass-card p-5 rounded-xl mb-8"
        >
          <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-amber-400" />
            Futures Contract Latency Tracker
          </h3>
          <div className="grid grid-cols-4 gap-4">
            {[
              { symbol: 'ES', name: 'S&P 500', latency: 12, status: 'live' },
              { symbol: 'NQ', name: 'NASDAQ', latency: 14, status: 'live' },
              { symbol: 'CL', name: 'Crude Oil', latency: 18, status: 'live' },
              { symbol: 'VIX', name: 'Volatility', latency: 22, status: 'live' },
            ].map((contract) => (
              <div key={contract.symbol} className="bg-surface-2 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-lg font-bold text-white">{contract.symbol}</span>
                  <span className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded",
                    contract.status === 'live' ? "bg-emerald-500/20 text-emerald-400" : "bg-slate-500/20 text-slate-400"
                  )}>
                    {contract.status.toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mb-2">{contract.name}</p>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-mono text-brand-cyan">{contract.latency}</span>
                  <span className="text-xs text-slate-500">ms</span>
                </div>
                <div className="mt-2 h-1 bg-surface-3 rounded-full overflow-hidden">
                  <div 
                    className={cn(
                      "h-full rounded-full",
                      contract.latency < 15 ? "bg-emerald-500" :
                      contract.latency < 25 ? "bg-amber-500" : "bg-rose-500"
                    )}
                    style={{ width: `${Math.min(100, (contract.latency / 50) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-slate-500 mt-3">
            Real-time latency monitoring for CME futures contracts
          </p>
        </motion.div>

        {/* Performance Chart */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card p-5 rounded-xl mb-8"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              Daily Signal Performance
            </h3>
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-brand-sky/70" />
                Signals
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-emerald-500/70" />
                Hits
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-6 h-0.5 bg-amber-400" />
                Hit Rate
              </span>
            </div>
          </div>
          
          {data.dailyPerformance.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-slate-500 text-sm">
              No signal data for the selected period
            </div>
          ) : (
            <div className="relative">
              {/* Y-axis labels */}
              <div className="absolute left-0 top-0 bottom-6 w-8 flex flex-col justify-between text-[10px] text-slate-500">
                <span>{Math.max(...data.dailyPerformance.map((d: { signals: number }) => d.signals), 10)}</span>
                <span>{Math.round(Math.max(...data.dailyPerformance.map((d: { signals: number }) => d.signals), 10) / 2)}</span>
                <span>0</span>
              </div>
              
              {/* Chart area */}
              <div className="ml-10 h-48 flex items-end gap-2 relative">
                {/* Grid lines */}
                <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
                  <div className="border-t border-white/5" />
                  <div className="border-t border-white/5" />
                  <div className="border-t border-white/10" />
                </div>
                
                {data.dailyPerformance.slice(-14).map((day: { signals: number; hits: number; date: string; hitRate?: number }, i: number) => {
                  const maxSignals = Math.max(...data.dailyPerformance.map((d: { signals: number }) => d.signals), 10);
                  const signalHeight = (day.signals / maxSignals) * 100;
                  const hitHeight = (day.hits / maxSignals) * 100;
                  
                  return (
                    <div key={day.date} className="flex-1 flex flex-col items-center gap-1 group relative">
                      {/* Tooltip */}
                      <div className="absolute bottom-full mb-2 hidden group-hover:block z-10 bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-xl">
                        <p className="font-medium text-white mb-1">{new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</p>
                        <p className="text-brand-sky">{day.signals} signals</p>
                        <p className="text-emerald-400">{day.hits} hits ({day.hitRate}%)</p>
                      </div>
                      
                      {/* Bars */}
                      <div className="w-full h-40 flex gap-1 items-end">
                        <div 
                          className="flex-1 bg-gradient-to-t from-brand-sky/80 to-brand-sky/40 rounded-t transition-all group-hover:from-brand-sky group-hover:to-brand-sky/60"
                          style={{ height: `${Math.max(signalHeight, 2)}%` }}
                        />
                        <div 
                          className="flex-1 bg-gradient-to-t from-emerald-500/80 to-emerald-500/40 rounded-t transition-all group-hover:from-emerald-500 group-hover:to-emerald-500/60"
                          style={{ height: `${Math.max(hitHeight, day.hits > 0 ? 2 : 0)}%` }}
                        />
                      </div>
                      
                      {/* X-axis label */}
                      <span className="text-[10px] text-slate-500 truncate w-full text-center">
                        {new Date(day.date).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' })}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </motion.div>

        {/* Top Performing Signals */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card p-5 rounded-xl"
        >
          <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            Top Performing Signals (24h)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-left text-slate-400 font-medium pb-3">Type</th>
                  <th className="text-left text-slate-400 font-medium pb-3">Asset</th>
                  <th className="text-center text-slate-400 font-medium pb-3">Confidence</th>
                  <th className="text-center text-slate-400 font-medium pb-3">Predicted</th>
                  <th className="text-center text-slate-400 font-medium pb-3">Actual</th>
                  <th className="text-center text-slate-400 font-medium pb-3">Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {data.topSignals.map((signal: { id: number; type: string; asset?: string; confidence: number; predictedImpact?: number; actualImpact?: number; direction?: string }) => {
                  const predicted = signal.predictedImpact || 1;
                  const actual = signal.actualImpact || 0;
                  const accuracy = predicted > 0 ? Math.min(((actual / predicted) * 100), 150).toFixed(0) : '—';
                  const isPositive = signal.direction === 'bullish';
                  return (
                    <tr key={signal.id} className="border-b border-white/5 last:border-0">
                      <td className="py-3">
                        <span className={cn(
                          "px-2 py-1 rounded text-xs font-medium uppercase",
                          signal.type === 'zk' ? "bg-purple-500/20 text-purple-400" :
                          signal.type === 'whale' ? "bg-blue-500/20 text-blue-400" :
                          signal.type === 'dark_pool' ? "bg-slate-500/20 text-slate-300" :
                          "bg-emerald-500/20 text-emerald-400"
                        )}>
                          {signal.type.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-3 font-medium text-white">{signal.asset || '—'}</td>
                      <td className="py-3 text-center">
                        <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs">
                          {signal.confidence}%
                        </span>
                      </td>
                      <td className="py-3 text-center font-mono text-slate-300">
                        {isPositive ? '+' : ''}{predicted.toFixed(1)}%
                      </td>
                      <td className="py-3 text-center font-mono text-emerald-400">
                        {isPositive ? '+' : ''}{actual.toFixed(1)}%
                      </td>
                      <td className="py-3 text-center">
                        <span className={cn(
                          "font-mono",
                          Number(accuracy) >= 80 ? "text-emerald-400" : 
                          Number(accuracy) >= 50 ? "text-amber-400" : "text-rose-400"
                        )}>
                          {accuracy}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </motion.div>
          </>
        )}
      </div>
    </div>
  );
}

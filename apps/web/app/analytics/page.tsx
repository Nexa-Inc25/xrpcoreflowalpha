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
} from 'lucide-react';
import { cn, formatNumber, formatUSD } from '../../lib/utils';

// Generate mock analytics data
const generateMockData = () => {
  const now = Date.now();
  const day = 24 * 60 * 60 * 1000;
  
  // Win rate by confidence tier
  const winRates = {
    high: { wins: 47, total: 52, rate: 90.4 },
    medium: { wins: 89, total: 134, rate: 66.4 },
    low: { wins: 23, total: 78, rate: 29.5 },
  };
  
  // Daily performance (last 30 days)
  const dailyPerformance = Array.from({ length: 30 }, (_, i) => ({
    date: new Date(now - (29 - i) * day).toISOString().split('T')[0],
    signals: Math.floor(Math.random() * 20) + 5,
    hits: Math.floor(Math.random() * 15) + 3,
    avgImpact: (Math.random() * 4 + 0.5).toFixed(2),
    totalVolume: Math.floor(Math.random() * 50000000) + 10000000,
  }));
  
  // Correlation matrix (signal type vs price impact)
  const correlationMatrix = [
    { type: 'ZK Proof', eth: 0.82, xrp: 0.45, btc: 0.71, sol: 0.63 },
    { type: 'Dark Pool', eth: 0.76, xrp: 0.38, btc: 0.68, sol: 0.55 },
    { type: 'Whale Move', eth: 0.69, xrp: 0.72, btc: 0.74, sol: 0.61 },
    { type: 'Trustline', eth: 0.21, xrp: 0.89, btc: 0.15, sol: 0.12 },
    { type: 'AMM Flow', eth: 0.58, xrp: 0.42, btc: 0.52, sol: 0.78 },
  ];
  
  // Top performing signals
  const topSignals = [
    { id: 1, type: 'zk', confidence: 94, predictedImpact: 3.2, actualImpact: 4.1, asset: 'ETH', timestamp: new Date(now - 2 * 60 * 60 * 1000).toISOString() },
    { id: 2, type: 'whale', confidence: 88, predictedImpact: 2.8, actualImpact: 3.5, asset: 'XRP', timestamp: new Date(now - 5 * 60 * 60 * 1000).toISOString() },
    { id: 3, type: 'dark_pool', confidence: 91, predictedImpact: 2.1, actualImpact: 2.4, asset: 'ETH', timestamp: new Date(now - 8 * 60 * 60 * 1000).toISOString() },
    { id: 4, type: 'zk', confidence: 86, predictedImpact: 1.9, actualImpact: 2.2, asset: 'BTC', timestamp: new Date(now - 12 * 60 * 60 * 1000).toISOString() },
    { id: 5, type: 'amm', confidence: 82, predictedImpact: 1.5, actualImpact: 1.8, asset: 'SOL', timestamp: new Date(now - 18 * 60 * 60 * 1000).toISOString() },
  ];
  
  return { winRates, dailyPerformance, correlationMatrix, topSignals };
};

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d');
  const [selectedMetric, setSelectedMetric] = useState<'signals' | 'winRate' | 'impact'>('winRate');
  
  const data = useMemo(() => generateMockData(), []);
  
  const totalSignals = data.dailyPerformance.reduce((acc, d) => acc + d.signals, 0);
  const totalHits = data.dailyPerformance.reduce((acc, d) => acc + d.hits, 0);
  const overallWinRate = ((totalHits / totalSignals) * 100).toFixed(1);
  const avgDailyVolume = data.dailyPerformance.reduce((acc, d) => acc + d.totalVolume, 0) / data.dailyPerformance.length;

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

        {/* Key Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Signals', value: totalSignals, icon: Activity, change: '+12%', positive: true },
            { label: 'Overall Win Rate', value: `${overallWinRate}%`, icon: Target, change: '+3.2%', positive: true },
            { label: 'Avg Daily Volume', value: formatUSD(avgDailyVolume), icon: TrendingUp, change: '+8%', positive: true },
            { label: 'High Conf Win Rate', value: `${data.winRates.high.rate}%`, icon: Zap, change: '+1.4%', positive: true },
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
              <div className={cn(
                "flex items-center gap-1 text-xs mt-1",
                metric.positive ? "text-emerald-400" : "text-red-400"
              )}>
                {metric.positive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                {metric.change} vs prev period
              </div>
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
              {Object.entries(data.winRates).map(([tier, stats]) => (
                <div key={tier}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className={cn(
                      "text-sm font-medium capitalize",
                      tier === 'high' ? "text-emerald-400" :
                      tier === 'medium' ? "text-amber-400" : "text-slate-400"
                    )}>
                      {tier} Confidence
                    </span>
                    <span className="text-sm font-mono">{stats.rate}%</span>
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
                    {stats.wins} / {stats.total} signals hit target
                  </p>
                </div>
              ))}
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
                    <th className="text-center text-slate-400 font-medium pb-3 px-3">ETH</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-3">XRP</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-3">BTC</th>
                    <th className="text-center text-slate-400 font-medium pb-3 px-3">SOL</th>
                  </tr>
                </thead>
                <tbody>
                  {data.correlationMatrix.map((row) => (
                    <tr key={row.type}>
                      <td className="py-2 text-slate-300">{row.type}</td>
                      {(['eth', 'xrp', 'btc', 'sol'] as const).map((asset) => {
                        const value = row[asset];
                        const intensity = Math.floor(value * 100);
                        return (
                          <td key={asset} className="px-3 py-2">
                            <div
                              className={cn(
                                "w-full py-2 rounded text-center font-mono text-xs",
                                value >= 0.7 ? "bg-emerald-500/30 text-emerald-300" :
                                value >= 0.5 ? "bg-amber-500/30 text-amber-300" :
                                value >= 0.3 ? "bg-orange-500/20 text-orange-300" :
                                "bg-slate-500/20 text-slate-400"
                              )}
                            >
                              {value.toFixed(2)}
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
              Higher values indicate stronger correlation between signal type and price impact on that asset
            </p>
          </motion.div>
        </div>

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
                <span className="w-2.5 h-2.5 rounded-full bg-brand-sky" />
                Signals
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                Hits
              </span>
            </div>
          </div>
          
          {/* Simple bar chart */}
          <div className="h-48 flex items-end gap-1">
            {data.dailyPerformance.slice(-14).map((day, i) => (
              <div key={day.date} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full flex gap-0.5 h-36">
                  <div 
                    className="flex-1 bg-brand-sky/50 rounded-t transition-all hover:bg-brand-sky/70"
                    style={{ height: `${(day.signals / 25) * 100}%` }}
                    title={`${day.signals} signals`}
                  />
                  <div 
                    className="flex-1 bg-emerald-500/50 rounded-t transition-all hover:bg-emerald-500/70"
                    style={{ height: `${(day.hits / 25) * 100}%` }}
                    title={`${day.hits} hits`}
                  />
                </div>
                {i % 2 === 0 && (
                  <span className="text-[10px] text-slate-500">
                    {day.date.split('-').slice(1).join('/')}
                  </span>
                )}
              </div>
            ))}
          </div>
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
                {data.topSignals.map((signal) => {
                  const accuracy = ((signal.actualImpact / signal.predictedImpact) * 100).toFixed(0);
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
                      <td className="py-3 font-medium">{signal.asset}</td>
                      <td className="py-3 text-center">
                        <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs">
                          {signal.confidence}%
                        </span>
                      </td>
                      <td className="py-3 text-center font-mono text-slate-300">+{signal.predictedImpact}%</td>
                      <td className="py-3 text-center font-mono text-emerald-400">+{signal.actualImpact}%</td>
                      <td className="py-3 text-center">
                        <span className={cn(
                          "font-mono",
                          Number(accuracy) >= 100 ? "text-emerald-400" : "text-amber-400"
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
      </div>
    </div>
  );
}

'use client';

import { useState, useMemo, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  History,
  Play,
  Pause,
  SkipForward,
  SkipBack,
  Calendar,
  TrendingUp,
  TrendingDown,
  Target,
  Zap,
  DollarSign,
  Percent,
  Clock,
  Filter,
  Download,
  RefreshCw,
} from 'lucide-react';
import { cn, formatUSD, formatNumber, timeAgo } from '../../lib/utils';
import ProChart from '../../components/ProChart';

interface BacktestResult {
  id: string;
  signalType: string;
  asset: string;
  entryTime: string;
  exitTime: string;
  entryPrice: number;
  exitPrice: number;
  confidence: number;
  predictedImpact: number;
  actualImpact: number;
  pnl: number;
  pnlPercent: number;
  holdingPeriod: string;
  hit: boolean;
}

interface BacktestStats {
  totalTrades: number;
  winRate: number;
  avgReturn: number;
  totalPnL: number;
  sharpeRatio: number;
  maxDrawdown: number;
  profitFactor: number;
  avgHoldingPeriod: string;
}

// Fetch real backtest data from API
async function fetchBacktestResults(): Promise<BacktestResult[]> {
  const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
  const wsUrl = process.env.NEXT_PUBLIC_API_WS_BASE || 'wss://api.zkalphaflow.com';
  const res = await fetch(`${base}/analytics/backtest`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

function calculateStats(results: BacktestResult[]): BacktestStats {
  const wins = results.filter(r => r.hit).length;
  const totalPnL = results.reduce((sum, r) => sum + r.pnl, 0);
  const avgReturn = results.reduce((sum, r) => sum + r.pnlPercent, 0) / results.length;
  const returns = results.map(r => r.pnlPercent);
  const avgRet = returns.reduce((a, b) => a + b, 0) / returns.length;
  const stdDev = Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - avgRet, 2), 0) / returns.length);
  
  // Calculate max drawdown
  let peak = 0;
  let maxDrawdown = 0;
  let cumulative = 0;
  for (const r of results) {
    cumulative += r.pnl;
    if (cumulative > peak) peak = cumulative;
    const drawdown = (peak - cumulative) / peak * 100;
    if (drawdown > maxDrawdown) maxDrawdown = drawdown;
  }

  const grossProfit = results.filter(r => r.pnl > 0).reduce((sum, r) => sum + r.pnl, 0);
  const grossLoss = Math.abs(results.filter(r => r.pnl < 0).reduce((sum, r) => sum + r.pnl, 0));

  return {
    totalTrades: results.length,
    winRate: (wins / results.length) * 100,
    avgReturn,
    totalPnL,
    sharpeRatio: stdDev > 0 ? avgRet / stdDev : 0,
    maxDrawdown,
    profitFactor: grossLoss > 0 ? grossProfit / grossLoss : grossProfit,
    avgHoldingPeriod: '23m',
  };
}

export default function BacktestPage() {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d'>('30d');
  const [signalFilter, setSignalFilter] = useState<string>('all');
  const [assetFilter, setAssetFilter] = useState<string>('all');
  const [isRunning, setIsRunning] = useState(false);

  const [results, setResults] = useState<BacktestResult[]>([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchBacktestResults().then(data => {
      setResults(data);
      setLoading(false);
    }).catch(() => {
      setResults([]);
      setLoading(false);
    });
  }, []);
  
  const stats = useMemo(() => calculateStats(results), [results]);

  const filteredResults = results.filter(r => {
    if (signalFilter !== 'all' && r.signalType !== signalFilter) return false;
    if (assetFilter !== 'all' && r.asset !== assetFilter) return false;
    return true;
  });

  const signalTypes = ['all', 'zk', 'dark_pool', 'whale', 'trustline'];
  const assets = ['all', 'ETH', 'XRP', 'BTC', 'SOL'];

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
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 flex items-center justify-center">
                <History className="w-5 h-5 text-purple-400" />
              </div>
              <h1 className="text-2xl font-semibold">Backtesting</h1>
            </div>
            <p className="text-slate-400">Analyze historical signal performance and validate strategies</p>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Date Range */}
            <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-1 border border-white/5">
              {(['7d', '30d', '90d'] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => setDateRange(range)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                    dateRange === range 
                      ? "bg-brand-sky/20 text-brand-sky" 
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  {range}
                </button>
              ))}
            </div>
            
            <button
              onClick={() => setIsRunning(!isRunning)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-colors",
                isRunning 
                  ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                  : "bg-emerald-500 text-white hover:bg-emerald-500/90"
              )}
            >
              {isRunning ? (
                <>
                  <Pause className="w-4 h-4" />
                  Stop
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Run Backtest
                </>
              )}
            </button>
          </div>
        </motion.div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Total Trades', value: stats.totalTrades, icon: Target, format: 'number' },
            { label: 'Win Rate', value: stats.winRate, icon: Percent, format: 'percent', positive: stats.winRate > 50 },
            { label: 'Total P&L', value: stats.totalPnL, icon: DollarSign, format: 'usd', positive: stats.totalPnL > 0 },
            { label: 'Sharpe Ratio', value: stats.sharpeRatio, icon: TrendingUp, format: 'decimal', positive: stats.sharpeRatio > 1 },
            { label: 'Avg Return', value: stats.avgReturn, icon: TrendingUp, format: 'percent', positive: stats.avgReturn > 0 },
            { label: 'Max Drawdown', value: stats.maxDrawdown, icon: TrendingDown, format: 'percent', positive: false },
            { label: 'Profit Factor', value: stats.profitFactor, icon: Zap, format: 'decimal', positive: stats.profitFactor > 1 },
            { label: 'Avg Hold Time', value: stats.avgHoldingPeriod, icon: Clock, format: 'string' },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="glass-card p-4 rounded-xl"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400 uppercase tracking-wider">{stat.label}</span>
                <stat.icon className="w-4 h-4 text-slate-500" />
              </div>
              <p className={cn(
                "text-xl font-bold",
                stat.format !== 'string' && stat.positive !== undefined && (stat.positive ? "text-emerald-400" : "text-red-400")
              )}>
                {stat.format === 'usd' ? formatUSD(stat.value as number) :
                 stat.format === 'percent' ? `${(stat.value as number).toFixed(1)}%` :
                 stat.format === 'decimal' ? (stat.value as number).toFixed(2) :
                 stat.value}
              </p>
            </motion.div>
          ))}
        </div>

        {/* Chart */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mb-8"
        >
          <ProChart symbol="ETH" data={[]} height={350} showIndicators={false} />
        </motion.div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-6">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Signal:</span>
            <div className="flex items-center gap-1 p-1 rounded-lg bg-surface-1 border border-white/5">
              {signalTypes.map((type) => (
                <button
                  key={type}
                  onClick={() => setSignalFilter(type)}
                  className={cn(
                    "px-2.5 py-1 rounded text-xs font-medium transition-colors capitalize",
                    signalFilter === type 
                      ? "bg-brand-sky/20 text-brand-sky" 
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  {type === 'all' ? 'All' : type.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Asset:</span>
            <div className="flex items-center gap-1 p-1 rounded-lg bg-surface-1 border border-white/5">
              {assets.map((asset) => (
                <button
                  key={asset}
                  onClick={() => setAssetFilter(asset)}
                  className={cn(
                    "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                    assetFilter === asset 
                      ? "bg-brand-sky/20 text-brand-sky" 
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  {asset === 'all' ? 'All' : asset}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Results Table */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card rounded-xl overflow-hidden"
        >
          <div className="p-4 border-b border-white/5 flex items-center justify-between">
            <h3 className="font-medium">Trade History</h3>
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-2 text-sm text-slate-400 hover:text-white transition-colors">
              <Download className="w-4 h-4" />
              Export CSV
            </button>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5 bg-surface-2/30">
                  <th className="text-left text-slate-400 font-medium px-4 py-3">Signal</th>
                  <th className="text-left text-slate-400 font-medium px-4 py-3">Asset</th>
                  <th className="text-left text-slate-400 font-medium px-4 py-3">Entry</th>
                  <th className="text-center text-slate-400 font-medium px-4 py-3">Confidence</th>
                  <th className="text-center text-slate-400 font-medium px-4 py-3">Predicted</th>
                  <th className="text-center text-slate-400 font-medium px-4 py-3">Actual</th>
                  <th className="text-right text-slate-400 font-medium px-4 py-3">P&L</th>
                  <th className="text-center text-slate-400 font-medium px-4 py-3">Result</th>
                </tr>
              </thead>
              <tbody>
                {filteredResults.slice(0, 20).map((result, i) => (
                  <motion.tr
                    key={result.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.02 }}
                    className="border-b border-white/5 hover:bg-white/[0.02]"
                  >
                    <td className="px-4 py-3">
                      <span className={cn(
                        "px-2 py-1 rounded text-xs font-medium uppercase",
                        result.signalType === 'zk' ? "bg-purple-500/20 text-purple-400" :
                        result.signalType === 'whale' ? "bg-blue-500/20 text-blue-400" :
                        result.signalType === 'dark_pool' ? "bg-slate-500/20 text-slate-300" :
                        "bg-cyan-500/20 text-cyan-400"
                      )}>
                        {result.signalType.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium">{result.asset}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {new Date(result.entryTime).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={cn(
                        "px-2 py-0.5 rounded-full text-xs",
                        result.confidence >= 80 ? "bg-emerald-500/20 text-emerald-400" :
                        result.confidence >= 60 ? "bg-amber-500/20 text-amber-400" :
                        "bg-slate-500/20 text-slate-400"
                      )}>
                        {result.confidence}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center font-mono text-slate-300">
                      +{result.predictedImpact.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-center font-mono">
                      <span className={result.actualImpact >= 0 ? "text-emerald-400" : "text-red-400"}>
                        {result.actualImpact >= 0 ? '+' : ''}{result.actualImpact.toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      <span className={result.pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                        {result.pnl >= 0 ? '+' : ''}{formatUSD(result.pnl)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {result.hit ? (
                        <span className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 text-xs font-medium">
                          HIT
                        </span>
                      ) : (
                        <span className="px-2 py-1 rounded bg-red-500/20 text-red-400 text-xs font-medium">
                          MISS
                        </span>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {filteredResults.length > 20 && (
            <div className="p-4 border-t border-white/5 text-center">
              <button className="text-sm text-brand-sky hover:text-brand-sky/80 transition-colors">
                Load more results ({filteredResults.length - 20} remaining)
              </button>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}

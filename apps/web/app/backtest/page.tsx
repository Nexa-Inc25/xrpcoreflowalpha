'use client';

import { motion } from 'framer-motion';
import { History, TrendingUp, Target, Clock } from 'lucide-react';

export default function BacktestPage() {

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
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400 border border-amber-500/30">
                Coming Soon
              </span>
            </div>
            <p className="text-slate-400">Analyze historical signal performance and validate strategies</p>
          </div>
        </motion.div>
        
        {/* Coming Soon Hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card rounded-2xl p-12 text-center mb-8"
        >
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 flex items-center justify-center">
            <History className="w-10 h-10 text-purple-400" />
          </div>
          <h2 className="text-2xl font-bold mb-3">Backtesting Engine Coming Soon</h2>
          <p className="text-slate-400 max-w-lg mx-auto mb-8">
            We're building a comprehensive backtesting system that will let you validate signal predictions against historical price data. 
            This requires storing signals with timestamps and tracking outcomes over time.
          </p>
          
          <div className="grid sm:grid-cols-3 gap-4 max-w-2xl mx-auto">
            <div className="p-4 rounded-xl bg-surface-1 border border-white/5">
              <Clock className="w-6 h-6 text-brand-sky mx-auto mb-2" />
              <h3 className="font-medium mb-1">Historical Data</h3>
              <p className="text-xs text-slate-500">TimescaleDB storage for signals & prices</p>
            </div>
            <div className="p-4 rounded-xl bg-surface-1 border border-white/5">
              <Target className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
              <h3 className="font-medium mb-1">Outcome Tracking</h3>
              <p className="text-xs text-slate-500">Compare predictions vs actual moves</p>
            </div>
            <div className="p-4 rounded-xl bg-surface-1 border border-white/5">
              <TrendingUp className="w-6 h-6 text-purple-400 mx-auto mb-2" />
              <h3 className="font-medium mb-1">Performance Metrics</h3>
              <p className="text-xs text-slate-500">Win rate, Sharpe ratio, drawdowns</p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

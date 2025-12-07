'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import {
  Wallet,
  Search,
  ExternalLink,
  Copy,
  Check,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Loader2,
  ArrowRight,
  Zap,
  Eye,
} from 'lucide-react';
import { cn, formatUSD } from '../../lib/utils';
import { fetchWhaleTransfers } from '../../lib/api';

interface WhaleTransfer {
  id: string;
  hash: string;
  blockchain: string;
  symbol: string;
  amount: number;
  amount_usd: number;
  timestamp: number;
  from: {
    address: string;
    owner: string;
    owner_type: string;
  };
  to: {
    address: string;
    owner: string;
    owner_type: string;
  };
  confidence: number;
  direction: string;
}

export default function WalletsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [chainFilter, setChainFilter] = useState<string>('all');
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null);

  // Fetch real whale transfers from API
  const { data: whaleData, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['whale-transfers', chainFilter],
    queryFn: () => fetchWhaleTransfers({ 
      chain: chainFilter !== 'all' ? chainFilter : undefined,
      limit: 50 
    }),
    refetchInterval: 60000,
  });

  const transfers: WhaleTransfer[] = whaleData?.transfers || [];
  
  const filteredTransfers = transfers.filter(t => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return t.from?.owner?.toLowerCase().includes(q) || 
           t.to?.owner?.toLowerCase().includes(q) ||
           t.from?.address?.toLowerCase().includes(q) ||
           t.to?.address?.toLowerCase().includes(q) ||
           t.symbol?.toLowerCase().includes(q);
  });

  const copyAddress = async (address: string) => {
    await navigator.clipboard.writeText(address);
    setCopiedAddress(address);
    setTimeout(() => setCopiedAddress(null), 2000);
  };

  const getChainColor = (chain: string) => {
    switch (chain) {
      case 'ethereum': return 'bg-blue-500/20 text-blue-400';
      case 'ripple': return 'bg-cyan-500/20 text-cyan-400';
      case 'bitcoin': return 'bg-orange-500/20 text-orange-400';
      case 'solana': return 'bg-purple-500/20 text-purple-400';
      default: return 'bg-slate-500/20 text-slate-400';
    }
  };

  const getDirectionColor = (dir: string) => {
    if (dir === 'BULLISH') return 'text-emerald-400 bg-emerald-500/10';
    if (dir === 'BEARISH') return 'text-red-400 bg-red-500/10';
    return 'text-slate-400 bg-slate-500/10';
  };

  const getExplorerUrl = (chain: string, hash: string) => {
    switch (chain) {
      case 'ethereum': return `https://etherscan.io/tx/${hash}`;
      case 'ripple': return `https://xrpscan.com/tx/${hash}`;
      case 'bitcoin': return `https://blockchain.com/btc/tx/${hash}`;
      case 'solana': return `https://solscan.io/tx/${hash}`;
      default: return '#';
    }
  };

  const chains = ['all', 'ethereum', 'ripple', 'bitcoin', 'solana'];

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
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-sky/20 to-blue-500/20 border border-brand-sky/30 flex items-center justify-center">
                <Wallet className="w-5 h-5 text-brand-sky" />
              </div>
              <h1 className="text-2xl font-semibold">Whale Transfers</h1>
            </div>
            <p className="text-slate-400">Real-time large transaction tracking via Whale Alert API</p>
          </div>
          <button 
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-sky text-white font-medium hover:bg-brand-sky/90 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn("w-4 h-4", isFetching && "animate-spin")} />
            Refresh
          </button>
        </motion.div>

        {/* Search & Chain Filter */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search by owner, address, or symbol..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-surface-1 border border-white/5 text-sm placeholder:text-slate-500 focus:outline-none focus:border-brand-sky/50"
            />
          </div>
          <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-1 border border-white/5">
            {chains.map((chain) => (
              <button
                key={chain}
                onClick={() => setChainFilter(chain)}
                className={cn(
                  "px-3 py-2 rounded-lg text-xs font-medium transition-colors capitalize",
                  chainFilter === chain ? "bg-brand-sky/20 text-brand-sky" : "text-slate-400 hover:text-white"
                )}
              >
                {chain === 'all' ? 'All Chains' : chain}
              </button>
            ))}
          </div>
        </div>

        {/* Transfer count */}
        <div className="mb-4 text-sm text-slate-400">
          {isLoading ? 'Loading...' : `${filteredTransfers.length} whale transfers found`}
        </div>

        {/* Transfers List */}
        <div className="space-y-3">
          {isLoading ? (
            <div className="text-center py-16">
              <Loader2 className="w-8 h-8 text-brand-sky mx-auto mb-4 animate-spin" />
              <p className="text-slate-400">Fetching whale transfers...</p>
            </div>
          ) : filteredTransfers.length === 0 ? (
            <div className="text-center py-16">
              <Wallet className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-300 mb-2">No whale transfers</h3>
              <p className="text-sm text-slate-500">
                {whaleData?.transfers?.length === 0 
                  ? 'No large transfers detected in the last 10 minutes'
                  : 'No transfers match your search criteria'}
              </p>
            </div>
          ) : (
            filteredTransfers.map((transfer, index) => (
              <motion.div
                key={transfer.id || transfer.hash || index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.03 }}
                className="glass-card p-4 rounded-xl"
              >
                <div className="flex items-start gap-4">
                  {/* Amount Badge */}
                  <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30 flex flex-col items-center justify-center flex-shrink-0">
                    <span className="text-lg font-bold text-amber-400">
                      {transfer.amount_usd >= 1_000_000_000 
                        ? `$${(transfer.amount_usd / 1_000_000_000).toFixed(1)}B`
                        : transfer.amount_usd >= 1_000_000
                        ? `$${(transfer.amount_usd / 1_000_000).toFixed(1)}M`
                        : formatUSD(transfer.amount_usd)}
                    </span>
                    <span className="text-[10px] text-amber-500">{transfer.symbol}</span>
                  </div>

                  {/* Transfer Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className={cn(
                        "px-2 py-0.5 rounded text-[10px] uppercase font-medium",
                        getChainColor(transfer.blockchain)
                      )}>
                        {transfer.blockchain}
                      </span>
                      <span className={cn(
                        "px-2 py-0.5 rounded text-[10px] uppercase font-medium",
                        getDirectionColor(transfer.direction)
                      )}>
                        {transfer.direction}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-400">
                        {transfer.confidence}% conf
                      </span>
                    </div>

                    {/* From -> To */}
                    <div className="flex items-center gap-2 text-sm mb-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-slate-400 text-[10px] uppercase tracking-wider">From</p>
                        <p className="font-medium truncate">{transfer.from?.owner || 'Unknown'}</p>
                        <div className="flex items-center gap-1">
                          <code className="font-mono text-[10px] text-slate-500">
                            {transfer.from?.address?.slice(0, 8)}...
                          </code>
                          <button
                            onClick={() => copyAddress(transfer.from?.address || '')}
                            className="p-0.5 hover:bg-white/5 rounded"
                          >
                            {copiedAddress === transfer.from?.address ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3 text-slate-500" />
                            )}
                          </button>
                        </div>
                      </div>
                      
                      <ArrowRight className="w-5 h-5 text-slate-600 flex-shrink-0" />
                      
                      <div className="flex-1 min-w-0">
                        <p className="text-slate-400 text-[10px] uppercase tracking-wider">To</p>
                        <p className="font-medium truncate">{transfer.to?.owner || 'Unknown'}</p>
                        <div className="flex items-center gap-1">
                          <code className="font-mono text-[10px] text-slate-500">
                            {transfer.to?.address?.slice(0, 8)}...
                          </code>
                          <button
                            onClick={() => copyAddress(transfer.to?.address || '')}
                            className="p-0.5 hover:bg-white/5 rounded"
                          >
                            {copiedAddress === transfer.to?.address ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3 text-slate-500" />
                            )}
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Time & Links */}
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>{new Date(transfer.timestamp * 1000).toLocaleString()}</span>
                      <Link
                        href={`/flow/${encodeURIComponent(transfer.hash)}`}
                        className="flex items-center gap-1 text-brand-sky hover:underline"
                      >
                        View Details <Eye className="w-3 h-3" />
                      </Link>
                      <a
                        href={getExplorerUrl(transfer.blockchain, transfer.hash)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-slate-400 hover:text-slate-200"
                      >
                        Explorer <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>

                  {/* Confidence Indicator */}
                  <div className="text-right flex-shrink-0">
                    <div className={cn(
                      "w-12 h-12 rounded-full flex items-center justify-center",
                      transfer.confidence >= 80 ? "bg-emerald-500/20" :
                      transfer.confidence >= 60 ? "bg-amber-500/20" : "bg-slate-500/20"
                    )}>
                      <Zap className={cn(
                        "w-5 h-5",
                        transfer.confidence >= 80 ? "text-emerald-400" :
                        transfer.confidence >= 60 ? "text-amber-400" : "text-slate-400"
                      )} />
                    </div>
                  </div>
                </div>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

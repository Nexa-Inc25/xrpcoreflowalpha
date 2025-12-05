'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Wallet,
  Plus,
  Search,
  ExternalLink,
  Copy,
  Check,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  Link2,
  GitBranch,
  Eye,
  MoreVertical,
} from 'lucide-react';
import { cn, formatUSD, timeAgo } from '../../lib/utils';

interface TrackedWallet {
  id: string;
  address: string;
  label: string;
  network: 'ethereum' | 'xrpl' | 'solana';
  cluster?: string;
  balance: number;
  balanceChange24h: number;
  txCount24h: number;
  lastActivity: string;
  risk: 'low' | 'medium' | 'high';
  tags: string[];
}

interface WalletCluster {
  id: string;
  name: string;
  walletCount: number;
  totalBalance: number;
  risk: 'low' | 'medium' | 'high';
}

const mockWallets: TrackedWallet[] = [
  {
    id: '1',
    address: '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
    label: 'Uniswap V2 Router',
    network: 'ethereum',
    cluster: 'DEX Routers',
    balance: 45000000,
    balanceChange24h: 12.5,
    txCount24h: 1247,
    lastActivity: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
    risk: 'low',
    tags: ['DEX', 'High Volume', 'Verified'],
  },
  {
    id: '2',
    address: '0x28C6c06298d514Db089934071355E5743bf21d60',
    label: 'Binance Hot Wallet',
    network: 'ethereum',
    cluster: 'Exchange',
    balance: 2100000000,
    balanceChange24h: -3.2,
    txCount24h: 856,
    lastActivity: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    risk: 'medium',
    tags: ['CEX', 'Hot Wallet', 'Large Holdings'],
  },
  {
    id: '3',
    address: 'rN7n3473SaZBCG4dFL83w7LaaK9cejpqTN',
    label: 'XRPL Whale #1',
    network: 'xrpl',
    balance: 125000000,
    balanceChange24h: 8.7,
    txCount24h: 34,
    lastActivity: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    risk: 'high',
    tags: ['Whale', 'Active Trader'],
  },
  {
    id: '4',
    address: '0x3DdfA8eC3052539b6C9549F12cEA2C295cfF5296',
    label: 'Unknown Whale',
    network: 'ethereum',
    cluster: 'Suspected Fund',
    balance: 78000000,
    balanceChange24h: 45.2,
    txCount24h: 12,
    lastActivity: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
    risk: 'high',
    tags: ['Whale', 'New Activity', 'ZK User'],
  },
];

const mockClusters: WalletCluster[] = [
  { id: '1', name: 'DEX Routers', walletCount: 8, totalBalance: 120000000, risk: 'low' },
  { id: '2', name: 'Exchange', walletCount: 24, totalBalance: 5600000000, risk: 'medium' },
  { id: '3', name: 'Suspected Fund', walletCount: 5, totalBalance: 340000000, risk: 'high' },
];

export default function WalletsPage() {
  const [wallets] = useState<TrackedWallet[]>(mockWallets);
  const [clusters] = useState<WalletCluster[]>(mockClusters);
  const [searchQuery, setSearchQuery] = useState('');
  const [view, setView] = useState<'list' | 'clusters'>('list');
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);

  const filteredWallets = wallets.filter(w => {
    const matchesSearch = !searchQuery || 
      w.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.address.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCluster = !selectedCluster || w.cluster === selectedCluster;
    return matchesSearch && matchesCluster;
  });

  const copyAddress = async (address: string) => {
    await navigator.clipboard.writeText(address);
    setCopiedAddress(address);
    setTimeout(() => setCopiedAddress(null), 2000);
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'high': return 'text-red-400 bg-red-500/10 border-red-500/30';
      case 'medium': return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
      default: return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
    }
  };

  const getNetworkColor = (network: string) => {
    switch (network) {
      case 'ethereum': return 'bg-blue-500/20 text-blue-400';
      case 'xrpl': return 'bg-cyan-500/20 text-cyan-400';
      case 'solana': return 'bg-purple-500/20 text-purple-400';
      default: return 'bg-slate-500/20 text-slate-400';
    }
  };

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
              <h1 className="text-2xl font-semibold">Wallet Tracking</h1>
            </div>
            <p className="text-slate-400">Monitor wallet activity, clusters, and flow patterns</p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-sky text-white font-medium hover:bg-brand-sky/90 transition-colors">
            <Plus className="w-4 h-4" />
            Track Wallet
          </button>
        </motion.div>

        {/* Search & Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search by label or address..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-surface-1 border border-white/5 text-sm placeholder:text-slate-500 focus:outline-none focus:border-brand-sky/50"
            />
          </div>
          <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-1 border border-white/5">
            <button
              onClick={() => setView('list')}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                view === 'list' ? "bg-brand-sky/20 text-brand-sky" : "text-slate-400 hover:text-white"
              )}
            >
              List View
            </button>
            <button
              onClick={() => setView('clusters')}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                view === 'clusters' ? "bg-brand-sky/20 text-brand-sky" : "text-slate-400 hover:text-white"
              )}
            >
              Clusters
            </button>
          </div>
        </div>

        {/* Cluster Pills */}
        {view === 'list' && (
          <div className="flex flex-wrap gap-2 mb-6">
            <button
              onClick={() => setSelectedCluster(null)}
              className={cn(
                "px-3 py-1.5 rounded-full text-sm font-medium transition-colors",
                !selectedCluster 
                  ? "bg-brand-sky/20 text-brand-sky border border-brand-sky/30"
                  : "bg-surface-1 text-slate-400 hover:text-white"
              )}
            >
              All Wallets
            </button>
            {clusters.map((cluster) => (
              <button
                key={cluster.id}
                onClick={() => setSelectedCluster(cluster.name)}
                className={cn(
                  "px-3 py-1.5 rounded-full text-sm font-medium transition-colors flex items-center gap-1.5",
                  selectedCluster === cluster.name
                    ? "bg-brand-sky/20 text-brand-sky border border-brand-sky/30"
                    : "bg-surface-1 text-slate-400 hover:text-white"
                )}
              >
                <GitBranch className="w-3 h-3" />
                {cluster.name}
                <span className="text-xs opacity-60">({cluster.walletCount})</span>
              </button>
            ))}
          </div>
        )}

        {/* Content */}
        <AnimatePresence mode="wait">
          {view === 'list' ? (
            <motion.div
              key="list"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              {filteredWallets.map((wallet, index) => (
                <motion.div
                  key={wallet.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="glass-card p-4 rounded-xl"
                >
                  <div className="flex items-start gap-4">
                    {/* Icon */}
                    <div className="w-10 h-10 rounded-lg bg-surface-2 flex items-center justify-center flex-shrink-0">
                      <Wallet className="w-5 h-5 text-slate-400" />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <h3 className="font-medium">{wallet.label}</h3>
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] uppercase font-medium",
                          getNetworkColor(wallet.network)
                        )}>
                          {wallet.network}
                        </span>
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] uppercase font-medium border",
                          getRiskColor(wallet.risk)
                        )}>
                          {wallet.risk} risk
                        </span>
                        {wallet.cluster && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-500/20 text-slate-400 flex items-center gap-1">
                            <GitBranch className="w-2.5 h-2.5" />
                            {wallet.cluster}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2 text-sm text-slate-400">
                        <code className="font-mono text-xs bg-surface-2 px-1.5 py-0.5 rounded">
                          {wallet.address.slice(0, 10)}...{wallet.address.slice(-8)}
                        </code>
                        <button
                          onClick={() => copyAddress(wallet.address)}
                          className="p-1 hover:bg-white/5 rounded transition-colors"
                        >
                          {copiedAddress === wallet.address ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                        <a
                          href={wallet.network === 'ethereum' 
                            ? `https://etherscan.io/address/${wallet.address}`
                            : wallet.network === 'xrpl'
                            ? `https://xrpscan.com/account/${wallet.address}`
                            : `https://solscan.io/account/${wallet.address}`
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 hover:bg-white/5 rounded transition-colors"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>

                      {/* Tags */}
                      <div className="flex flex-wrap gap-1 mt-2">
                        {wallet.tags.map((tag) => (
                          <span key={tag} className="px-2 py-0.5 rounded text-[10px] bg-surface-2 text-slate-400">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-6 text-sm">
                      <div className="text-right">
                        <p className="text-slate-400 text-xs mb-0.5">Balance</p>
                        <p className="font-medium">{formatUSD(wallet.balance)}</p>
                        <p className={cn(
                          "text-xs flex items-center justify-end gap-0.5",
                          wallet.balanceChange24h >= 0 ? "text-emerald-400" : "text-red-400"
                        )}>
                          {wallet.balanceChange24h >= 0 ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : (
                            <TrendingDown className="w-3 h-3" />
                          )}
                          {Math.abs(wallet.balanceChange24h)}%
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-slate-400 text-xs mb-0.5">24h Txns</p>
                        <p className="font-medium">{wallet.txCount24h.toLocaleString()}</p>
                        <p className="text-xs text-slate-500">{timeAgo(wallet.lastActivity)}</p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <motion.div
              key="clusters"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="grid md:grid-cols-2 lg:grid-cols-3 gap-4"
            >
              {clusters.map((cluster, index) => (
                <motion.div
                  key={cluster.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="glass-card p-5 rounded-xl cursor-pointer hover:border-brand-sky/30 transition-colors"
                  onClick={() => {
                    setSelectedCluster(cluster.name);
                    setView('list');
                  }}
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-lg bg-brand-sky/10 flex items-center justify-center">
                      <GitBranch className="w-5 h-5 text-brand-sky" />
                    </div>
                    <div>
                      <h3 className="font-medium">{cluster.name}</h3>
                      <p className="text-xs text-slate-400">{cluster.walletCount} wallets</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-surface-2/50">
                      <p className="text-xs text-slate-400 mb-1">Total Balance</p>
                      <p className="font-semibold">{formatUSD(cluster.totalBalance)}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-surface-2/50">
                      <p className="text-xs text-slate-400 mb-1">Risk Level</p>
                      <p className={cn(
                        "font-semibold capitalize",
                        cluster.risk === 'high' ? "text-red-400" :
                        cluster.risk === 'medium' ? "text-amber-400" : "text-emerald-400"
                      )}>
                        {cluster.risk}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-xs text-slate-500">Click to view wallets</span>
                    <Eye className="w-4 h-4 text-slate-500" />
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

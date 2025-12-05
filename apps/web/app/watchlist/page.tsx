'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Star,
  Plus,
  Trash2,
  Bell,
  BellOff,
  ExternalLink,
  Wallet,
  Coins,
  TrendingUp,
  TrendingDown,
  Copy,
  Check,
  Search,
  Filter,
  MoreVertical,
  AlertTriangle,
} from 'lucide-react';
import { cn, formatUSD, formatNumber, timeAgo } from '../../lib/utils';

interface WatchItem {
  id: string;
  type: 'wallet' | 'token' | 'contract';
  address: string;
  label: string;
  network: string;
  alertsEnabled: boolean;
  lastActivity?: string;
  balance?: number;
  priceChange24h?: number;
  addedAt: string;
}

// No mock data - empty initial state
const mockWatchlist: WatchItem[] = [];

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchItem[]>(mockWatchlist);
  const [filter, setFilter] = useState<'all' | 'wallet' | 'token' | 'contract'>('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const filteredItems = items.filter(item => {
    if (filter !== 'all' && item.type !== filter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return item.label.toLowerCase().includes(q) || item.address.toLowerCase().includes(q);
    }
    return true;
  });

  const toggleAlert = (id: string) => {
    setItems(items.map(item => 
      item.id === id ? { ...item, alertsEnabled: !item.alertsEnabled } : item
    ));
  };

  const removeItem = (id: string) => {
    setItems(items.filter(item => item.id !== id));
  };

  const copyAddress = async (id: string, address: string) => {
    await navigator.clipboard.writeText(address);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'wallet': return <Wallet className="w-4 h-4" />;
      case 'token': return <Coins className="w-4 h-4" />;
      default: return <AlertTriangle className="w-4 h-4" />;
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'wallet': return 'text-brand-sky bg-brand-sky/10 border-brand-sky/30';
      case 'token': return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
      default: return 'text-purple-400 bg-purple-500/10 border-purple-500/30';
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="w-full max-w-[1400px] mx-auto px-4 lg:px-6 py-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start justify-between mb-8"
        >
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30 flex items-center justify-center">
                <Star className="w-5 h-5 text-amber-400" />
              </div>
              <h1 className="text-2xl font-semibold">Watchlist</h1>
            </div>
            <p className="text-slate-400">Track wallets, tokens, and smart contracts</p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-sky text-white font-medium hover:bg-brand-sky/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Item
          </button>
        </motion.div>

        {/* Filters */}
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
            {(['all', 'wallet', 'token', 'contract'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize",
                  filter === f 
                    ? "bg-brand-sky/20 text-brand-sky" 
                    : "text-slate-400 hover:text-white"
                )}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Watchlist Grid */}
        <div className="grid gap-4">
          <AnimatePresence mode="popLayout">
            {filteredItems.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center py-16"
              >
                <Star className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-slate-300 mb-2">No items found</h3>
                <p className="text-sm text-slate-500">
                  {searchQuery ? 'Try a different search term' : 'Add wallets, tokens, or contracts to track'}
                </p>
              </motion.div>
            ) : (
              filteredItems.map((item, index) => (
                <motion.div
                  key={item.id}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ delay: index * 0.05 }}
                  className="glass-card p-4 rounded-xl group"
                >
                  <div className="flex items-start gap-4">
                    {/* Type Icon */}
                    <div className={cn(
                      "w-10 h-10 rounded-lg border flex items-center justify-center flex-shrink-0",
                      getTypeColor(item.type)
                    )}>
                      {getTypeIcon(item.type)}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium">{item.label}</h3>
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] uppercase font-medium",
                          item.network === 'ethereum' ? "bg-blue-500/20 text-blue-400" :
                          item.network === 'xrpl' ? "bg-cyan-500/20 text-cyan-400" :
                          "bg-slate-500/20 text-slate-400"
                        )}>
                          {item.network}
                        </span>
                        {item.alertsEnabled && (
                          <Bell className="w-3.5 h-3.5 text-amber-400" />
                        )}
                      </div>
                      
                      <div className="flex items-center gap-2 text-sm text-slate-400">
                        <code className="font-mono text-xs bg-surface-2 px-1.5 py-0.5 rounded">
                          {item.address.slice(0, 8)}...{item.address.slice(-6)}
                        </code>
                        <button
                          onClick={() => copyAddress(item.id, item.address)}
                          className="p-1 hover:bg-white/5 rounded transition-colors"
                        >
                          {copiedId === item.id ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                        <a
                          href={item.network === 'ethereum' 
                            ? `https://etherscan.io/address/${item.address}`
                            : `https://xrpscan.com/account/${item.address}`
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 hover:bg-white/5 rounded transition-colors"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>

                      {/* Stats Row */}
                      <div className="flex items-center gap-4 mt-3 text-xs">
                        {item.balance && (
                          <span className="text-slate-400">
                            Balance: <span className="text-white">{formatUSD(item.balance)}</span>
                          </span>
                        )}
                        {item.priceChange24h !== undefined && (
                          <span className={cn(
                            "flex items-center gap-1",
                            item.priceChange24h >= 0 ? "text-emerald-400" : "text-red-400"
                          )}>
                            {item.priceChange24h >= 0 ? (
                              <TrendingUp className="w-3 h-3" />
                            ) : (
                              <TrendingDown className="w-3 h-3" />
                            )}
                            {Math.abs(item.priceChange24h).toFixed(2)}% 24h
                          </span>
                        )}
                        {item.lastActivity && (
                          <span className="text-slate-500">
                            Last activity: {timeAgo(item.lastActivity)}
                          </span>
                        )}
                        <span className="text-slate-600 ml-auto">
                          Added {timeAgo(item.addedAt)}
                        </span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => toggleAlert(item.id)}
                        className={cn(
                          "p-2 rounded-lg transition-colors",
                          item.alertsEnabled 
                            ? "bg-amber-500/20 text-amber-400 hover:bg-amber-500/30"
                            : "bg-white/5 text-slate-400 hover:text-white"
                        )}
                        title={item.alertsEnabled ? 'Disable alerts' : 'Enable alerts'}
                      >
                        {item.alertsEnabled ? (
                          <Bell className="w-4 h-4" />
                        ) : (
                          <BellOff className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => removeItem(item.id)}
                        className="p-2 rounded-lg bg-white/5 text-slate-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
                        title="Remove from watchlist"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </motion.div>
              ))
            )}
          </AnimatePresence>
        </div>

        {/* Add Modal */}
        <AnimatePresence>
          {showAddModal && (
            <AddWatchItemModal
              onClose={() => setShowAddModal(false)}
              onAdd={(item) => {
                setItems([item, ...items]);
                setShowAddModal(false);
              }}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function AddWatchItemModal({ 
  onClose, 
  onAdd 
}: { 
  onClose: () => void; 
  onAdd: (item: WatchItem) => void;
}) {
  const [type, setType] = useState<'wallet' | 'token' | 'contract'>('wallet');
  const [address, setAddress] = useState('');
  const [label, setLabel] = useState('');
  const [network, setNetwork] = useState<'ethereum' | 'xrpl'>('ethereum');
  const [alertsEnabled, setAlertsEnabled] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!address || !label) return;

    onAdd({
      id: Math.random().toString(36).slice(2),
      type,
      address,
      label,
      network,
      alertsEnabled,
      addedAt: new Date().toISOString(),
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="w-full max-w-md rounded-2xl border border-white/10 bg-surface-1/95 backdrop-blur-xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold mb-4">Add to Watchlist</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Type Selection */}
          <div>
            <label className="text-sm text-slate-400 mb-2 block">Type</label>
            <div className="grid grid-cols-3 gap-2">
              {(['wallet', 'token', 'contract'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setType(t)}
                  className={cn(
                    "px-3 py-2 rounded-lg text-sm font-medium capitalize transition-colors",
                    type === t 
                      ? "bg-brand-sky/20 text-brand-sky border border-brand-sky/30"
                      : "bg-surface-2 text-slate-400 hover:text-white"
                  )}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Network */}
          <div>
            <label className="text-sm text-slate-400 mb-2 block">Network</label>
            <div className="grid grid-cols-2 gap-2">
              {(['ethereum', 'xrpl'] as const).map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setNetwork(n)}
                  className={cn(
                    "px-3 py-2 rounded-lg text-sm font-medium uppercase transition-colors",
                    network === n 
                      ? "bg-brand-sky/20 text-brand-sky border border-brand-sky/30"
                      : "bg-surface-2 text-slate-400 hover:text-white"
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {/* Address */}
          <div>
            <label className="text-sm text-slate-400 mb-2 block">Address</label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="0x... or r..."
              className="w-full px-4 py-2.5 rounded-lg bg-surface-2 border border-white/5 text-sm placeholder:text-slate-500 focus:outline-none focus:border-brand-sky/50 font-mono"
            />
          </div>

          {/* Label */}
          <div>
            <label className="text-sm text-slate-400 mb-2 block">Label</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g., Whale Wallet #1"
              className="w-full px-4 py-2.5 rounded-lg bg-surface-2 border border-white/5 text-sm placeholder:text-slate-500 focus:outline-none focus:border-brand-sky/50"
            />
          </div>

          {/* Alerts Toggle */}
          <label className="flex items-center gap-3 cursor-pointer">
            <div
              className={cn(
                "w-10 h-6 rounded-full p-1 transition-colors",
                alertsEnabled ? "bg-brand-sky" : "bg-surface-2"
              )}
              onClick={() => setAlertsEnabled(!alertsEnabled)}
            >
              <motion.div
                className="w-4 h-4 rounded-full bg-white"
                animate={{ x: alertsEnabled ? 16 : 0 }}
                transition={{ type: 'spring', damping: 20, stiffness: 300 }}
              />
            </div>
            <span className="text-sm">Enable alerts for this item</span>
          </label>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-lg bg-surface-2 text-slate-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!address || !label}
              className="flex-1 px-4 py-2.5 rounded-lg bg-brand-sky text-white font-medium hover:bg-brand-sky/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Add to Watchlist
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}

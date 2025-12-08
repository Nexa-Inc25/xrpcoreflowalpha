'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation } from '@tanstack/react-query';
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
  AlertTriangle,
  Shield,
  Clock,
  FileWarning,
} from 'lucide-react';
import { cn, formatUSD } from '../../lib/utils';
import { fetchWhaleTransfers } from '../../lib/api';

// API base for wallet endpoints
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';

// Institutional wallet types
interface InstitutionalWallet {
  address: string;
  label: string;
  entity: string;
  chain: string;
  type: string;
  verified: boolean;
  source: string;
  notes: string;
}

interface WalletBalance {
  address: string;
  label?: string;
  type?: string;
  balance_eth?: number;
  error?: string;
}

// Wallet analysis types
interface WalletFlag {
  tx_hash: string;
  flag: string;
  timestamp: string;
  value?: number;
  value_eth?: number;
  note?: string;
  token_symbol?: string;
}

interface WalletAnalysis {
  address: string;
  analyzed_at: string;
  summary: {
    total_transactions: number;
    total_token_transfers: number;
    total_eth_received: number;
    total_eth_sent: number;
    unique_tokens: string[];
  };
  flags: {
    wrapped_securities: WalletFlag[];
    settlement_timing: WalletFlag[];
    total_flags: number;
  };
  etherscan_link: string;
}

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
  const [analyzeAddress, setAnalyzeAddress] = useState('');
  const [activeTab, setActiveTab] = useState<'whales' | 'analyze' | 'institutional'>('whales');
  const [selectedEntity, setSelectedEntity] = useState<string>('all');

  // Fetch real whale transfers from API
  const { data: whaleData, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['whale-transfers', chainFilter],
    queryFn: () => fetchWhaleTransfers({ 
      chain: chainFilter !== 'all' ? chainFilter : undefined,
      limit: 50 
    }),
    refetchInterval: 60000,
  });

  // Wallet analysis mutation
  const analysisMutation = useMutation({
    mutationFn: async (address: string): Promise<WalletAnalysis> => {
      const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
      const res = await fetch(`${base}/wallet/analyze/${address}`);
      if (!res.ok) throw new Error('Analysis failed');
      return res.json();
    },
  });

  const handleAnalyze = () => {
    if (analyzeAddress.startsWith('0x') && analyzeAddress.length === 42) {
      analysisMutation.mutate(analyzeAddress);
    }
  };

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
          className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-6"
        >
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-sky/20 to-blue-500/20 border border-brand-sky/30 flex items-center justify-center">
                <Wallet className="w-5 h-5 text-brand-sky" />
              </div>
              <h1 className="text-2xl font-semibold">Wallet Intelligence</h1>
            </div>
            <p className="text-slate-400">Track whale transfers & analyze institutional wallets</p>
          </div>
        </motion.div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 mb-6">
          <button
            onClick={() => setActiveTab('whales')}
            className={cn(
              "px-4 py-2 rounded-xl font-medium text-sm transition-all",
              activeTab === 'whales' 
                ? "bg-brand-sky text-white" 
                : "bg-surface-1 text-slate-400 hover:text-white"
            )}
          >
            <Eye className="w-4 h-4 inline mr-2" />
            Whale Transfers
          </button>
          <button
            onClick={() => setActiveTab('analyze')}
            className={cn(
              "px-4 py-2 rounded-xl font-medium text-sm transition-all",
              activeTab === 'analyze' 
                ? "bg-brand-purple text-white" 
                : "bg-surface-1 text-slate-400 hover:text-white"
            )}
          >
            <Shield className="w-4 h-4 inline mr-2" />
            Analyze Wallet
          </button>
          <button
            onClick={() => setActiveTab('institutional')}
            className={cn(
              "px-4 py-2 rounded-xl font-medium text-sm transition-all",
              activeTab === 'institutional' 
                ? "bg-amber-500 text-white" 
                : "bg-surface-1 text-slate-400 hover:text-white"
            )}
          >
            <Wallet className="w-4 h-4 inline mr-2" />
            Institutional
          </button>
        </div>

        {/* Institutional Wallets Tab */}
        {activeTab === 'institutional' && <InstitutionalWalletsTab selectedEntity={selectedEntity} setSelectedEntity={setSelectedEntity} />}

        {/* Wallet Analysis Tab */}
        {activeTab === 'analyze' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            {/* Search Box */}
            <div className="glass-card rounded-2xl p-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Shield className="w-5 h-5 text-brand-purple" />
                Institutional Wallet Analysis
              </h2>
              <p className="text-slate-400 text-sm mb-4">
                Analyze any Ethereum wallet for wrapped securities, FTD patterns, and suspicious timing with equity markets.
              </p>
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="Enter ETH address (0x...)"
                  value={analyzeAddress}
                  onChange={(e) => setAnalyzeAddress(e.target.value)}
                  className="flex-1 px-4 py-3 rounded-xl bg-slate-800 border border-white/10 text-sm placeholder:text-slate-500 focus:outline-none focus:border-brand-purple/50 font-mono"
                />
                <button
                  onClick={handleAnalyze}
                  disabled={analysisMutation.isPending || !analyzeAddress.startsWith('0x')}
                  className="px-6 py-3 rounded-xl bg-brand-purple text-white font-medium hover:bg-brand-purple/90 transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {analysisMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Search className="w-4 h-4" />
                  )}
                  Analyze
                </button>
              </div>

              {/* Quick Links to Known Wallets */}
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="text-xs text-slate-500">Quick analyze:</span>
                {[
                  { label: 'Citadel', addr: '0x5a52e96bacdabb82fd05763e25335261b270efcb' },
                  { label: 'GSR', addr: '0x15abb66ba754f05cbc0165a64a11cded1543de48' },
                  { label: 'Cumberland', addr: '0xcd531ae9efcce479654c4926dec5f6209531ca7b' },
                ].map(w => (
                  <button
                    key={w.addr}
                    onClick={() => {
                      setAnalyzeAddress(w.addr);
                      analysisMutation.mutate(w.addr);
                    }}
                    className="px-2 py-1 rounded bg-slate-800 text-xs text-slate-300 hover:bg-slate-700 transition-colors"
                  >
                    {w.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Analysis Results */}
            {analysisMutation.data && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-card rounded-2xl p-6"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold">Analysis Results</h3>
                  <a
                    href={analysisMutation.data.etherscan_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-brand-sky hover:underline flex items-center gap-1"
                  >
                    View on Etherscan <ExternalLink className="w-3 h-3" />
                  </a>
                </div>

                {/* Summary Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <div className="p-3 rounded-xl bg-slate-800/50">
                    <div className="text-2xl font-bold">{analysisMutation.data.summary.total_transactions}</div>
                    <div className="text-xs text-slate-400">Transactions</div>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-800/50">
                    <div className="text-2xl font-bold">{analysisMutation.data.summary.total_token_transfers}</div>
                    <div className="text-xs text-slate-400">Token Transfers</div>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-800/50">
                    <div className="text-2xl font-bold">{analysisMutation.data.summary.total_eth_received.toFixed(2)}</div>
                    <div className="text-xs text-slate-400">ETH Received</div>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-800/50">
                    <div className="text-2xl font-bold text-amber-400">{analysisMutation.data.flags.total_flags}</div>
                    <div className="text-xs text-slate-400">Flags Detected</div>
                  </div>
                </div>

                {/* Flags */}
                {analysisMutation.data.flags.total_flags > 0 ? (
                  <div className="space-y-4">
                    <h4 className="text-sm font-medium text-amber-400 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" />
                      Suspicious Activity Detected
                    </h4>
                    {[...analysisMutation.data.flags.wrapped_securities, ...analysisMutation.data.flags.settlement_timing].map((flag, i) => (
                      <div key={i} className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs font-medium">
                            {flag.flag}
                          </span>
                          {flag.token_symbol && (
                            <span className="text-sm text-slate-300">{flag.token_symbol}</span>
                          )}
                        </div>
                        <p className="text-sm text-slate-400">{flag.note}</p>
                        <div className="mt-2 flex items-center gap-4 text-xs text-slate-500">
                          <span>{new Date(flag.timestamp).toLocaleString()}</span>
                          {flag.value && <span>${flag.value.toLocaleString()}</span>}
                          {flag.value_eth && <span>{flag.value_eth.toFixed(2)} ETH</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-center">
                    <Check className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
                    <p className="text-emerald-400 font-medium">No suspicious patterns detected</p>
                    <p className="text-xs text-slate-400 mt-1">
                      {analysisMutation.data.summary.total_transactions === 0 
                        ? "Note: No transactions found. You may need an Etherscan API key."
                        : "Wallet activity appears normal"}
                    </p>
                  </div>
                )}

                {/* Unique Tokens */}
                {analysisMutation.data.summary.unique_tokens.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-sm font-medium mb-2">Tokens Held</h4>
                    <div className="flex flex-wrap gap-2">
                      {analysisMutation.data.summary.unique_tokens.map(token => (
                        <span key={token} className="px-2 py-1 rounded bg-slate-800 text-xs">
                          {token}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {analysisMutation.error && (
              <div className="glass-card rounded-2xl p-6 border border-red-500/20">
                <div className="flex items-center gap-2 text-red-400">
                  <FileWarning className="w-5 h-5" />
                  <span>Analysis failed. Make sure ETHERSCAN_API_KEY is configured.</span>
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Whale Transfers Tab */}
        {activeTab === 'whales' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            {/* Refresh Button */}
            <div className="flex justify-end mb-4">
              <button 
                onClick={() => refetch()}
                disabled={isFetching}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-sky text-white font-medium hover:bg-brand-sky/90 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={cn("w-4 h-4", isFetching && "animate-spin")} />
                Refresh
              </button>
            </div>

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
          </motion.div>
        )}

        {/* Institutional Wallets Tab */}
        {activeTab === 'institutional' && (
          <InstitutionalWalletsTab 
            selectedEntity={selectedEntity} 
            setSelectedEntity={setSelectedEntity} 
          />
        )}
      </div>
    </div>
  );
}

// Institutional Wallets Tab Component
function InstitutionalWalletsTab({ 
  selectedEntity, 
  setSelectedEntity 
}: { 
  selectedEntity: string; 
  setSelectedEntity: (e: string) => void;
}) {
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null);

  // Fetch institutional wallets
  const { data: walletsData, isLoading } = useQuery({
    queryKey: ['institutional-wallets', selectedEntity],
    queryFn: async () => {
      const url = selectedEntity === 'all' 
        ? `${API_BASE}/wallets`
        : `${API_BASE}/wallets?entity=${selectedEntity}`;
      const res = await fetch(url);
      return res.json();
    },
  });

  // Fetch entity balances (only for Ethereum entities)
  const { data: balancesData, isLoading: balancesLoading, refetch: refetchBalances } = useQuery({
    queryKey: ['entity-balances', selectedEntity],
    queryFn: async () => {
      if (selectedEntity === 'all' || !['binance', 'gsr', 'cumberland', 'wintermute', 'coinbase', 'kraken', 'alameda'].includes(selectedEntity)) {
        return null;
      }
      const res = await fetch(`${API_BASE}/wallets/entity/${selectedEntity}/balances`);
      return res.json();
    },
    enabled: selectedEntity !== 'all',
  });

  const wallets: InstitutionalWallet[] = walletsData?.wallets || [];
  const entities = walletsData?.entities_summary || {};

  const copyAddress = async (address: string) => {
    await navigator.clipboard.writeText(address);
    setCopiedAddress(address);
    setTimeout(() => setCopiedAddress(null), 2000);
  };

  const getChainColor = (chain: string) => {
    switch (chain) {
      case 'ethereum': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'xrpl': return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30';
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  const getEntityColor = (entity: string) => {
    switch (entity) {
      case 'binance': return 'bg-amber-500/20 text-amber-400';
      case 'ripple': return 'bg-cyan-500/20 text-cyan-400';
      case 'gsr': return 'bg-purple-500/20 text-purple-400';
      case 'cumberland': return 'bg-emerald-500/20 text-emerald-400';
      case 'wintermute': return 'bg-blue-500/20 text-blue-400';
      case 'coinbase': return 'bg-indigo-500/20 text-indigo-400';
      case 'kraken': return 'bg-violet-500/20 text-violet-400';
      case 'alameda': return 'bg-red-500/20 text-red-400';
      default: return 'bg-slate-500/20 text-slate-400';
    }
  };

  const getExplorerUrl = (chain: string, address: string) => {
    if (chain === 'ethereum') return `https://etherscan.io/address/${address}`;
    if (chain === 'xrpl') return `https://xrpscan.com/account/${address}`;
    return '#';
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      {/* Entity Filter */}
      <div className="glass-card rounded-2xl p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-slate-400 mr-2">Filter by entity:</span>
          <button
            onClick={() => setSelectedEntity('all')}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              selectedEntity === 'all' ? "bg-brand-sky text-white" : "bg-slate-800 text-slate-400 hover:text-white"
            )}
          >
            All ({walletsData?.total || 0})
          </button>
          {Object.entries(entities).map(([entity, data]: [string, any]) => (
            <button
              key={entity}
              onClick={() => setSelectedEntity(entity)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize",
                selectedEntity === entity ? getEntityColor(entity) : "bg-slate-800 text-slate-400 hover:text-white"
              )}
            >
              {entity} ({data.count})
            </button>
          ))}
        </div>
      </div>

      {/* Entity Balance Summary (if available) */}
      {balancesData && !balancesData.error && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card rounded-2xl p-6 border border-amber-500/20"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold capitalize flex items-center gap-2">
              <Wallet className="w-5 h-5 text-amber-400" />
              {selectedEntity} Live Balances
            </h3>
            <button
              onClick={() => refetchBalances()}
              disabled={balancesLoading}
              className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
            >
              <RefreshCw className={cn("w-3 h-3", balancesLoading && "animate-spin")} />
              Refresh
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="p-3 rounded-xl bg-slate-800/50">
              <div className="text-2xl font-bold text-amber-400">{balancesData.total_eth?.toFixed(2) || '0'}</div>
              <div className="text-xs text-slate-400">Total ETH</div>
            </div>
            <div className="p-3 rounded-xl bg-slate-800/50">
              <div className="text-2xl font-bold">{balancesData.wallet_count || 0}</div>
              <div className="text-xs text-slate-400">Wallets Tracked</div>
            </div>
          </div>
          <div className="text-xs text-slate-500">Source: {balancesData.source}</div>
        </motion.div>
      )}

      {/* Wallets List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="text-center py-16">
            <Loader2 className="w-8 h-8 text-brand-sky mx-auto mb-4 animate-spin" />
            <p className="text-slate-400">Loading institutional wallets...</p>
          </div>
        ) : wallets.length === 0 ? (
          <div className="text-center py-16">
            <Wallet className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-300 mb-2">No wallets found</h3>
          </div>
        ) : (
          wallets.map((wallet, index) => (
            <motion.div
              key={wallet.address}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.03 }}
              className="glass-card p-4 rounded-xl hover:border-white/10 transition-colors"
            >
              <div className="flex items-start gap-4">
                {/* Entity Badge */}
                <div className={cn(
                  "w-14 h-14 rounded-xl flex flex-col items-center justify-center flex-shrink-0 border",
                  getChainColor(wallet.chain)
                )}>
                  <span className="text-xs font-bold uppercase">{wallet.chain === 'ethereum' ? 'ETH' : 'XRP'}</span>
                </div>

                {/* Wallet Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-medium">{wallet.label}</span>
                    <span className={cn("px-2 py-0.5 rounded text-[10px] uppercase font-medium", getEntityColor(wallet.entity))}>
                      {wallet.entity}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-slate-700 text-slate-300">
                      {wallet.type}
                    </span>
                    {wallet.verified && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 flex items-center gap-1">
                        <Check className="w-3 h-3" /> Verified
                      </span>
                    )}
                  </div>

                  {/* Address */}
                  <div className="flex items-center gap-2 mb-2">
                    <code className="font-mono text-xs text-slate-400 bg-slate-800 px-2 py-1 rounded">
                      {wallet.address.slice(0, 10)}...{wallet.address.slice(-8)}
                    </code>
                    <button
                      onClick={() => copyAddress(wallet.address)}
                      className="p-1 hover:bg-white/5 rounded"
                    >
                      {copiedAddress === wallet.address ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5 text-slate-500" />
                      )}
                    </button>
                    <a
                      href={getExplorerUrl(wallet.chain, wallet.address)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1 hover:bg-white/5 rounded text-slate-500 hover:text-brand-sky"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>

                  {/* Notes */}
                  <p className="text-xs text-slate-500">{wallet.notes}</p>
                  <p className="text-[10px] text-slate-600 mt-1">Source: {wallet.source}</p>
                </div>

                {/* Balance (if available from balancesData) */}
                {balancesData?.wallets && (
                  <div className="text-right flex-shrink-0">
                    {balancesData.wallets.find((b: WalletBalance) => b.address.toLowerCase() === wallet.address.toLowerCase())?.balance_eth !== undefined && (
                      <div className="text-sm font-bold text-amber-400">
                        {balancesData.wallets.find((b: WalletBalance) => b.address.toLowerCase() === wallet.address.toLowerCase())?.balance_eth?.toFixed(4)} ETH
                      </div>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          ))
        )}
      </div>

      {/* Citadel Note */}
      <div className="glass-card rounded-2xl p-4 border border-slate-700">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-amber-400">Citadel Securities Note</h4>
            <p className="text-xs text-slate-400 mt-1">
              Citadel operates through partners (EDX Markets, prime brokers) and does not have publicly disclosed crypto wallet addresses. 
              Track via proxy signals: monitor large flows TO/FROM Binance, Coinbase, and Kraken for institutional activity patterns.
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useState, forwardRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ExternalLink, 
  Zap, 
  Coins, 
  TrendingUp, 
  Clock, 
  Layers,
  ChevronRight,
  Loader2,
  BarChart3
} from 'lucide-react';
import { fetchXrplFlowsHistory } from '../lib/api';
import { cn, timeAgo, formatUSD } from '../lib/utils';
import IsoFlowCard from './IsoFlowCard';
import EventDetailPanel from './EventDetailPanel';

function ClientTime({ timestamp }: { timestamp: string | number }) {
  const [mounted, setMounted] = useState(false);
  
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <span className="text-[11px] text-slate-500 ml-auto">
      {timeAgo(timestamp)}
    </span>
  );
}

interface EventListProps {
  events: any[];
  isLoading?: boolean;
}

const filterOptions = [
  { id: 'all', label: 'All Flows', icon: Layers },
  { id: 'zk', label: 'ZK / ETH', icon: Zap },
  { id: 'xrpl_iso', label: 'XRPL / ISO', icon: Coins },
] as const;

type FilterType = typeof filterOptions[number]['id'];

export default function EventList({ events, isLoading }: EventListProps) {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<FilterType>('all');
  const [selectedEvent, setSelectedEvent] = useState<any>(null);

  const { data: xrplHistory } = useQuery({
    queryKey: ['xrpl_flows_history'],
    queryFn: fetchXrplFlowsHistory,
    enabled: filter === 'xrpl_iso',
    staleTime: 60_000,
  });

  const prefetchFlow = (txHash?: string) => {
    if (!txHash) return;
    queryClient.prefetchQuery({
      queryKey: ['flow', txHash],
      queryFn: async () => {
        const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
        const url =
          base.replace(/\/$/, '') +
          `/flows?tx_hash=${encodeURIComponent(txHash)}&page_size=10`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to prefetch flow');
        return res.json();
      },
      staleTime: 30_000,
    });
  };

  const filteredEvents = events.filter((event) => {
    const t = String(event.type || '').toLowerCase();
    const net = String(event.network || event.features?.network || '').toLowerCase();
    if (filter === 'zk') {
      return t === 'zk' || t === 'dark_pool';
    }
    if (filter === 'xrpl_iso') {
      // Include XRPL-related types and networks
      if (['xrp', 'trustline', 'orderbook', 'rwa_amm', 'event'].includes(t)) return true;
      if (['xrpl', 'xrp', 'xlm', 'xdc', 'hbar'].includes(net)) return true;
      return false;
    }
    // 'all' filter shows everything
    return true;
  });

  let displayEvents = filteredEvents;

  if (filter === 'xrpl_iso' && xrplHistory?.items) {
    const baseIds = new Set(filteredEvents.map((e: any) => e.id));
    const extra = (xrplHistory.items as any[]).filter(
      (evt) => evt && !baseIds.has(evt.id),
    );
    displayEvents = [...filteredEvents, ...extra];
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-white/5 px-5 py-4">
        <div>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-brand-sky" />
            <h2 className="text-base font-semibold tracking-tight">Dark Flow Feed</h2>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Live detection of ZK proofs, dark pool activity, and institutional flows
          </p>
        </div>
        
        {/* Filter tabs */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-1/80 border border-white/5">
          {filterOptions.map((opt) => {
            const Icon = opt.icon;
            const isActive = filter === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => setFilter(opt.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                  isActive 
                    ? "bg-brand-sky/20 text-brand-sky shadow-sm" 
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{opt.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Event list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />
          </div>
        ) : displayEvents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-500">
            <Layers className="w-10 h-10 mb-3 opacity-50" />
            <p className="text-sm">No events detected</p>
            <p className="text-xs mt-1">Waiting for dark flow signals...</p>
          </div>
        ) : (
          <ul className="divide-y divide-white/5">
            <AnimatePresence mode="popLayout" initial={false}>
              {displayEvents.map((event, index) => (
                <EventRow 
                  key={event.id} 
                  event={event} 
                  index={index}
                  filter={filter}
                  onHover={prefetchFlow}
                  onSelect={setSelectedEvent}
                />
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>

      {/* Footer stats */}
      <div className="border-t border-white/5 px-5 py-3 flex items-center justify-between text-xs text-slate-500">
        <span>{displayEvents.length} events</span>
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          Real-time
        </span>
      </div>

      {/* Event Detail Panel */}
      <AnimatePresence>
        {selectedEvent && (
          <EventDetailPanel 
            key={selectedEvent.id || 'detail'}
            event={selectedEvent} 
            onClose={() => setSelectedEvent(null)} 
          />
        )}
      </AnimatePresence>
    </div>
  );
}

interface EventRowProps {
  event: any;
  index: number;
  filter: FilterType;
  onHover: (txHash?: string) => void;
  onSelect: (event: any) => void;
}

// Generate meaningful event description
function getEventDescription(event: any): string {
  const conf = String(event.confidence || '').toLowerCase();
  const type = String(event.type || '').toLowerCase();
  const network = String(event.network || event.features?.network || '').toUpperCase();
  const usd = event.features?.usd_value;
  
  // Build a meaningful description
  const confLabel = conf === 'high' ? 'High-confidence' : conf === 'medium' ? 'Notable' : 'Detected';
  
  if (type === 'zk') {
    return `${confLabel} ZK proof activity detected on ${network || 'ETH'}. Possible institutional dark pool execution.`;
  }
  if (type === 'dark_pool') {
    return `${confLabel} dark pool flow detected. Large block trade signaling institutional positioning.`;
  }
  if (type === 'xrp' || type === 'trustline') {
    return `${confLabel} XRPL flow detected. Cross-border settlement pattern indicates smart money movement.`;
  }
  if (type === 'orderbook') {
    return `${confLabel} order book imbalance detected. Sweep pattern with directional bias.`;
  }
  if (type === 'whale') {
    return `${confLabel} whale movement detected${usd ? ` (~$${(usd/1e6).toFixed(1)}M)` : ''}. Large holder repositioning.`;
  }
  if (type === 'rwa_amm') {
    return `${confLabel} RWA/AMM flow detected. Tokenized asset liquidity shift.`;
  }
  // Default for generic "event" type
  if (conf === 'high') {
    return `High-confidence institutional flow detected. Pattern suggests imminent market impact.`;
  }
  if (conf === 'medium') {
    return `Notable flow activity detected. Monitoring for follow-through signals.`;
  }
  return `Flow activity detected. Low confidence signal - pattern developing.`;
}

// Helper component for event row content (shared between Link and div wrappers)
function EventRowContent({ 
  event, 
  description, 
  isIsoFlow, 
  isHighConf, 
  isMediumConf, 
  conf, 
  type, 
  network, 
  usd, 
  ruleScore,
  getTypeIcon,
  getTypeColor
}: {
  event: any;
  description: string;
  isIsoFlow: boolean;
  isHighConf: boolean;
  isMediumConf: boolean;
  conf: string;
  type: string;
  network: any;
  usd: number | undefined;
  ruleScore: number | undefined;
  getTypeIcon: () => JSX.Element;
  getTypeColor: () => string;
}) {
  return (
    <>
      {/* Type icon */}
      <div className={cn(
        "flex-shrink-0 w-9 h-9 rounded-lg border flex items-center justify-center mt-0.5",
        getTypeColor()
      )}>
        {getTypeIcon()}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {isIsoFlow ? (
          <IsoFlowCard event={event} />
        ) : (
          <>
            {/* Message - use meaningful description */}
            <p className="text-sm leading-relaxed text-slate-200 group-hover:text-white transition-colors line-clamp-2">
              {description}
            </p>

            {/* Meta row */}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {/* Confidence badge */}
              <span className={cn(
                "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium",
                isHighConf && "badge-high",
                isMediumConf && "badge-medium",
                !isHighConf && !isMediumConf && "badge-low"
              )}>
                <span className={cn(
                  "w-1.5 h-1.5 rounded-full",
                  isHighConf && "bg-emerald-400",
                  isMediumConf && "bg-amber-400",
                  !isHighConf && !isMediumConf && "bg-slate-400"
                )} />
                {conf || 'low'}
              </span>

              {/* Type */}
              <span className="px-2 py-0.5 rounded-full bg-surface-2/80 text-[10px] font-medium uppercase tracking-wider text-slate-300">
                {type}
              </span>

              {/* Network */}
              {network && (
                <span className="px-2 py-0.5 rounded-full bg-surface-1 text-[10px] text-slate-400 border border-white/5">
                  {network}
                </span>
              )}

              {/* USD value */}
              {typeof usd === 'number' && usd > 0 && (
                <span className="text-[11px] font-mono text-slate-400">
                  {formatUSD(usd)}
                </span>
              )}

              {/* Time */}
              {event.timestamp && (
                <ClientTime timestamp={event.timestamp} />
              )}
            </div>
          </>
        )}
      </div>

      {/* Right side: score + expand icon */}
      <div className="flex-shrink-0 flex flex-col items-end gap-2">
        {ruleScore != null && ruleScore >= 50 && (
          <div className={cn(
            "px-2 py-1 rounded-lg text-xs font-semibold tabular-nums",
            ruleScore >= 80 
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" 
              : ruleScore >= 60 
                ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                : "bg-slate-700/50 text-slate-300 border border-slate-600/50"
          )}>
            {ruleScore.toFixed(0)}
          </div>
        )}
        <div className="flex items-center gap-1">
          <BarChart3 className="w-4 h-4 text-slate-600 group-hover:text-brand-sky transition-colors" />
          <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 group-hover:translate-x-0.5 transition-all" />
        </div>
      </div>
    </>
  );
}

const EventRow = forwardRef<HTMLLIElement, EventRowProps>(function EventRow({ 
  event, 
  index, 
  filter,
  onHover,
  onSelect
}, ref) {
  // Only use REAL blockchain tx hashes (must start with 0x for ETH or be valid XRPL hash)
  const rawTxHash = event.features?.tx_hash || event.features?.txHash || event.tx_hash;
  const txHash = rawTxHash && (rawTxHash.startsWith('0x') || /^[A-F0-9]{64}$/i.test(rawTxHash)) 
    ? rawTxHash 
    : undefined;
  const conf = String(event.confidence || '').toLowerCase();
  const type = String(event.type || '').toLowerCase();
  const network = event.network || event.features?.network;
  const usd = event.features?.usd_value as number | undefined;
  const ruleScore = event.rule_score as number | undefined;
  const description = getEventDescription(event);

  const isIsoFlow =
    filter === 'xrpl_iso' &&
    ['xrp', 'trustline', 'orderbook', 'rwa_amm'].includes(type);

  const isHighConf = conf === 'high';
  const isMediumConf = conf === 'medium';

  const getTypeIcon = () => {
    if (type === 'zk') return <Zap className="w-4 h-4" />;
    if (type === 'xrp' || type === 'trustline') return <Coins className="w-4 h-4" />;
    return <TrendingUp className="w-4 h-4" />;
  };

  const getTypeColor = () => {
    if (type === 'zk') return 'text-purple-400 bg-purple-500/10 border-purple-500/30';
    if (type === 'xrp') return 'text-blue-400 bg-blue-500/10 border-blue-500/30';
    if (type === 'solana_amm') return 'text-green-400 bg-green-500/10 border-green-500/30';
    return 'text-slate-400 bg-slate-500/10 border-slate-500/30';
  };

  return (
    <motion.li
      ref={ref}
      layout
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -20 }}
      transition={{ 
        duration: 0.2, 
        delay: index < 5 ? index * 0.03 : 0 
      }}
      className={cn(
        "group relative event-row-hover",
        isHighConf && "bg-emerald-500/[0.03]",
        isMediumConf && "bg-amber-500/[0.02]"
      )}
      onMouseEnter={() => {
        if (isHighConf) onHover(txHash);
      }}
    >
      {/* Left accent bar for high confidence */}
      {isHighConf && (
        <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-emerald-400 to-emerald-600" />
      )}

      {/* Content wrapper - only link if we have a real tx hash */}
      {txHash ? (
        <Link
          href={`/flow/${encodeURIComponent(txHash)}`}
          className="flex items-start gap-4 px-5 py-4 w-full text-left"
        >
          <EventRowContent 
            event={event} 
            description={description} 
            isIsoFlow={isIsoFlow}
            isHighConf={isHighConf}
            isMediumConf={isMediumConf}
            conf={conf}
            type={type}
            network={network}
            usd={usd}
            ruleScore={ruleScore}
            getTypeIcon={getTypeIcon}
            getTypeColor={getTypeColor}
          />
        </Link>
      ) : (
        <div className="flex items-start gap-4 px-5 py-4 w-full text-left cursor-default">
          <EventRowContent 
            event={event} 
            description={description} 
            isIsoFlow={isIsoFlow}
            isHighConf={isHighConf}
            isMediumConf={isMediumConf}
            conf={conf}
            type={type}
            network={network}
            usd={usd}
            ruleScore={ruleScore}
            getTypeIcon={getTypeIcon}
            getTypeColor={getTypeColor}
          />
        </div>
      )}
    </motion.li>
  );
});

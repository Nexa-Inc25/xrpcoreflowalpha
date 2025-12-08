'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bell,
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
  Zap,
  TrendingUp,
  Wallet,
  AlertTriangle,
  Clock,
  Volume2,
  VolumeX,
  Filter,
  Server,
  Info,
} from 'lucide-react';
import { cn, timeAgo } from '../../lib/utils';

interface Alert {
  id: string;
  name: string;
  type: 'confidence' | 'volume' | 'wallet' | 'pattern';
  condition: string;
  threshold: number;
  enabled: boolean;
  triggered: number;
  lastTriggered?: string;
  createdAt: string;
}

interface AlertHistory {
  id: string;
  alertId: string;
  alertName: string;
  message: string;
  timestamp: string;
  read: boolean;
}

interface SystemAlert {
  level: 'warning' | 'info' | 'error';
  component: string;
  message: string;
  action: string;
}

// No mock data - empty initial state
const mockAlerts: Alert[] = [];
const mockHistory: AlertHistory[] = [];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>(mockAlerts);
  const [history, setHistory] = useState<AlertHistory[]>(mockHistory);
  const [activeTab, setActiveTab] = useState<'rules' | 'history' | 'system'>('system');
  
  // Fetch system alerts from API
  const { data: systemAlerts } = useQuery({
    queryKey: ['system_alerts'],
    queryFn: async () => {
      const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
      const res = await fetch(`${base}/admin/alerts`);
      if (!res.ok) return { alerts: [], alert_count: 0 };
      return res.json();
    },
    refetchInterval: 30_000,
  });
  const [showCreateModal, setShowCreateModal] = useState(false);

  const toggleAlert = (id: string) => {
    setAlerts(alerts.map(a => 
      a.id === id ? { ...a, enabled: !a.enabled } : a
    ));
  };

  const deleteAlert = (id: string) => {
    setAlerts(alerts.filter(a => a.id !== id));
  };

  const markAsRead = (id: string) => {
    setHistory(history.map(h => 
      h.id === id ? { ...h, read: true } : h
    ));
  };

  const markAllAsRead = () => {
    setHistory(history.map(h => ({ ...h, read: true })));
  };

  const unreadCount = history.filter(h => !h.read).length;

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'confidence': return <Zap className="w-4 h-4" />;
      case 'volume': return <TrendingUp className="w-4 h-4" />;
      case 'wallet': return <Wallet className="w-4 h-4" />;
      default: return <AlertTriangle className="w-4 h-4" />;
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'confidence': return 'text-purple-400 bg-purple-500/10 border-purple-500/30';
      case 'volume': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
      case 'wallet': return 'text-brand-sky bg-brand-sky/10 border-brand-sky/30';
      default: return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="w-full max-w-[1200px] mx-auto px-4 lg:px-6 py-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start justify-between mb-8"
        >
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500/20 to-red-500/20 border border-amber-500/30 flex items-center justify-center">
                <Bell className="w-5 h-5 text-amber-400" />
              </div>
              <h1 className="text-2xl font-semibold">Alerts</h1>
              {unreadCount > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-red-500 text-white text-xs font-medium">
                  {unreadCount}
                </span>
              )}
            </div>
            <p className="text-slate-400">Custom alert rules and notification history</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-sky text-white font-medium hover:bg-brand-sky/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Alert
          </button>
        </motion.div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 rounded-xl bg-surface-1 border border-white/5 mb-6">
          <button
            onClick={() => setActiveTab('system')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors relative",
              activeTab === 'system' 
                ? "bg-brand-sky/20 text-brand-sky" 
                : "text-slate-400 hover:text-white"
            )}
          >
            <Server className="w-4 h-4" />
            System
            {(systemAlerts?.alert_count || 0) > 0 && activeTab !== 'system' && (
              <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-amber-500 text-[10px] flex items-center justify-center text-black font-bold">
                {systemAlerts?.alert_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('rules')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors",
              activeTab === 'rules' 
                ? "bg-brand-sky/20 text-brand-sky" 
                : "text-slate-400 hover:text-white"
            )}
          >
            <Filter className="w-4 h-4" />
            Alert Rules
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors relative",
              activeTab === 'history' 
                ? "bg-brand-sky/20 text-brand-sky" 
                : "text-slate-400 hover:text-white"
            )}
          >
            <Clock className="w-4 h-4" />
            History
            {unreadCount > 0 && activeTab !== 'history' && (
              <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-[10px] flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </button>
        </div>

        {/* Content */}
        <AnimatePresence mode="wait">
          {activeTab === 'system' ? (
            <motion.div
              key="system"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              {(!systemAlerts?.alerts || systemAlerts.alerts.length === 0) ? (
                <div className="text-center py-16">
                  <Check className="w-12 h-12 text-emerald-500 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-slate-300 mb-2">All systems operational</h3>
                  <p className="text-sm text-slate-500">No issues detected</p>
                </div>
              ) : (
                (systemAlerts.alerts as SystemAlert[]).map((alert, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className={cn(
                      "glass-card p-4 rounded-xl border",
                      alert.level === 'error' && "border-red-500/30 bg-red-500/5",
                      alert.level === 'warning' && "border-amber-500/30 bg-amber-500/5",
                      alert.level === 'info' && "border-blue-500/30 bg-blue-500/5"
                    )}
                  >
                    <div className="flex items-start gap-4">
                      <div className={cn(
                        "w-10 h-10 rounded-lg border flex items-center justify-center flex-shrink-0",
                        alert.level === 'error' && "text-red-400 bg-red-500/10 border-red-500/30",
                        alert.level === 'warning' && "text-amber-400 bg-amber-500/10 border-amber-500/30",
                        alert.level === 'info' && "text-blue-400 bg-blue-500/10 border-blue-500/30"
                      )}>
                        {alert.level === 'error' ? <AlertTriangle className="w-5 h-5" /> : 
                         alert.level === 'warning' ? <AlertTriangle className="w-5 h-5" /> : 
                         <Info className="w-5 h-5" />}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={cn(
                            "text-xs px-2 py-0.5 rounded uppercase font-medium",
                            alert.level === 'error' && "bg-red-500/20 text-red-400",
                            alert.level === 'warning' && "bg-amber-500/20 text-amber-400",
                            alert.level === 'info' && "bg-blue-500/20 text-blue-400"
                          )}>
                            {alert.level}
                          </span>
                          <span className="text-xs text-slate-500">{alert.component}</span>
                        </div>
                        <h3 className="font-medium text-slate-200">{alert.message}</h3>
                        <p className="text-sm text-slate-400 mt-1">
                          <span className="text-slate-500">Action:</span> {alert.action}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </motion.div>
          ) : activeTab === 'rules' ? (
            <motion.div
              key="rules"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              {alerts.length === 0 ? (
                <div className="text-center py-16">
                  <Bell className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-slate-300 mb-2">No custom alerts configured</h3>
                  <p className="text-sm text-slate-500">Create your first alert rule to get notified</p>
                </div>
              ) : (
                alerts.map((alert, index) => (
                  <motion.div
                    key={alert.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className={cn(
                      "glass-card p-4 rounded-xl transition-opacity",
                      !alert.enabled && "opacity-60"
                    )}
                  >
                    <div className="flex items-start gap-4">
                      <div className={cn(
                        "w-10 h-10 rounded-lg border flex items-center justify-center flex-shrink-0",
                        getTypeColor(alert.type)
                      )}>
                        {getTypeIcon(alert.type)}
                      </div>

                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-medium">{alert.name}</h3>
                          {alert.enabled ? (
                            <Volume2 className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <VolumeX className="w-3.5 h-3.5 text-slate-500" />
                          )}
                        </div>
                        <p className="text-sm text-slate-400">
                          {alert.condition} {alert.type === 'volume' ? `$${alert.threshold.toLocaleString()}` : `${alert.threshold}%`}
                        </p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                          <span>Triggered {alert.triggered} times</span>
                          {alert.lastTriggered && (
                            <span>Last: {timeAgo(alert.lastTriggered)}</span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleAlert(alert.id)}
                          className={cn(
                            "w-10 h-6 rounded-full p-1 transition-colors",
                            alert.enabled ? "bg-emerald-500" : "bg-surface-2"
                          )}
                        >
                          <motion.div
                            className="w-4 h-4 rounded-full bg-white"
                            animate={{ x: alert.enabled ? 16 : 0 }}
                          />
                        </button>
                        <button
                          onClick={() => deleteAlert(alert.id)}
                          className="p-2 rounded-lg text-slate-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </motion.div>
          ) : (
            <motion.div
              key="history"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              {unreadCount > 0 && (
                <div className="flex justify-end mb-4">
                  <button
                    onClick={markAllAsRead}
                    className="text-sm text-brand-sky hover:text-brand-sky/80 transition-colors"
                  >
                    Mark all as read
                  </button>
                </div>
              )}

              <div className="space-y-3">
                {history.length === 0 ? (
                  <div className="text-center py-16">
                    <Clock className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-slate-300 mb-2">No alert history</h3>
                    <p className="text-sm text-slate-500">Triggered alerts will appear here</p>
                  </div>
                ) : (
                  history.map((item, index) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className={cn(
                        "p-4 rounded-xl border transition-colors cursor-pointer",
                        item.read 
                          ? "bg-surface-1/50 border-white/5"
                          : "bg-brand-sky/5 border-brand-sky/20"
                      )}
                      onClick={() => markAsRead(item.id)}
                    >
                      <div className="flex items-start gap-3">
                        {!item.read && (
                          <span className="w-2 h-2 rounded-full bg-brand-sky mt-2 flex-shrink-0" />
                        )}
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs px-2 py-0.5 rounded bg-surface-2 text-slate-400">
                              {item.alertName}
                            </span>
                            <span className="text-xs text-slate-500">
                              {timeAgo(item.timestamp)}
                            </span>
                          </div>
                          <p className="text-sm text-slate-200">{item.message}</p>
                        </div>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Create Alert Modal */}
        <AnimatePresence>
          {showCreateModal && (
            <CreateAlertModal
              onClose={() => setShowCreateModal(false)}
              onCreate={(alert) => {
                setAlerts([alert, ...alerts]);
                setShowCreateModal(false);
              }}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function CreateAlertModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (alert: Alert) => void;
}) {
  const [name, setName] = useState('');
  const [type, setType] = useState<Alert['type']>('confidence');
  const [threshold, setThreshold] = useState(80);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name) return;

    onCreate({
      id: Math.random().toString(36).slice(2),
      name,
      type,
      condition: type === 'volume' ? 'Volume ≥' : type === 'confidence' ? 'Confidence ≥' : 'Pattern =',
      threshold,
      enabled: true,
      triggered: 0,
      createdAt: new Date().toISOString(),
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
        <h2 className="text-lg font-semibold mb-4">Create Alert</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm text-slate-400 mb-2 block">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., High Volume Alert"
              className="w-full px-4 py-2.5 rounded-lg bg-surface-2 border border-white/5 text-sm placeholder:text-slate-500 focus:outline-none focus:border-brand-sky/50"
            />
          </div>

          <div>
            <label className="text-sm text-slate-400 mb-2 block">Alert Type</label>
            <div className="grid grid-cols-2 gap-2">
              {(['confidence', 'volume', 'wallet', 'pattern'] as const).map((t) => (
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

          {(type === 'confidence' || type === 'volume') && (
            <div>
              <label className="text-sm text-slate-400 mb-2 block">
                Threshold {type === 'volume' ? '(USD)' : '(%)'}
              </label>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full px-4 py-2.5 rounded-lg bg-surface-2 border border-white/5 text-sm focus:outline-none focus:border-brand-sky/50"
              />
            </div>
          )}

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
              disabled={!name}
              className="flex-1 px-4 py-2.5 rounded-lg bg-brand-sky text-white font-medium hover:bg-brand-sky/90 transition-colors disabled:opacity-50"
            >
              Create Alert
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}

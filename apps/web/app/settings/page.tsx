'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Settings,
  Key,
  Bell,
  CreditCard,
  Shield,
  Copy,
  Check,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  RefreshCw,
  ExternalLink,
  Send,
  Crown,
  Zap,
  Mail,
  Smartphone,
  Globe,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '../../lib/utils';

// Telegram icon component
function TelegramIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
    </svg>
  );
}

interface ApiKey {
  id: string;
  name: string;
  key: string;
  createdAt: string;
  lastUsed?: string;
  permissions: string[];
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'general' | 'api' | 'notifications' | 'billing'>('general');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState<string | null>(null);
  const [telegramLinked, setTelegramLinked] = useState(false);
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [pushAlerts, setPushAlerts] = useState(true);
  const [highConfOnly, setHighConfOnly] = useState(false);
  
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([
    {
      id: '1',
      name: 'Production API',
      key: 'zk_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6',
      createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30).toISOString(),
      lastUsed: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      permissions: ['read:flows', 'read:analytics', 'write:watchlist'],
    },
    {
      id: '2',
      name: 'Development',
      key: 'zk_test_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4',
      createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7).toISOString(),
      permissions: ['read:flows'],
    },
  ]);

  const copyToClipboard = async (id: string, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const generateNewKey = () => {
    const newKey: ApiKey = {
      id: Math.random().toString(36).slice(2),
      name: `API Key ${apiKeys.length + 1}`,
      key: `zk_live_${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`,
      createdAt: new Date().toISOString(),
      permissions: ['read:flows'],
    };
    setApiKeys([...apiKeys, newKey]);
  };

  const deleteKey = (id: string) => {
    setApiKeys(apiKeys.filter(k => k.id !== id));
  };

  const tabs = [
    { id: 'general', label: 'General', icon: Settings },
    { id: 'api', label: 'API Keys', icon: Key },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'billing', label: 'Billing', icon: CreditCard },
  ] as const;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="w-full max-w-[1100px] mx-auto px-4 lg:px-6 py-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-500/20 to-slate-600/20 border border-slate-500/30 flex items-center justify-center">
              <Settings className="w-5 h-5 text-slate-400" />
            </div>
            <h1 className="text-2xl font-semibold">Settings</h1>
          </div>
          <p className="text-slate-400">Manage your account, API keys, and preferences</p>
        </motion.div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 rounded-xl bg-surface-1 border border-white/5 mb-8 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap",
                activeTab === tab.id 
                  ? "bg-brand-sky/20 text-brand-sky" 
                  : "text-slate-400 hover:text-white"
              )}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <AnimatePresence mode="wait">
          {activeTab === 'general' && (
            <motion.div
              key="general"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              {/* Profile Section */}
              <div className="glass-card p-6 rounded-xl">
                <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
                  <Shield className="w-4 h-4 text-brand-sky" />
                  Profile
                </h3>
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-brand-sky to-brand-purple flex items-center justify-center text-2xl font-medium text-white">
                    P
                  </div>
                  <div>
                    <p className="font-medium text-lg">
                      Pro User
                    </p>
                    <p className="text-slate-400 text-sm">pro@zkalphaflow.com</p>
                    <p className="text-xs text-slate-500 mt-1">
                      Member since Dec 1, 2024
                    </p>
                  </div>
                </div>
              </div>

              {/* Preferences */}
              <div className="glass-card p-6 rounded-xl">
                <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
                  <Globe className="w-4 h-4 text-brand-purple" />
                  Preferences
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Dark Mode</p>
                      <p className="text-sm text-slate-400">Always enabled for trading focus</p>
                    </div>
                    <div className="w-10 h-6 rounded-full bg-brand-sky p-1">
                      <div className="w-4 h-4 rounded-full bg-white ml-4" />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Sound Alerts</p>
                      <p className="text-sm text-slate-400">Play sound for high-confidence signals</p>
                    </div>
                    <button
                      onClick={() => setHighConfOnly(!highConfOnly)}
                      className={cn(
                        "w-10 h-6 rounded-full p-1 transition-colors",
                        highConfOnly ? "bg-brand-sky" : "bg-surface-2"
                      )}
                    >
                      <motion.div
                        className="w-4 h-4 rounded-full bg-white"
                        animate={{ x: highConfOnly ? 16 : 0 }}
                      />
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'api' && (
            <motion.div
              key="api"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              <div className="glass-card p-6 rounded-xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium flex items-center gap-2">
                    <Key className="w-4 h-4 text-brand-sky" />
                    API Keys
                  </h3>
                  <button
                    onClick={generateNewKey}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-brand-sky/20 text-brand-sky text-sm font-medium hover:bg-brand-sky/30 transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    Generate New Key
                  </button>
                </div>
                
                <div className="space-y-3">
                  {apiKeys.map((apiKey) => (
                    <div key={apiKey.id} className="p-4 rounded-lg bg-surface-2/50 border border-white/5">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <p className="font-medium">{apiKey.name}</p>
                          <p className="text-xs text-slate-500 mt-0.5">
                            Created {new Date(apiKey.createdAt).toLocaleDateString()}
                            {apiKey.lastUsed && ` • Last used ${new Date(apiKey.lastUsed).toLocaleString()}`}
                          </p>
                        </div>
                        <button
                          onClick={() => deleteKey(apiKey.id)}
                          className="p-1.5 rounded-lg text-slate-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      
                      <div className="flex items-center gap-2 mt-3">
                        <code className="flex-1 px-3 py-2 rounded-lg bg-surface-1 font-mono text-sm text-slate-300 overflow-x-auto">
                          {showKey === apiKey.id ? apiKey.key : apiKey.key.replace(/./g, '•').slice(0, 20) + '...'}
                        </code>
                        <button
                          onClick={() => setShowKey(showKey === apiKey.id ? null : apiKey.id)}
                          className="p-2 rounded-lg bg-surface-1 text-slate-400 hover:text-white transition-colors"
                        >
                          {showKey === apiKey.id ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                        <button
                          onClick={() => copyToClipboard(apiKey.id, apiKey.key)}
                          className="p-2 rounded-lg bg-surface-1 text-slate-400 hover:text-white transition-colors"
                        >
                          {copiedKey === apiKey.id ? (
                            <Check className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <Copy className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                      
                      <div className="flex flex-wrap gap-1 mt-3">
                        {apiKey.permissions.map((perm) => (
                          <span key={perm} className="px-2 py-0.5 rounded text-[10px] bg-slate-500/20 text-slate-400">
                            {perm}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-300">
                      Keep your API keys secure. Never share them publicly or commit them to version control.
                    </p>
                  </div>
                </div>
              </div>

              {/* API Documentation */}
              <div className="glass-card p-6 rounded-xl">
                <h3 className="text-sm font-medium mb-4">API Documentation</h3>
                <p className="text-sm text-slate-400 mb-4">
                  Access real-time flow data, analytics, and alerts programmatically.
                </p>
                <a
                  href="https://docs.zkalphaflow.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-2 text-sm font-medium hover:bg-surface-2/80 transition-colors"
                >
                  View Documentation
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </motion.div>
          )}

          {activeTab === 'notifications' && (
            <motion.div
              key="notifications"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              {/* Telegram Integration */}
              <div className="glass-card p-6 rounded-xl">
                <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
                  <TelegramIcon className="w-4 h-4 text-[#0088cc]" />
                  Telegram Alerts
                </h3>
                {telegramLinked ? (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-[#0088cc]/20 flex items-center justify-center">
                        <TelegramIcon className="w-5 h-5 text-[#0088cc]" />
                      </div>
                      <div>
                        <p className="font-medium">Connected</p>
                        <p className="text-sm text-slate-400">@your_telegram_username</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setTelegramLinked(false)}
                      className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/30 transition-colors"
                    >
                      Disconnect
                    </button>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm text-slate-400 mb-4">
                      Connect your Telegram to receive real-time alerts for high-confidence signals.
                    </p>
                    <button
                      onClick={() => setTelegramLinked(true)}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#0088cc] text-white font-medium hover:bg-[#0088cc]/90 transition-colors"
                    >
                      <TelegramIcon className="w-5 h-5" />
                      Connect Telegram
                    </button>
                  </div>
                )}
              </div>

              {/* Email & Push Settings */}
              <div className="glass-card p-6 rounded-xl">
                <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
                  <Bell className="w-4 h-4 text-amber-400" />
                  Alert Preferences
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Mail className="w-5 h-5 text-slate-400" />
                      <div>
                        <p className="font-medium">Email Alerts</p>
                        <p className="text-sm text-slate-400">Daily digest + critical signals</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setEmailAlerts(!emailAlerts)}
                      className={cn(
                        "w-10 h-6 rounded-full p-1 transition-colors",
                        emailAlerts ? "bg-brand-sky" : "bg-surface-2"
                      )}
                    >
                      <motion.div
                        className="w-4 h-4 rounded-full bg-white"
                        animate={{ x: emailAlerts ? 16 : 0 }}
                      />
                    </button>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Smartphone className="w-5 h-5 text-slate-400" />
                      <div>
                        <p className="font-medium">Push Notifications</p>
                        <p className="text-sm text-slate-400">Real-time mobile alerts</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setPushAlerts(!pushAlerts)}
                      className={cn(
                        "w-10 h-6 rounded-full p-1 transition-colors",
                        pushAlerts ? "bg-brand-sky" : "bg-surface-2"
                      )}
                    >
                      <motion.div
                        className="w-4 h-4 rounded-full bg-white"
                        animate={{ x: pushAlerts ? 16 : 0 }}
                      />
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Zap className="w-5 h-5 text-slate-400" />
                      <div>
                        <p className="font-medium">High Confidence Only</p>
                        <p className="text-sm text-slate-400">Only alert on 80%+ confidence</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setHighConfOnly(!highConfOnly)}
                      className={cn(
                        "w-10 h-6 rounded-full p-1 transition-colors",
                        highConfOnly ? "bg-brand-sky" : "bg-surface-2"
                      )}
                    >
                      <motion.div
                        className="w-4 h-4 rounded-full bg-white"
                        animate={{ x: highConfOnly ? 16 : 0 }}
                      />
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'billing' && (
            <motion.div
              key="billing"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              {/* Current Plan */}
              <div className="glass-card p-6 rounded-xl border-2 border-amber-500/30">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 flex items-center justify-center">
                      <Crown className="w-6 h-6 text-amber-400" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold">Pro Plan</h3>
                      <p className="text-slate-400">$99/month • Billed monthly</p>
                    </div>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400 text-sm font-medium">
                    Active
                  </span>
                </div>
                
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="p-3 rounded-lg bg-surface-2/50">
                    <p className="text-xs text-slate-400 mb-1">Next billing date</p>
                    <p className="font-medium">Jan 5, 2025</p>
                  </div>
                  <div className="p-3 rounded-lg bg-surface-2/50">
                    <p className="text-xs text-slate-400 mb-1">API calls this month</p>
                    <p className="font-medium">12,847 / Unlimited</p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button className="px-4 py-2 rounded-lg bg-surface-2 text-sm font-medium hover:bg-surface-2/80 transition-colors">
                    Manage Subscription
                  </button>
                  <button className="px-4 py-2 rounded-lg bg-surface-2 text-sm font-medium hover:bg-surface-2/80 transition-colors">
                    View Invoices
                  </button>
                </div>
              </div>

              {/* Features */}
              <div className="glass-card p-6 rounded-xl">
                <h3 className="text-sm font-medium mb-4">Plan Features</h3>
                <div className="grid gap-3">
                  {[
                    'Unlimited real-time flow detection',
                    'Unlimited API access',
                    'Telegram & email alerts',
                    'Advanced analytics dashboard',
                    'Historical data (90 days)',
                    'Wallet clustering & tracking',
                    'Priority support',
                    'Custom alert thresholds',
                  ].map((feature) => (
                    <div key={feature} className="flex items-center gap-2 text-sm">
                      <Check className="w-4 h-4 text-emerald-400" />
                      {feature}
                    </div>
                  ))}
                </div>
              </div>

              {/* Payment Method */}
              <div className="glass-card p-6 rounded-xl">
                <h3 className="text-sm font-medium mb-4 flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-brand-sky" />
                  Payment Method
                </h3>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-8 rounded bg-slate-700 flex items-center justify-center text-xs font-bold">
                      VISA
                    </div>
                    <div>
                      <p className="font-medium">•••• •••• •••• 4242</p>
                      <p className="text-sm text-slate-400">Expires 12/26</p>
                    </div>
                  </div>
                  <button className="px-3 py-1.5 rounded-lg bg-surface-2 text-sm font-medium hover:bg-surface-2/80 transition-colors">
                    Update
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

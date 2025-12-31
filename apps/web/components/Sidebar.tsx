'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import {
  Zap,
  BarChart3,
  Star,
  Settings,
  Bell,
  Wallet,
  TrendingUp,
  Activity,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Crown,
  Fingerprint,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useSidebar } from '../contexts/SidebarContext';

const baseNavItems = [
  { href: '/', label: 'Dashboard', icon: Activity, badge: 'Live' },
  { href: '/fingerprints', label: 'Algo Fingerprints', icon: Fingerprint },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/backtest', label: 'Backtest', icon: TrendingUp },
  { href: '/watchlist', label: 'Watchlist', icon: Star },
  { href: '/alerts', label: 'Alerts', icon: Bell }, // Badge fetched from API
  { href: '/wallets', label: 'Wallets', icon: Wallet },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { collapsed, toggle, mobileOpen, setMobileOpen } = useSidebar();
  
  // Fetch real alert count from API
  const { data: alertData } = useQuery({
    queryKey: ['system_alerts'],
    queryFn: async () => {
      const base = process.env.NEXT_PUBLIC_API_BASE || 'https://api.zkalphaflow.com';
      const res = await fetch(`${base}/admin/alerts`);
      if (!res.ok) return { alert_count: 0, alerts: [] };
      return res.json();
    },
    refetchInterval: 30_000,
  });
  
  // Only count warning and error level alerts, not info
  const actionableAlertCount = alertData?.alerts?.filter(
    (alert: any) => alert.level === 'warning' || alert.level === 'error'
  ).length || 0;
  
  // Build nav items with real alert count
  const navItems = baseNavItems.map(item => {
    if (item.href === '/alerts' && actionableAlertCount > 0) {
      return { ...item, badge: String(actionableAlertCount) };
    }
    return item;
  });
  
  const handleSignOut = () => {
    window.location.href = '/sign-in';
  };

  // Close mobile menu when navigating
  const handleNavClick = () => {
    setMobileOpen(false);
  };

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 72 : 240 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "fixed left-0 top-0 h-screen flex flex-col border-r border-white/5 bg-surface-0 backdrop-blur-xl transition-transform duration-300 ease-out",
        mobileOpen ? "translate-x-0 z-50" : "-translate-x-full z-40",
        "lg:translate-x-0 lg:z-40"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-white/5">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-sky to-brand-purple flex items-center justify-center flex-shrink-0">
          <Zap className="w-5 h-5 text-white" />
        </div>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <h1 className="font-semibold text-white">ZK Alpha Flow</h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider">Pro Edition</p>
          </motion.div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={handleNavClick}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all group relative",
                isActive
                  ? "bg-brand-sky/10 text-brand-sky"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              )}
            >
              {isActive && (
                <motion.div
                  layoutId="activeNav"
                  className="absolute inset-0 rounded-lg bg-brand-sky/10 border border-brand-sky/20"
                  transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                />
              )}
              <Icon className={cn(
                "w-5 h-5 flex-shrink-0 relative z-10",
                isActive && "text-brand-sky"
              )} />
              {!collapsed && (
                <span className="text-sm font-medium relative z-10">{item.label}</span>
              )}
              {!collapsed && item.badge && (
                <span className={cn(
                  "ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium relative z-10",
                  item.badge === 'Live' 
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-brand-purple/20 text-brand-purple"
                )}>
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Pro Badge */}
      {!collapsed && (
        <div className="mx-3 mb-3 p-3 rounded-xl bg-gradient-to-br from-brand-purple/20 to-brand-sky/20 border border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <Crown className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-medium text-white">Pro Plan</span>
          </div>
          <p className="text-[11px] text-slate-400">Unlimited alerts, API access, priority support</p>
        </div>
      )}

      {/* User Section */}
      <div className="border-t border-white/5 p-3">
        <div className={cn(
          "flex items-center gap-3",
          collapsed && "justify-center"
        )}>
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-sky to-brand-purple flex items-center justify-center text-xs font-medium text-white flex-shrink-0">
            P
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  Pro User
                </p>
                <p className="text-[11px] text-slate-500 truncate">
                  pro@zkalphaflow.com
                </p>
              </div>
              <button
                onClick={handleSignOut}
                className="p-1.5 rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Collapse Toggle */}
      <button
        onClick={toggle}
        className="absolute -right-3 top-20 w-6 h-6 rounded-full bg-surface-1 border border-white/10 flex items-center justify-center text-slate-400 hover:text-white transition-colors"
      >
        {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
      </button>
    </motion.aside>
  );
}

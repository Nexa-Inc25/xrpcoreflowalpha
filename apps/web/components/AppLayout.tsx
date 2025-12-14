'use client';

import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Menu, X } from 'lucide-react';
import Sidebar from './Sidebar';
import { useSidebar } from '../contexts/SidebarContext';

// Runtime shim: patch WebSocket to redirect old ws://localhost:8010/events
// connections (from legacy bundles) to the correct API WS base.
if (typeof window !== 'undefined' && typeof window.WebSocket === 'function') {
  type PatchedWSConstructor = typeof WebSocket & { _zkPatched?: boolean };

  const OriginalWebSocket = window.WebSocket as PatchedWSConstructor;

  if (!OriginalWebSocket._zkPatched) {
    const PatchedWebSocket = (function (
      url: string | URL,
      protocols?: string | string[],
    ) {
      const raw = typeof url === 'string' ? url : url.toString();
      let nextUrl = raw;

      if (raw === 'ws://localhost:8010/events' || raw === 'ws://localhost:8010/events/') {
        const baseWs =
          process.env.NEXT_PUBLIC_API_WS_BASE || 'wss://api.zkalphaflow.com';
        nextUrl = baseWs.replace(/\/$/, '') + '/events';
      }

      return new OriginalWebSocket(nextUrl, protocols as any);
    }) as unknown as PatchedWSConstructor;

    // Preserve prototype and mark as patched
    PatchedWebSocket.prototype = OriginalWebSocket.prototype;
    PatchedWebSocket._zkPatched = true;
    window.WebSocket = PatchedWebSocket;
  }
}

// Pages that should NOT show the sidebar (e.g., auth pages)
const noSidebarPaths = ['/sign-in', '/sign-up'];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { collapsed, mobileOpen, toggleMobile } = useSidebar();
  const showSidebar = !noSidebarPaths.some(path => pathname?.startsWith(path));
  const [isDesktop, setIsDesktop] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const checkDesktop = () => setIsDesktop(window.innerWidth >= 1024);
    checkDesktop();
    window.addEventListener('resize', checkDesktop);
    return () => window.removeEventListener('resize', checkDesktop);
  }, []);

  if (!mounted) {
    return <>{children}</>;
  }

  if (!showSidebar) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen">
      {/* Mobile header with menu button */}
      <header className="lg:hidden fixed top-0 left-0 right-0 z-50 h-14 bg-surface-0/95 backdrop-blur-lg border-b border-white/5 flex items-center px-4">
        <button
          onClick={toggleMobile}
          className="p-2 -ml-2 rounded-lg hover:bg-white/5 text-slate-400"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        <span className="ml-3 font-semibold text-white">ZK Alpha Flow</span>
      </header>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div 
          className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={toggleMobile}
        />
      )}

      <Sidebar />
      
      {/* Main content - no margin on mobile, responsive margin on desktop */}
      <main 
        className="min-h-screen transition-all duration-200 pt-14 lg:pt-0"
        style={{ marginLeft: isDesktop ? (collapsed ? 72 : 240) : 0 }}
      >
        {children}
      </main>
    </div>
  );
}

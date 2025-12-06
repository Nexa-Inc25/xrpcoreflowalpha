'use client';

import { usePathname } from 'next/navigation';
import Sidebar from './Sidebar';
import { useSidebar } from '../contexts/SidebarContext';

// Pages that should NOT show the sidebar (e.g., auth pages)
const noSidebarPaths = ['/sign-in', '/sign-up'];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { collapsed } = useSidebar();
  const showSidebar = !noSidebarPaths.some(path => pathname?.startsWith(path));

  if (!showSidebar) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen">
      <Sidebar />
      {/* Main content with responsive left margin - 240px expanded, 72px collapsed */}
      <main 
        className="min-h-screen transition-all duration-200"
        style={{ marginLeft: collapsed ? 72 : 240 }}
      >
        {children}
      </main>
    </div>
  );
}

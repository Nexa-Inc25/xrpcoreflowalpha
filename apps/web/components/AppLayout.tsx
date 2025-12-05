'use client';

import { usePathname } from 'next/navigation';
import Sidebar from './Sidebar';

// Pages that should NOT show the sidebar (e.g., auth pages)
const noSidebarPaths = ['/sign-in', '/sign-up'];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const showSidebar = !noSidebarPaths.some(path => pathname?.startsWith(path));

  if (!showSidebar) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen">
      <Sidebar />
      {/* Main content with left margin for sidebar - 240px expanded */}
      <main className="ml-[240px] min-h-screen transition-all duration-200">
        {children}
      </main>
    </div>
  );
}

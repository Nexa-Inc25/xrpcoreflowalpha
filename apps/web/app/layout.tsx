import type { Metadata } from 'next';
import { ClerkProvider } from '@clerk/nextjs';
import ReactQueryProvider from '../components/ReactQueryProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'ZK Alpha Flow Dashboard',
  description: 'Live ZK dark flow tracker.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className="bg-slate-950 text-slate-100">
          <ReactQueryProvider>{children}</ReactQueryProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}

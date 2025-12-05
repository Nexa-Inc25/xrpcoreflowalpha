import type { Metadata, Viewport } from 'next';
import { ClerkProvider } from '@clerk/nextjs';
import ReactQueryProvider from '../components/ReactQueryProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'ZK Alpha Flow | Real-Time Dark Pool Detection',
  description: 'Institutional-grade ZK dark pool flow detection. See large trades 30-90 seconds before market impact. Real-time alerts for Ethereum, Solana, and XRPL.',
  keywords: ['ZK proofs', 'dark pool', 'institutional flow', 'crypto trading', 'alpha signals', 'DeFi'],
  authors: [{ name: 'ZK Alpha Flow' }],
  creator: 'ZK Alpha Flow',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://zkalphaflow.com',
    siteName: 'ZK Alpha Flow',
    title: 'ZK Alpha Flow | Real-Time Dark Pool Detection',
    description: 'See institutional ZK dark pool flow 30-90 seconds before price moves.',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'ZK Alpha Flow Dashboard',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ZK Alpha Flow',
    description: 'Real-time ZK dark pool detection for professional traders.',
    images: ['/og-image.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
  icons: {
    icon: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: '#020617',
};

const enableClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const content = (
    <html lang="en" className="antialiased">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="bg-surface-0 text-slate-100 min-h-screen">
        <ReactQueryProvider>{children}</ReactQueryProvider>
      </body>
    </html>
  );

  return enableClerk ? <ClerkProvider>{content}</ClerkProvider> : content;
}

import type { Metadata, Viewport } from 'next';
import { ClerkProvider } from '@clerk/nextjs';
import ReactQueryProvider from '../components/ReactQueryProvider';
import { SidebarProvider } from '../contexts/SidebarContext';
import AppLayout from '../components/AppLayout';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://zkalphaflow.com'),
  title: {
    default: 'ZK Alpha Flow | Real-Time Dark Pool Detection',
    template: '%s | ZK Alpha Flow',
  },
  description: 'Institutional-grade ZK dark pool flow detection. See large trades 30-90 seconds before market impact. Real-time alerts for Ethereum, Solana, and XRPL.',
  keywords: ['ZK proofs', 'dark pool', 'institutional flow', 'crypto trading', 'alpha signals', 'DeFi', 'whale tracking', 'XRP', 'Ethereum', 'Solana', 'algo fingerprinting'],
  authors: [{ name: 'ZK Alpha Flow' }],
  creator: 'ZK Alpha Flow',
  publisher: 'ZK Alpha Flow',
  formatDetection: {
    email: false,
    telephone: false,
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://zkalphaflow.com',
    siteName: 'ZK Alpha Flow',
    title: 'ZK Alpha Flow | Real-Time Dark Pool Detection',
    description: 'See institutional ZK dark pool flow 30-90 seconds before price moves. Algorithmic fingerprinting identifies Citadel, Jane Street, Jump Trading, and more.',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'ZK Alpha Flow Dashboard - Real-time dark pool detection',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ZK Alpha Flow | Dark Pool Detection',
    description: 'Real-time ZK dark pool detection. Identify institutional algo patterns before the market moves.',
    images: ['/og-image.png'],
    creator: '@zkalphaflow',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  icons: {
    icon: '/favicon.svg',
    shortcut: '/favicon.svg',
    apple: '/favicon.svg',
  },
  manifest: '/manifest.json',
  alternates: {
    canonical: 'https://zkalphaflow.com',
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
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{if(typeof window==='undefined')return;var WS=window.WebSocket;if(typeof WS!=='function')return;if(WS.__zkPatched)return;var base=${JSON.stringify(process.env.NEXT_PUBLIC_API_WS_BASE || 'wss://api.zkalphaflow.com')};var Patched=function(url,protocols){var raw=(typeof url==='string')?url:(url&&url.toString?url.toString():String(url));var next=raw;if(raw==='ws://localhost:8010/events'||raw==='ws://localhost:8010/events/'){next=String(base).replace(/\\/$/,'')+'/events';}return protocols!=null?new WS(next,protocols):new WS(next);};Patched.prototype=WS.prototype;Patched.__zkPatched=true;window.WebSocket=Patched;}catch(e){}})();`,
          }}
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="bg-surface-0 text-slate-100 min-h-screen">
        <ReactQueryProvider>
          <SidebarProvider>
            <AppLayout>{children}</AppLayout>
          </SidebarProvider>
        </ReactQueryProvider>
      </body>
    </html>
  );

  return enableClerk ? <ClerkProvider>{content}</ClerkProvider> : content;
}

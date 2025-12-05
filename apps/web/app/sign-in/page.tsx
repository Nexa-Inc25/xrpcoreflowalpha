'use client';

import dynamic from 'next/dynamic';

const SignIn = dynamic(
  () => import('@clerk/nextjs').then((mod) => mod.SignIn),
  { ssr: false }
);

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
      <SignIn routing="hash" />
    </div>
  );
}

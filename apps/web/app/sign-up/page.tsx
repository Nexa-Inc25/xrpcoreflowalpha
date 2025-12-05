'use client';

import dynamic from 'next/dynamic';

const SignUp = dynamic(
  () => import('@clerk/nextjs').then((mod) => mod.SignUp),
  { ssr: false }
);

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
      <SignUp routing="hash" />
    </div>
  );
}

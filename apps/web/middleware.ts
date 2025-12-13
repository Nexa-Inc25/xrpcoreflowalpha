import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Check if Clerk is properly configured (both keys required)
const CLERK_CONFIGURED = 
  (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || '').startsWith('pk_') &&
  (process.env.CLERK_SECRET_KEY || '').startsWith('sk_');

export default async function middleware(request: NextRequest) {
  const isDocument = request.headers.get('sec-fetch-dest') === 'document';

  // Force HTTPS in production
  if (request.headers.get('x-forwarded-proto') !== 'https' && process.env.NODE_ENV === 'production') {
    const res = NextResponse.redirect(
      `https://${request.headers.get('host')}${request.nextUrl.pathname}`,
      301
    );

    if (isDocument) {
      res.headers.set('Cache-Control', 'no-store');
    }

    return res;
  }

  // Skip auth for local dev without Clerk secrets
  if (!CLERK_CONFIGURED) {
    const res = NextResponse.next();
    if (isDocument) {
      res.headers.set('Cache-Control', 'no-store');
    }
    return res;
  }

  // Dynamic import Clerk only when configured
  try {
    const { clerkMiddleware, createRouteMatcher } = await import('@clerk/nextjs/server');
    
    const isPublicRoute = createRouteMatcher([
      '/sign-in(.*)',
      '/sign-up(.*)',
      '/',
      '/analytics(.*)',
      '/settings(.*)',
      '/flow(.*)',
    ]);

    // Create and run Clerk middleware
    const clerkHandler = clerkMiddleware((auth, req) => {
      if (!isPublicRoute(req)) {
        const { userId } = auth();
        if (!userId) {
          const signInUrl = new URL('/sign-in', req.url);
          signInUrl.searchParams.set('redirect_url', req.url);
          return NextResponse.redirect(signInUrl);
        }
      }
      return NextResponse.next();
    });

    const res = (await clerkHandler(request, {} as any)) as NextResponse;
    if (isDocument) {
      res.headers.set('Cache-Control', 'no-store');
    }
    return res;
  } catch (e) {
    // Fallback if Clerk fails
    console.warn('[Middleware] Clerk error, bypassing:', e);
    const res = NextResponse.next();
    if (isDocument) {
      res.headers.set('Cache-Control', 'no-store');
    }
    return res;
  }
}

export const config = {
  matcher: [
    // Skip Next.js internals and static files
    '/((?!_next|[^?]*\\.(?:html?|css|js|json|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
};

import { auth } from '@/lib/auth/config';
import { NextResponse } from 'next/server';

export default auth((req) => {
  const isLoggedIn   = !!req.auth;
  const isAuthRoute  = req.nextUrl.pathname.startsWith('/login');
  const isApiAuth    = req.nextUrl.pathname.startsWith('/api/auth');
  const isPublicApi  = req.nextUrl.pathname.startsWith('/api/health');

  if (isAuthRoute || isApiAuth || isPublicApi) return NextResponse.next();
  if (!isLoggedIn) {
    const loginUrl = new URL('/login', req.nextUrl.origin);
    loginUrl.searchParams.set('callbackUrl', req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
});

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};

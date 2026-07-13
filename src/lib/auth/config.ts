import type { NextAuthOptions } from 'next-auth';
import Credentials from 'next-auth/providers/credentials';
import GitHub from 'next-auth/providers/github';
import { LoginRequestSchema } from '@/lib/schemas/auth';
import type { SessionUser } from '@/lib/schemas/auth';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

// Fallback demo directory for UI metadata; auth itself is delegated to the BFF.
const DEMO_USERS: SessionUser[] = [
  { id: '1', email: 'admin@forge.dev', name: 'Admin', role: 'admin' },
  { id: '2', email: 'dev@forge.dev', name: 'Developer', role: 'developer' },
  { id: '3', email: 'viewer@forge.dev', name: 'Viewer', role: 'viewer' },
];

const githubClientId = process.env.GITHUB_CLIENT_ID || undefined;
const githubClientSecret = process.env.GITHUB_CLIENT_SECRET || undefined;

export const authOptions: NextAuthOptions = {
  providers: [
    Credentials({
      name: 'Credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const parsed = LoginRequestSchema.safeParse(credentials);
        if (!parsed.success) return null;

        const response = await fetch(`${BFF}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(parsed.data),
        });

        if (!response.ok) return null;

        const body = await response.json();
        const token = body?.token as string | undefined;
        const email = body?.user?.email as string | undefined;
        const role = body?.user?.role ?? 'developer';

        if (!token || !email) return null;

        const fallback = DEMO_USERS.find((u) => u.email === email);

        return {
          id: fallback?.id ?? email,
          email,
          name: fallback?.name ?? email.split('@')[0],
          role,
          bffToken: token,
        } as any;
      },
    }),
    ...(githubClientId && githubClientSecret
      ? [GitHub({ clientId: githubClientId, clientSecret: githubClientSecret })]
      : []),
  ],
  session: { strategy: 'jwt' },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        (token as any).role = (user as any).role ?? 'developer';
        (token as any).bffToken = (user as any).bffToken;
        token.sub = (user as any).id ?? token.sub;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as any).id = token.sub ?? '';
        (session.user as any).role = (token as any).role ?? 'developer';
        (session.user as any).bffToken = (token as any).bffToken;
      }
      return session;
    },
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
};

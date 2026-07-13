import NextAuth from 'next-auth';
import Credentials from 'next-auth/providers/credentials';
import GitHub from 'next-auth/providers/github';
import { LoginRequestSchema } from '@/lib/schemas/auth';
import type { SessionUser } from '@/lib/schemas/auth';

// Demo credentials (replace with real DB lookup in production)
const DEMO_USERS: SessionUser[] = [
  { id: '1', email: 'admin@forge.dev',     name: 'Admin',     role: 'admin' },
  { id: '2', email: 'dev@forge.dev',       name: 'Developer', role: 'developer' },
  { id: '3', email: 'viewer@forge.dev',    name: 'Viewer',    role: 'viewer' },
];

// Build the providers array conditionally so GitHub OAuth is only registered
// when real credentials are present. An empty string passed to the GitHub
// provider registers it as enabled but causes a cryptic client_id error at
// the OAuth redirect — undefined correctly disables it.
const githubClientId     = process.env.GITHUB_CLIENT_ID     || undefined;
const githubClientSecret = process.env.GITHUB_CLIENT_SECRET || undefined;

const providers = [
  Credentials({
    credentials: {
      email:    { label: 'Email',    type: 'email'    },
      password: { label: 'Password', type: 'password' },
    },
    async authorize(credentials) {
      const parsed = LoginRequestSchema.safeParse(credentials);
      if (!parsed.success) return null;
      const user = DEMO_USERS.find(u => u.email === parsed.data.email);
      if (!user) return null;
      // In production: bcrypt.compare(parsed.data.password, user.passwordHash)
      return { id: user.id, email: user.email, name: user.name,
               role: user.role } as any;
    },
  }),
  ...(githubClientId && githubClientSecret
    ? [GitHub({ clientId: githubClientId, clientSecret: githubClientSecret })]
    : []),
];

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers,
  session: { strategy: 'jwt' },
  callbacks: {
    jwt({ token, user }) {
      if (user) token.role = (user as any).role ?? 'developer';
      return token;
    },
    session({ session, token }) {
      if (session.user) (session.user as any).role = token.role;
      return session;
    },
  },
  pages: {
    signIn: '/login',
    error:  '/login',
  },
});

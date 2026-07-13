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

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        email:    { label: 'Email',    type: 'email'    },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const parsed = LoginRequestSchema.safeParse(credentials);
        if (!parsed.success) return null;
        // Demo: any password >= 8 chars works for demo users
        const user = DEMO_USERS.find(u => u.email === parsed.data.email);
        if (!user) return null;
        // In production: bcrypt.compare(parsed.data.password, user.passwordHash)
        return { id: user.id, email: user.email, name: user.name,
                 role: user.role } as any;
      },
    }),
    GitHub({
      clientId:     process.env.GITHUB_CLIENT_ID     ?? '',
      clientSecret: process.env.GITHUB_CLIENT_SECRET ?? '',
    }),
  ],
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

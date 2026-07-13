import { DefaultSession } from 'next-auth';
import { JWT as DefaultJWT } from 'next-auth/jwt';
import type { Role } from '@/lib/schemas/auth';

declare module 'next-auth' {
  interface Session {
    user: {
      id: string;
      role: Role;
      bffToken?: string;
    } & DefaultSession['user'];
  }

  interface User {
    id: string;
    role: Role;
    bffToken?: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT extends DefaultJWT {
    role?: Role;
    bffToken?: string;
    sub?: string;
  }
}

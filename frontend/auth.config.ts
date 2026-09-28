import type { NextAuthConfig } from "next-auth";

// Edge-safe: no Prisma, no bcrypt, no Node-only APIs. This is what
// middleware.ts imports (the Edge runtime can't load Prisma's engine) — it
// only needs enough config to decode the session JWT, not to authenticate
// anyone. The Credentials provider (which does need Prisma) lives in
// auth.ts and is added on top of this config there.
export default {
  pages: { signIn: "/login" },
  providers: [],
  callbacks: {
    // Persist the user's id onto the session JWT so callers (like the
    // /api/chat route) don't need a DB lookup just to know who's asking.
    async jwt({ token, user }) {
      if (user) token.id = user.id;
      return token;
    },
    async session({ session, token }) {
      if (session.user) session.user.id = token.id as string;
      return session;
    },
  },
} satisfies NextAuthConfig;

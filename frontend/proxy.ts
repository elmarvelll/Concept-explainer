import NextAuth from "next-auth";
import { NextResponse } from "next/server";

import authConfig from "@/auth.config";

// Built from the Prisma-free config rather than importing the full `auth`
// from @/auth (which pulls in Prisma) — this file only ever needs to read
// the session JWT, never to sign in.
const { auth } = NextAuth(authConfig);

const PUBLIC_PATHS = ["/login", "/signup"];

export default auth((req) => {
  const { pathname } = req.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname === p);

  if (!req.auth && !isPublic) {
    // API routes are called by fetch/axios, not page navigation — a plain
    // 401 is what the caller can actually handle, a redirect isn't.
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }

    const loginUrl = new URL("/login", req.nextUrl.origin);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (req.auth && isPublic) {
    return NextResponse.redirect(new URL("/", req.nextUrl.origin));
  }

  return NextResponse.next();
});

export const config = {
  // Run on everything except static assets, images, and NextAuth's own
  // /api/auth routes (those must stay reachable while logged out — they're
  // how login/signup actually happen). /api/signup is intentionally left
  // uncovered here too, for the same reason.
  matcher: ["/((?!api/auth|api/signup|_next/static|_next/image|favicon.ico).*)"],
};

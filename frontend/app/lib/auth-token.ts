import { SignJWT } from "jose";

const JWT_SECRET = new TextEncoder().encode(process.env.JWT_SECRET);
const JWT_ALGORITHM = "HS256";
const JWT_TTL_SECONDS = 60;

/**
 * Signs a short-lived JWT asserting who this request is for, after this app
 * has already verified the browser's NextAuth session. The Python service
 * trusts this signature (shared JWT_SECRET) instead of talking to NextAuth
 * or the user DB itself.
 */
export async function signServiceToken(user: { id: string; email: string }): Promise<string> {
  return new SignJWT({ email: user.email })
    .setProtectedHeader({ alg: JWT_ALGORITHM })
    .setSubject(user.id)
    .setIssuedAt()
    .setExpirationTime(`${JWT_TTL_SECONDS}s`)
    .sign(JWT_SECRET);
}

import { PrismaClient } from "@/app/generated/prisma";

// Next.js dev mode hot-reloads modules on every request, which would
// otherwise create a new PrismaClient (and a new DB connection pool) each
// time. Stashing it on `globalThis` survives the reload so only one is
// ever created outside of a fresh process.
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma = globalForPrisma.prisma ?? new PrismaClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}

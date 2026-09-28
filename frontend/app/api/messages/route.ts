import { NextResponse } from "next/server";

import { auth } from "@/auth";
import { prisma } from "@/app/lib/prisma";

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const messages = await prisma.message.findMany({
    where: { userId: session.user.id },
    orderBy: { createdAt: "asc" },
    select: { id: true, role: true, content: true },
  });

  return NextResponse.json({ messages });
}

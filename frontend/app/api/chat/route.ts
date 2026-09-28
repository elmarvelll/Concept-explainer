import axios from "axios";
import { NextResponse } from "next/server";

import { auth } from "@/auth";
import { signServiceToken } from "@/app/lib/auth-token";

const PYTHON_API_URL = process.env.PYTHON_API_URL || "http://localhost:8000/api";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const body = await req.json().catch(() => null);
  const messages = body?.messages;
  const lastMessage = Array.isArray(messages) ? messages[messages.length - 1] : null;
  if (!lastMessage || lastMessage.role !== "user" || typeof lastMessage.content !== "string") {
    return NextResponse.json({ error: "messages must end with a user message" }, { status: 400 });
  }

  const token = await signServiceToken({ id: session.user.id, email: session.user.email! });

  try {
    // The Python service owns conversation history now (it reads/writes
    // Message rows itself, see backend/history.py) — only the new message
    // needs to be sent, not the whole conversation.
    const { data } = await axios.post(
      `${PYTHON_API_URL}/chat`,
      { message: lastMessage.content },
      { headers: { Authorization: `Bearer ${token}` } },
    );
    return NextResponse.json(data);
  } catch (err) {
    if (axios.isAxiosError(err) && err.response) {
      return NextResponse.json(err.response.data, { status: err.response.status });
    }
    return NextResponse.json({ error: "The AI service is unreachable" }, { status: 502 });
  }
}

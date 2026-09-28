import axios from "axios";

// Same-origin: the browser only ever talks to this Next.js app. This route
// verifies the session and forwards to the Python service itself — see
// app/api/chat/route.ts.
const client = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type StoredMessage = ChatMessage & { id: string };

export async function getMessages(): Promise<StoredMessage[]> {
  const { data } = await client.get<{ messages: { id: string; role: "USER" | "ASSISTANT"; content: string }[] }>(
    "/messages",
  );
  return data.messages.map((m) => ({ id: m.id, role: m.role === "USER" ? "user" : "assistant", content: m.content }));
}

export async function sendChat(messages: ChatMessage[]): Promise<string> {
  try {
    const { data } = await client.post<{ reply: string }>("/chat", { messages });
    return data.reply;
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const detail = err.response?.data?.detail || err.response?.data?.error;
      throw new Error(detail || `Request failed: ${err.response?.status ?? "network error"}`);
    }
    throw err;
  }
}

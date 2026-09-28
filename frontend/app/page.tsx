"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessage, getMessages, sendChat } from "./lib/api";

type DisplayMessage = ChatMessage & { id: number | string };

export default function Home() {
  const { data: session, status } = useSession();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (status !== "authenticated") return;

    getMessages()
      .then((history) => setMessages(history))
      .catch(() => {
        // History just starts empty if this fails — not worth an error banner.
      })
      .finally(() => setLoadingHistory(false));
  }, [status]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, sending]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const concept = draft.trim();
    if (!concept || sending) return;

    setDraft("");
    const userMsg: DisplayMessage = { id: Date.now(), role: "user", content: concept };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setSending(true);

    try {
      const reply = await sendChat(nextMessages.map(({ role, content }) => ({ role, content })));
      setMessages((prev) => [...prev, { id: Date.now() + 1, role: "assistant", content: reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: "assistant", content: "Sorry, I ran into an error explaining that." },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col flex-1 items-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-1 w-full max-w-2xl flex-col px-4 py-8 sm:px-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
              Concept Explainer
            </h1>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Ask about any concept and get a clear, plain-language explanation.
            </p>
          </div>
          {session?.user && (
            <div className="flex shrink-0 flex-col items-end gap-1 pt-1">
              <span className="text-xs text-zinc-500 dark:text-zinc-500">{session.user.email}</span>
              <button
                type="button"
                onClick={() => signOut({ callbackUrl: "/login" })}
                className="text-xs font-medium text-zinc-600 underline hover:text-black dark:text-zinc-400 dark:hover:text-zinc-50"
              >
                Log out
              </button>
            </div>
          )}
        </div>

        <div className="mt-6 flex-1 space-y-4 overflow-y-auto">
          {!loadingHistory && messages.length === 0 && (
            <p className="text-sm text-zinc-500 dark:text-zinc-500">
              Try &ldquo;What is recursion?&rdquo; or &ldquo;Explain quantum entanglement&rdquo;.
            </p>
          )}
          {messages.map((m) =>
            m.role === "user" ? (
              <div
                key={m.id}
                className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-2xl bg-black px-4 py-2.5 text-sm leading-6 text-white dark:bg-zinc-50 dark:text-black"
              >
                {m.content}
              </div>
            ) : ( 
              // Explanatory replies are rendered like a note on a board, not a
              // chat bubble: full width, no background/border, just typeset
              // text — that's what makes it read as an explanation rather than
              // a search result.
              <div
                key={m.id}
                className="prose prose-zinc max-w-none text-[15px] leading-7 dark:prose-invert prose-p:my-4 prose-headings:mt-6 prose-headings:mb-3 prose-strong:font-semibold prose-ul:my-4 prose-li:my-1"
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              </div>
            ),
          )}
          {sending && <p className="text-sm text-zinc-500 dark:text-zinc-400">Thinking…</p>}
          <div ref={messagesEndRef} />
        </div>

        <form className="mt-6 flex items-end gap-2" onSubmit={handleSubmit}>
          <textarea
            className="flex-1 resize-none rounded-xl border border-zinc-300 bg-white px-4 py-3 text-sm text-black outline-none focus:border-black dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50 dark:focus:border-zinc-400"
            placeholder="Type a concept to explain…"
            rows={2}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={sending}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <button
            type="submit"
            disabled={sending || !draft.trim()}
            className="h-11 rounded-xl bg-black px-5 text-sm font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-40 dark:bg-zinc-50 dark:text-black dark:hover:bg-zinc-300"
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
}

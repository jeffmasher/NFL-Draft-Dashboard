"use client";

import { useChat } from "@ai-sdk/react";
import { useEffect, useRef, useState } from "react";

export function Chat() {
  const { messages, sendMessage, status, error } = useChat({
    onError: (err) => {
      console.error("Chat error:", err);
    },
  });
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const isLoading = status === "streaming" || status === "submitted";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = (text?: string) => {
    const msg = text ?? input;
    if (!msg.trim() || isLoading) return;
    sendMessage({ text: msg });
    setInput("");
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submit();
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-4 font-heading text-4xl text-gold/30">?</div>
            <h2 className="mb-2 font-heading text-xl font-bold text-text">
              ASK ABOUT THE SAINTS
            </h2>
            <p className="max-w-md font-body text-sm text-dim">
              Ask any question about Saints history, stats, players, or games.
              The AI will query the database for accurate answers.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {[
                "When did the Saints win the Super Bowl?",
                "Who has the most career passing yards?",
                "Show me all 1,000-yard receiving seasons",
                "Saints record in 2017",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => submit(q)}
                  className="rounded-lg border border-border bg-panel px-3 py-2 font-body text-xs text-dim transition-colors hover:border-gold/30 hover:text-text"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => {
          // Extract text from parts
          const textParts = m.parts
            .filter((p): p is { type: "text"; text: string } => p.type === "text")
            .map((p) => p.text)
            .join("");

          // For user messages, also check if parts is empty but we can fall back
          const displayText = textParts || "";

          // Skip assistant messages that have no text yet (e.g. tool-only steps)
          if (!displayText && m.role === "assistant") return null;
          if (!displayText && m.role === "user") return null;

          return (
            <div
              key={m.id}
              className={`mb-4 ${m.role === "user" ? "flex justify-end" : ""}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-4 py-3 ${
                  m.role === "user"
                    ? "bg-gold/15 text-text"
                    : "bg-panel text-text"
                }`}
              >
                <div className="mb-1 font-heading text-[10px] uppercase tracking-wider text-dim">
                  {m.role === "user" ? "You" : "Saints AI"}
                </div>
                <div className="whitespace-pre-wrap font-body text-sm leading-relaxed">
                  {displayText}
                </div>
              </div>
            </div>
          );
        })}

        {isLoading && !messages.some(
          (m) =>
            m.role === "assistant" &&
            m.parts.some((p) => p.type === "text" && "text" in p && (p as { type: "text"; text: string }).text)
        ) && (
          <div className="mb-4">
            <div className="max-w-[85%] rounded-lg bg-panel px-4 py-3">
              <div className="mb-1 font-heading text-[10px] uppercase tracking-wider text-dim">
                Saints AI
              </div>
              <div className="flex items-center gap-1">
                <span className="h-2 w-2 animate-bounce rounded-full bg-gold/50" style={{ animationDelay: "0ms" }} />
                <span className="h-2 w-2 animate-bounce rounded-full bg-gold/50" style={{ animationDelay: "150ms" }} />
                <span className="h-2 w-2 animate-bounce rounded-full bg-gold/50" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-lg border border-rec/30 bg-rec/10 px-4 py-3 font-body text-sm text-rec">
            Error: {error.message}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border bg-smoke p-4">
        <form onSubmit={handleSubmit} className="mx-auto flex max-w-3xl gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about Saints history, stats, players..."
            className="flex-1 rounded-lg border border-border bg-panel px-4 py-3 font-body text-sm text-text placeholder:text-muted focus:border-gold/50 focus:outline-none"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="rounded-lg bg-gold/20 px-5 py-3 font-heading text-sm font-bold text-gold transition-colors hover:bg-gold/30 disabled:opacity-50"
          >
            ASK
          </button>
        </form>
      </div>
    </div>
  );
}

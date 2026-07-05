"use client";

import { useEffect, useRef } from "react";

import type { ChatMessage } from "@/lib/api/types";
import { MessageBubble } from "./message-bubble";
import { TypingIndicator } from "./typing-indicator";

export function MessageList({
  messages,
  isTyping,
}: {
  messages: ChatMessage[];
  isTyping: boolean;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, isTyping]);

  return (
    <div
      ref={scrollRef}
      className="scrollbar-thin flex-1 overflow-y-auto px-4 py-4"
    >
      <div className="mx-auto flex max-w-2xl flex-col gap-3">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {isTyping && <TypingIndicator />}
      </div>
    </div>
  );
}

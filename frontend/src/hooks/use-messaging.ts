"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api/client";
import type { ChatMessage, IncomingMessage, StreamEvent } from "@/lib/api/types";

function clientId() {
  return `cmsg_${Math.random().toString(36).slice(2, 12)}`;
}

function nowIso() {
  return new Date().toISOString();
}

export function useMessaging() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [ready, setReady] = useState(false);
  const sessionIdRef = useRef<string | null>(null);

  const applyEvent = useCallback((event: StreamEvent) => {
    switch (event.type) {
      case "generation.started":
        setIsTyping(true);
        break;
      case "message.completed":
      case "generation.cancelled":
        setIsTyping(false);
        break;
      default:
        break;
    }

    setMessages((prev) => {
      switch (event.type) {
        case "user.message": {
          const existing = prev.find(
            (m) => m.client_message_id === event.client_message_id
          );
          if (existing) {
            return prev.map((m) =>
              m.client_message_id === event.client_message_id
                ? { ...m, id: event.message_id, status: "sent" }
                : m
            );
          }
          return [
            ...prev,
            {
              id: event.message_id,
              client_message_id: event.client_message_id,
              role: "user",
              content: event.content,
              status: "sent",
              createdAt: event.created_at,
            },
          ];
        }
        case "message.completed":
          if (
            prev.some((m) => m.generation_id === event.generation_id)
          ) {
            return prev.map((m) =>
              m.generation_id === event.generation_id
                ? { ...m, content: event.content, status: "completed" }
                : m
            );
          }
          return [
            ...prev,
            {
              id: event.message_id,
              client_message_id: event.generation_id,
              role: "assistant",
              content: event.content,
              status: "completed",
              createdAt: event.finished_at,
              generation_id: event.generation_id,
            },
          ];
        case "generation.cancelled":
          return prev
            .map((m) =>
              m.generation_id === event.generation_id
                ? {
                    ...m,
                    content: event.partial ?? m.content,
                    status: "cancelled" as const,
                  }
                : m
            )
            .filter(
              (m) =>
                !(
                  m.generation_id === event.generation_id &&
                  m.content.length === 0
                )
            );
        default:
          return prev;
      }
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    let unsub: (() => void) | undefined;

    (async () => {
      const session = await api.createSession({});
      if (cancelled) return;
      sessionIdRef.current = session.session_id;
      setReady(true);
      unsub = api.streamMessages(session.session_id, applyEvent);
    })();

    return () => {
      cancelled = true;
      unsub?.();
    };
  }, [applyEvent]);

  const sendMessage = useCallback((content: string) => {
    const trimmed = content.trim();
    const sessionId = sessionIdRef.current;
    if (!trimmed || !sessionId) return;

    const incoming: IncomingMessage = {
      role: "user",
      content: trimmed,
      client_message_id: clientId(),
      timestamp: nowIso(),
    };

    setIsTyping(true);

    setMessages((prev) => [
      ...prev,
      {
        id: incoming.client_message_id,
        client_message_id: incoming.client_message_id,
        role: "user",
        content: trimmed,
        status: "sending",
        createdAt: incoming.timestamp,
      },
    ]);

    void api.sendMessage({
      session_id: sessionId,
      message: incoming,
      interrupt_previous: true,
    });
  }, []);

  return { messages, ready, isTyping, sendMessage };
};

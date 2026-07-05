/**
 * Messaging API client.
 *
 * Implements the operations from the OpenAPI spec against a pluggable
 * transport. When `NEXT_PUBLIC_API_BASE_URL` is configured it talks real HTTP +
 * SSE; otherwise it falls back to an in-browser mock so the UI is fully
 * functional with zero backend.
 */

import { mockServer } from "./mock-server";
import type {
  CancelGenerationRequest,
  CreateSessionRequest,
  MessageAccepted,
  SendBatchRequest,
  SendMessageRequest,
  Session,
  StreamEvent,
} from "./types";

export interface MessagingClient {
  createSession(body: CreateSessionRequest): Promise<Session>;
  getSession(sessionId: string): Promise<Session>;
  sendMessage(body: SendMessageRequest): Promise<MessageAccepted>;
  sendBatch(body: SendBatchRequest): Promise<MessageAccepted>;
  cancelGeneration(body: CancelGenerationRequest): Promise<void>;
  /** Subscribe to the SSE stream for a session. Returns an unsubscribe fn. */
  streamMessages(
    sessionId: string,
    onEvent: (event: StreamEvent) => void,
    options?: { cursor?: string; signal?: AbortSignal }
  ): () => void;
}

/* ------------------------------- HTTP client ------------------------------ */

class HttpMessagingClient implements MessagingClient {
  constructor(private baseUrl: string) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!res.ok) {
      throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`);
    }
    return (res.status === 204 ? undefined : await res.json()) as T;
  }

  createSession(body: CreateSessionRequest) {
    return this.request<Session>("/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  getSession(sessionId: string) {
    return this.request<Session>(`/sessions/${sessionId}`);
  }

  sendMessage(body: SendMessageRequest) {
    return this.request<MessageAccepted>("/messages", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  sendBatch(body: SendBatchRequest) {
    return this.request<MessageAccepted>("/messages/batch", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async cancelGeneration(body: CancelGenerationRequest) {
    await this.request<void>("/messages/cancel", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  streamMessages(
    sessionId: string,
    onEvent: (event: StreamEvent) => void,
    options?: { cursor?: string; signal?: AbortSignal }
  ) {
    const url = new URL(`${this.baseUrl}/messages/stream`);
    url.searchParams.set("session_id", sessionId);
    if (options?.cursor) url.searchParams.set("cursor", options.cursor);

    const source = new EventSource(url.toString());
    source.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data) as StreamEvent);
      } catch {
        /* ignore malformed frames */
      }
    };
    options?.signal?.addEventListener("abort", () => source.close());
    return () => source.close();
  }
}

/* ------------------------------- Mock client ------------------------------ */

class MockMessagingClient implements MessagingClient {
  private async latency<T>(value: T): Promise<T> {
    await new Promise((r) => setTimeout(r, 90 + Math.random() * 130));
    return value;
  }

  createSession(body: CreateSessionRequest) {
    return this.latency(mockServer.createSession(body));
  }

  getSession(sessionId: string) {
    return this.latency(mockServer.getSession(sessionId));
  }

  sendMessage(body: SendMessageRequest) {
    return this.latency(mockServer.sendMessage(body));
  }

  sendBatch(body: SendBatchRequest) {
    return this.latency(mockServer.sendBatch(body));
  }

  async cancelGeneration(body: CancelGenerationRequest) {
    mockServer.cancelGeneration(body);
    await this.latency(undefined);
  }

  streamMessages(
    sessionId: string,
    onEvent: (event: StreamEvent) => void,
    options?: { cursor?: string; signal?: AbortSignal }
  ) {
    const unsub = mockServer.subscribe(sessionId, onEvent, options?.cursor);
    options?.signal?.addEventListener("abort", unsub);
    return unsub;
  }
}

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

export const api: MessagingClient = baseUrl
  ? new HttpMessagingClient(baseUrl)
  : new MockMessagingClient();

export const isMockMode = !baseUrl;

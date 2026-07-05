/**
 * In-browser mock of the Messaging LLM Orchestration API.
 *
 * It faithfully implements the interesting server-side semantics described in
 * the OpenAPI spec:
 *   - streaming assistant output over an SSE-like channel
 *   - "sending a new message invalidates any in-flight generation"
 *   - explicit cancellation (/messages/cancel)
 *   - burst/debounced input coalescing (/messages/batch)
 *   - resumable streams via an opaque `cursor`
 */

import type {
  CancelGenerationRequest,
  CreateSessionRequest,
  IncomingMessage,
  MessageAccepted,
  SendBatchRequest,
  SendMessageRequest,
  Session,
  StreamEvent,
} from "./types";

type Subscriber = (event: StreamEvent) => void;

interface Generation {
  generation_id: string;
  message_id: string;
  timer: ReturnType<typeof setInterval> | null;
  partial: string;
}

const CANNED_REPLIES: string[] = [
  "Absolutely — here's how I'd think about it. First, we scope the problem, then we sketch a couple of approaches and weigh the tradeoffs before committing to one. Want me to go deeper on any part?",
  "Great question. The short version: it depends on your latency budget. If you need sub-second responses, stream tokens as they're generated and coalesce rapid user input so you don't thrash the model.",
  "Got it. I'd start by cancelling any in-flight generation the moment new input arrives, then debounce the burst into a single prompt. That keeps the conversation feeling snappy and coherent.",
  "Sure thing! Think of it like texting a friend who types fast — you interrupt yourself constantly, and the other side should gracefully catch up rather than replying to every half-finished thought.",
  "Happy to help. Here's a tight plan: 1) capture intent, 2) stream a draft, 3) let the user interrupt at any time, 4) reconcile state from the cursor. Simple, resilient, and fast.",
  "Totally. The elegant part of this design is that interruption is a feature, not an error. Every new message just supersedes the last generation and we pick up cleanly from there.",
];

function id(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

class MockMessagingServer {
  private sessions = new Map<string, Session>();
  private generations = new Map<string, Generation>(); // by session_id
  private log = new Map<string, StreamEvent[]>(); // event log by session_id
  private subscribers = new Map<string, Set<Subscriber>>();
  private cursorSeq = new Map<string, number>();

  /* ----------------------------- infrastructure ---------------------------- */

  private nextCursor(sessionId: string): string {
    const n = (this.cursorSeq.get(sessionId) ?? 0) + 1;
    this.cursorSeq.set(sessionId, n);
    return `c${n.toString().padStart(6, "0")}`;
  }

  private emit(sessionId: string, event: StreamEvent) {
    const events = this.log.get(sessionId) ?? [];
    events.push(event);
    this.log.set(sessionId, events);
    const subs = this.subscribers.get(sessionId);
    if (subs) for (const s of subs) s(event);
  }

  subscribe(
    sessionId: string,
    cb: Subscriber,
    afterCursor?: string
  ): () => void {
    // Replay any events the client missed (resume-by-cursor).
    const events = this.log.get(sessionId) ?? [];
    const start = afterCursor
      ? events.findIndex((e) => e.cursor === afterCursor) + 1
      : 0;
    for (const e of events.slice(start)) cb(e);

    let set = this.subscribers.get(sessionId);
    if (!set) {
      set = new Set();
      this.subscribers.set(sessionId, set);
    }
    set.add(cb);
    return () => set!.delete(cb);
  }

  /* ------------------------------- endpoints ------------------------------- */

  createSession(body: CreateSessionRequest): Session {
    const session: Session = {
      session_id: id("sess"),
      user_id: body.user_id ?? id("user"),
      active_generation_id: null,
      last_message_at: nowIso(),
    };
    this.sessions.set(session.session_id, session);
    return session;
  }

  getSession(sessionId: string): Session {
    const s = this.sessions.get(sessionId);
    if (!s) throw new Error(`Session not found: ${sessionId}`);
    return { ...s };
  }

  sendMessage(body: SendMessageRequest): MessageAccepted {
    const session = this.sessions.get(body.session_id);
    if (!session) throw new Error(`Session not found: ${body.session_id}`);

    const interrupt = body.interrupt_previous ?? true;
    const replacing = interrupt && !!this.generations.get(body.session_id);
    if (interrupt) this.stopGeneration(body.session_id, "superseded");

    this.recordUserMessage(body.session_id, body.message);
    const generation_id = this.startGeneration(body.session_id, [
      body.message.content,
    ]);

    return {
      session_id: body.session_id,
      message_id: body.message.client_message_id,
      generation_id,
      status: replacing ? "replacing_previous" : "queued",
    };
  }

  sendBatch(body: SendBatchRequest): MessageAccepted {
    const session = this.sessions.get(body.session_id);
    if (!session) throw new Error(`Session not found: ${body.session_id}`);

    // Coalesce burst input: cancel in-flight work, record each message, then
    // start a single generation over the combined content.
    this.stopGeneration(body.session_id, "superseded");
    for (const m of body.messages) this.recordUserMessage(body.session_id, m);

    const generation_id = this.startGeneration(
      body.session_id,
      body.messages.map((m) => m.content)
    );

    return {
      session_id: body.session_id,
      message_id: body.messages[body.messages.length - 1]?.client_message_id,
      generation_id,
      status: "replacing_previous",
    };
  }

  cancelGeneration(body: CancelGenerationRequest): { cancelled: boolean } {
    const had = !!this.generations.get(body.session_id);
    this.stopGeneration(body.session_id, body.reason ?? "user_cancelled");
    return { cancelled: had };
  }

  /* ------------------------------- internals ------------------------------- */

  private recordUserMessage(sessionId: string, message: IncomingMessage) {
    const session = this.sessions.get(sessionId)!;
    session.last_message_at = nowIso();
    this.emit(sessionId, {
      type: "user.message",
      cursor: this.nextCursor(sessionId),
      session_id: sessionId,
      message_id: id("msg"),
      client_message_id: message.client_message_id,
      content: message.content,
      created_at: nowIso(),
    });
  }

  private startGeneration(sessionId: string, prompts: string[]): string {
    const session = this.sessions.get(sessionId)!;
    const generation_id = id("gen");
    const message_id = id("msg");
    session.active_generation_id = generation_id;

    this.emit(sessionId, {
      type: "generation.started",
      cursor: this.nextCursor(sessionId),
      session_id: sessionId,
      generation_id,
      message_id,
      created_at: nowIso(),
    });
    this.emitSessionUpdate(sessionId);

    const reply = this.composeReply(prompts);

    const gen: Generation = {
      generation_id,
      message_id,
      timer: null,
      partial: reply,
    };
    this.generations.set(sessionId, gen);

    const thinkMs = 600 + Math.random() * 500;
    gen.timer = setTimeout(() => {
      this.finishGeneration(sessionId);
    }, thinkMs) as unknown as ReturnType<typeof setInterval>;

    return generation_id;
  }

  private finishGeneration(sessionId: string) {
    const gen = this.generations.get(sessionId);
    if (!gen) return;
    if (gen.timer) clearInterval(gen.timer);
    this.generations.delete(sessionId);

    const session = this.sessions.get(sessionId)!;
    session.active_generation_id = null;
    session.last_message_at = nowIso();

    this.emit(sessionId, {
      type: "message.completed",
      cursor: this.nextCursor(sessionId),
      session_id: sessionId,
      generation_id: gen.generation_id,
      message_id: gen.message_id,
      content: gen.partial,
      finished_at: nowIso(),
    });
    this.emitSessionUpdate(sessionId);
  }

  private stopGeneration(sessionId: string, reason: string) {
    const gen = this.generations.get(sessionId);
    if (!gen) return;
    if (gen.timer) {
      clearInterval(gen.timer);
      clearTimeout(gen.timer as unknown as ReturnType<typeof setTimeout>);
    }
    this.generations.delete(sessionId);

    const session = this.sessions.get(sessionId)!;
    session.active_generation_id = null;

    this.emit(sessionId, {
      type: "generation.cancelled",
      cursor: this.nextCursor(sessionId),
      session_id: sessionId,
      generation_id: gen.generation_id,
      message_id: gen.message_id,
      reason,
      partial: gen.partial,
    });
    this.emitSessionUpdate(sessionId);
  }

  private emitSessionUpdate(sessionId: string) {
    const session = this.sessions.get(sessionId)!;
    this.emit(sessionId, {
      type: "session.updated",
      cursor: this.nextCursor(sessionId),
      session: { ...session },
    });
  }

  private composeReply(prompts: string[]): string {
    const joined = prompts.join(" ").toLowerCase();
    if (prompts.length > 1) {
      return `I caught all ${prompts.length} of those in one go — no need to wait between texts. ${pick(
        CANNED_REPLIES
      )}`;
    }
    if (/\bhello\b|\bhi\b|\bhey\b/.test(joined)) {
      return "Hey! 👋 Great to hear from you. What are we building today?";
    }
    if (joined.includes("?")) {
      return pick(CANNED_REPLIES);
    }
    return pick(CANNED_REPLIES);
  }
}

/** Singleton mock server shared across the app. */
export const mockServer = new MockMessagingServer();

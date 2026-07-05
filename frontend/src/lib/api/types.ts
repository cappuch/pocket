/**
 * Types generated from the Messaging LLM Orchestration API (OpenAPI 3.1.0).
 * These mirror the `components.schemas` section of the spec.
 */

export interface Session {
  session_id: string;
  user_id?: string;
  /** Present while the assistant is producing output. */
  active_generation_id?: string | null;
  last_message_at?: string; // ISO date-time
}

export interface IncomingMessage {
  role: "user";
  content: string;
  client_message_id: string;
  timestamp: string; // ISO date-time
}

export interface SendMessageRequest {
  session_id: string;
  message: IncomingMessage;
  /** Cancel any in-flight generation for this session. Defaults to true. */
  interrupt_previous?: boolean;
}

export type MessageAcceptedStatus = "queued" | "replacing_previous";

export interface MessageAccepted {
  session_id: string;
  message_id: string;
  generation_id: string;
  status: MessageAcceptedStatus;
}

export interface CreateSessionRequest {
  user_id?: string;
  metadata?: Record<string, unknown>;
}

export interface CancelGenerationRequest {
  session_id: string;
  reason?: string;
}

export interface SendBatchRequest {
  session_id: string;
  messages: IncomingMessage[];
}

/* -------------------------------------------------------------------------- */
/* Server-Sent Event payloads (GET /messages/stream)                          */
/* The spec types the stream as an opaque `string`; below is the concrete     */
/* event contract this client and mock server agree on.                       */
/* -------------------------------------------------------------------------- */

export type StreamEvent =
  | GenerationStartedEvent
  | MessageDeltaEvent
  | MessageCompletedEvent
  | GenerationCancelledEvent
  | UserMessageEvent
  | SessionUpdatedEvent
  | HeartbeatEvent;

export interface GenerationStartedEvent {
  type: "generation.started";
  cursor: string;
  session_id: string;
  generation_id: string;
  message_id: string;
  created_at: string;
}

export interface MessageDeltaEvent {
  type: "message.delta";
  cursor: string;
  session_id: string;
  generation_id: string;
  message_id: string;
  delta: string;
}

export interface MessageCompletedEvent {
  type: "message.completed";
  cursor: string;
  session_id: string;
  generation_id: string;
  message_id: string;
  content: string;
  finished_at: string;
}

export interface GenerationCancelledEvent {
  type: "generation.cancelled";
  cursor: string;
  session_id: string;
  generation_id: string;
  message_id: string;
  reason: string;
  /** The partial text produced before cancellation, if any. */
  partial?: string;
}

export interface UserMessageEvent {
  type: "user.message";
  cursor: string;
  session_id: string;
  message_id: string;
  client_message_id: string;
  content: string;
  created_at: string;
}

export interface SessionUpdatedEvent {
  type: "session.updated";
  cursor: string;
  session: Session;
}

export interface HeartbeatEvent {
  type: "heartbeat";
  cursor: string;
  ts: string;
}

/* -------------------------------------------------------------------------- */
/* Client-side view model                                                      */
/* -------------------------------------------------------------------------- */

export type ChatRole = "user" | "assistant";

export type MessageStatus =
  | "sending"
  | "sent"
  | "delivered"
  | "streaming"
  | "completed"
  | "cancelled"
  | "failed";

export interface ChatMessage {
  id: string;
  client_message_id: string;
  role: ChatRole;
  content: string;
  status: MessageStatus;
  createdAt: string;
  generation_id?: string;
}

export interface Conversation {
  key: string;
  session: Session;
  title: string;
  subtitle: string;
  avatarColor: string;
  messages: ChatMessage[];
  /** True while the assistant is generating but hasn't streamed text yet. */
  isTyping: boolean;
}

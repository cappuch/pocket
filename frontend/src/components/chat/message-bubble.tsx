import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/lib/api/types";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-[22px] px-[18px] py-[11px] text-[17px] leading-[1.35] tracking-[-0.022em]",
          isUser
            ? "rounded-br-[6px] bg-bubble-sent text-bubble-sent-foreground"
            : "rounded-bl-[6px] bg-bubble-received text-bubble-received-foreground"
        )}
      >
        {message.content}
      </div>
    </div>
  );
}

"use client";

import { Loader2 } from "lucide-react";

import { useMessaging } from "@/hooks/use-messaging";
import { MessageList } from "@/components/chat/message-list";
import { Composer } from "@/components/chat/composer";

export default function Home() {
  const { messages, ready, isTyping, sendMessage } = useMessaging();

  return (
    <main className="mx-auto flex h-[100dvh] w-full max-w-2xl flex-col bg-chat-panel md:h-screen">
      {!ready ? (
        <div className="flex flex-1 items-center justify-center text-muted-foreground">
          <Loader2 className="mr-2 size-5 animate-spin" />
          Loading…
        </div>
      ) : (
        <>
          <MessageList messages={messages} isTyping={isTyping} />
          <Composer onSend={sendMessage} />
        </>
      )}
    </main>
  );
}

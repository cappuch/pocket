"use client";

import { useState } from "react";
import { ArrowUp } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function Composer({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");

  const submit = () => {
    if (!value.trim()) return;
    onSend(value);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const canSend = value.trim().length > 0;

  return (
    <div className="border-t px-4 py-3">
      <div className="mx-auto flex max-w-2xl items-end gap-2">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled}
          placeholder="Message"
          className="scrollbar-thin max-h-36 min-h-11 flex-1 resize-none rounded-3xl border bg-background px-5 py-3 text-[17px] leading-[1.35] tracking-[-0.022em] outline-none focus:border-primary/60 disabled:opacity-50"
        />
        <Button
          size="icon"
          onClick={submit}
          disabled={!canSend || disabled}
          aria-label="Send"
          className={cn(
            "size-11 shrink-0 rounded-full",
            canSend
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground"
          )}
        >
          <ArrowUp className="size-4" />
        </Button>
      </div>
    </div>
  );
}

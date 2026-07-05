export function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-[5px] rounded-[22px] rounded-bl-[6px] bg-bubble-received px-[18px] py-[14px]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="typing-dot size-[8px] rounded-full bg-bubble-received-foreground"
            style={{ animationDelay: `${i * 0.22}s` }}
          />
        ))}
      </div>
    </div>
  );
}

interface TranscriptViewerProps {
  transcript: string;
}

const AGENT_ROLES = new Set(["agent", "emma", "assistant"]);

export function TranscriptViewer({ transcript }: TranscriptViewerProps) {
  if (!transcript) {
    return (
      <p className="text-muted-foreground text-sm">
        No transcript yet. Arrives once the post-call webhook fires.
      </p>
    );
  }

  const turns = transcript
    .split("\n")
    .filter((line) => line.trim().length > 0);

  return (
    <div className="space-y-2">
      {turns.map((line, i) => {
        const match = /^(\w+):\s*(.*)$/.exec(line);
        const role = (match?.[1] ?? "system").toLowerCase();
        const text = match?.[2] ?? line;
        const isAgent = AGENT_ROLES.has(role);
        return (
          <div
            key={i}
            className={`flex ${isAgent ? "justify-start" : "justify-end"}`}
          >
            <div
              className={`max-w-[80%] rounded-md px-3 py-2 text-sm ${
                isAgent
                  ? "bg-muted text-foreground"
                  : "bg-primary text-primary-foreground"
              }`}
            >
              <div className="mb-0.5 text-xs capitalize opacity-60">{role}</div>
              <div className="whitespace-pre-wrap">{text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

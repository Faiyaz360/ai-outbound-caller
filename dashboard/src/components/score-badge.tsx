import { Badge } from "@/components/ui/badge";
import type { Tier } from "@/lib/types";

interface ScoreBadgeProps {
  tier: Tier;
  score?: number;
  className?: string;
}

/**
 * Tier badge that encodes the lead temperature THREE ways:
 *   - shape (glyph) so it's distinguishable for colour-blind users
 *   - text label so a screen reader announces it
 *   - colour for fast visual scan
 *
 * Per UX review: never rely on colour alone.
 */
const STYLES: Record<
  Tier,
  { glyph: string; label: string; classes: string }
> = {
  HOT: {
    glyph: "●",
    label: "Hot",
    classes:
      "border-rose-500/40 bg-rose-500/15 text-rose-700 dark:text-rose-300",
  },
  WARM: {
    glyph: "◐",
    label: "Warm",
    classes:
      "border-amber-500/40 bg-amber-500/15 text-amber-700 dark:text-amber-300",
  },
  COLD: {
    glyph: "○",
    label: "Cold",
    classes:
      "border-sky-500/40 bg-sky-500/15 text-sky-700 dark:text-sky-300",
  },
  DEAD: {
    glyph: "✕",
    label: "Dead",
    classes:
      "border-zinc-500/40 bg-zinc-500/10 text-muted-foreground line-through",
  },
};

export function ScoreBadge({ tier, score, className }: ScoreBadgeProps) {
  const s = STYLES[tier];
  const ariaLabel =
    score !== undefined ? `Lead tier ${s.label}, score ${score}` : `Lead tier ${s.label}`;
  return (
    <Badge
      variant="outline"
      className={`gap-1.5 font-mono text-xs ${s.classes} ${className ?? ""}`}
      aria-label={ariaLabel}
    >
      <span aria-hidden>{s.glyph}</span>
      <span>{s.label}</span>
      {score !== undefined && (
        <span className="font-semibold opacity-70">· {score}</span>
      )}
    </Badge>
  );
}

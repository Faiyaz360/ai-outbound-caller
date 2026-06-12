import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
}

export function MetricCard({ label, value, hint }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-muted-foreground text-xs uppercase tracking-wide">
          {label}
        </div>
        <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
        {hint && (
          <div className="text-muted-foreground mt-1 text-xs">{hint}</div>
        )}
      </CardContent>
    </Card>
  );
}

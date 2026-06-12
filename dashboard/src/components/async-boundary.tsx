"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

interface AsyncBoundaryProps<T> {
  data: T | undefined;
  isLoading: boolean;
  error: unknown;
  empty?: ReactNode;
  isEmpty?: (data: T) => boolean;
  children: (data: T) => ReactNode;
}

/**
 * Renders one of four states from an SWR/use-query-style result so every
 * page handles loading, error and empty cases consistently.
 */
export function AsyncBoundary<T>({
  data,
  isLoading,
  error,
  empty,
  isEmpty,
  children,
}: AsyncBoundaryProps<T>) {
  if (error) {
    return (
      <div className="text-destructive border-destructive/30 bg-destructive/5 flex items-center gap-2 rounded-md border p-4 text-sm">
        <AlertCircle className="size-4" />
        <span>
          Failed to load. Is the FastAPI server running on{" "}
          <code className="font-mono">:8000</code>?
        </span>
      </div>
    );
  }
  if (isLoading || data === undefined) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 p-4 text-sm">
        <Loader2 className="size-4 animate-spin" />
        Loading…
      </div>
    );
  }
  if (isEmpty?.(data)) {
    return (
      <div className="text-muted-foreground rounded-md border border-dashed p-8 text-center text-sm">
        {empty ?? "Nothing here yet."}
      </div>
    );
  }
  return <>{children(data)}</>;
}

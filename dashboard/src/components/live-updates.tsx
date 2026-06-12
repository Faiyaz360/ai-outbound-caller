"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

const WATCHED_EVENTS = ["call_updated", "booking_created"] as const;
const TOAST_ID = "live-pending";

/**
 * Subscribes to the backend SSE feed and surfaces incoming events as a
 * single sticky "N new events" toast. The user explicitly clicks
 * "Refresh" to revalidate SWR caches - per UX review, never silently
 * reorder rows under the user's cursor.
 *
 * Renders nothing; mount once near the root.
 */
export function LiveUpdates() {
  const { mutate } = useSWRConfig();
  const [pending, setPending] = useState(0);

  // Open the SSE connection once (layout is mounted for the lifetime of the app).
  useEffect(() => {
    const url = "/api/events";
    let source: EventSource | null = null;

    try {
      source = new EventSource(url);
    } catch {
      return;
    }

    const handler = () => setPending((p) => p + 1);
    WATCHED_EVENTS.forEach((t) => source!.addEventListener(t, handler));

    return () => {
      if (!source) return;
      WATCHED_EVENTS.forEach((t) => source!.removeEventListener(t, handler));
      source.close();
    };
  }, []);

  // Maintain a single sticky toast that reflects the current pending count.
  useEffect(() => {
    if (pending === 0) {
      toast.dismiss(TOAST_ID);
      return;
    }
    toast.message(`${pending} new event${pending > 1 ? "s" : ""}`, {
      id: TOAST_ID,
      duration: Number.POSITIVE_INFINITY,
      description: "Click to refresh the views.",
      action: {
        label: "Refresh",
        onClick: () => {
          // Revalidate every SWR key pointing at /api/* (covers calls,
          // leads, action-queue, bookings, metrics, detail pages).
          mutate(
            (key) => typeof key === "string" && key.startsWith("/api/"),
            undefined,
            { revalidate: true },
          );
          setPending(0);
        },
      },
    });
  }, [pending, mutate]);

  return null;
}

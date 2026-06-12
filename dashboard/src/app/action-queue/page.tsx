"use client";

import useSWR from "swr";

import { AsyncBoundary } from "@/components/async-boundary";
import { CallTable } from "@/components/call-table";
import { fetcher } from "@/lib/api";
import type { Call, ListEnvelope } from "@/lib/types";

export default function ActionQueuePage() {
  const { data, error, isLoading } = useSWR<ListEnvelope<Call>>(
    "/api/action-queue",
    fetcher,
    { refreshInterval: 10_000 },
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Action queue</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Hot and warm leads who left their email but don&apos;t have a booking
          yet — send the demo video.
        </p>
      </div>

      <AsyncBoundary
        data={data}
        isLoading={isLoading}
        error={error}
        isEmpty={(d) => d.data.length === 0}
        empty="Inbox zero — every warm lead has been booked or followed up."
      >
        {(d) => <CallTable calls={d.data} />}
      </AsyncBoundary>
    </div>
  );
}

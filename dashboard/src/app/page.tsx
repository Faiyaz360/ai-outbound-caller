"use client";

import useSWR from "swr";

import { AsyncBoundary } from "@/components/async-boundary";
import { CallTable } from "@/components/call-table";
import { MetricCard } from "@/components/metric-card";
import { fetcher } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import type { Call, Envelope, ListEnvelope, Metrics } from "@/lib/types";

export default function OverviewPage() {
  const today = useSWR<Envelope<Metrics>>(
    "/api/metrics?range=today",
    fetcher,
    { refreshInterval: 10_000 },
  );
  const week = useSWR<Envelope<Metrics>>(
    "/api/metrics?range=week",
    fetcher,
    { refreshInterval: 30_000 },
  );
  const month = useSWR<Envelope<Metrics>>(
    "/api/metrics?range=month",
    fetcher,
    { refreshInterval: 60_000 },
  );
  const recent = useSWR<ListEnvelope<Call>>(
    "/api/calls?limit=10",
    fetcher,
    { refreshInterval: 5_000 },
  );

  const t = today.data?.data;
  const w = week.data?.data;
  const m = month.data?.data;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricCard
          label="Calls today"
          value={t?.calls ?? "·"}
          hint={`${w?.calls ?? "·"} this week`}
        />
        <MetricCard
          label="Contact rate"
          value={t ? `${t.contact_capture_pct}%` : "·"}
          hint="emails captured today"
        />
        <MetricCard
          label="Booking rate"
          value={t ? `${t.booking_rate_pct}%` : "·"}
          hint="meetings vs calls today"
        />
        <MetricCard
          label="Avg call"
          value={formatDuration(t?.avg_duration_s ?? 0)}
          hint={`30-day avg ${formatDuration(m?.avg_duration_s ?? 0)}`}
        />
      </div>

      <section>
        <h2 className="mb-3 text-lg font-medium">Recent calls</h2>
        <AsyncBoundary
          data={recent.data}
          isLoading={recent.isLoading}
          error={recent.error}
          isEmpty={(d) => d.data.length === 0}
          empty="No calls recorded yet. Run `emma call` to start one."
        >
          {(d) => <CallTable calls={d.data} />}
        </AsyncBoundary>
      </section>
    </div>
  );
}

"use client";

import { useState } from "react";
import useSWR from "swr";

import { AsyncBoundary } from "@/components/async-boundary";
import { CallTable } from "@/components/call-table";
import { fetcher } from "@/lib/api";
import type { Call, ListEnvelope, Outcome, Tier } from "@/lib/types";

const OUTCOMES: Array<{ value: Outcome | ""; label: string }> = [
  { value: "", label: "All outcomes" },
  { value: "meeting_booked", label: "Meeting booked" },
  { value: "pilot_agreed", label: "Pilot agreed" },
  { value: "follow_up_scheduled", label: "Follow-up scheduled" },
  { value: "not_now", label: "Not now" },
  { value: "do_not_call", label: "Do not call" },
];

const TIERS: Array<{ value: Tier | ""; label: string }> = [
  { value: "", label: "All tiers" },
  { value: "HOT", label: "Hot" },
  { value: "WARM", label: "Warm" },
  { value: "COLD", label: "Cold" },
  { value: "DEAD", label: "Dead" },
];

export default function CallsPage() {
  const [outcome, setOutcome] = useState<Outcome | "">("");
  const [tier, setTier] = useState<Tier | "">("");

  const params = new URLSearchParams({ limit: "100" });
  if (outcome) params.set("outcome", outcome);
  if (tier) params.set("tier", tier);

  const { data, error, isLoading } = useSWR<ListEnvelope<Call>>(
    `/api/calls?${params.toString()}`,
    fetcher,
    { refreshInterval: 5_000 },
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Calls</h1>
        <div className="text-muted-foreground text-sm">
          {data?.meta.total ?? "—"} total
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <FilterSelect
          value={outcome}
          onChange={(v) => setOutcome(v as Outcome | "")}
          options={OUTCOMES}
        />
        <FilterSelect
          value={tier}
          onChange={(v) => setTier(v as Tier | "")}
          options={TIERS}
        />
      </div>

      <AsyncBoundary
        data={data}
        isLoading={isLoading}
        error={error}
        isEmpty={(d) => d.data.length === 0}
        empty="No calls match those filters."
      >
        {(d) => <CallTable calls={d.data} />}
      </AsyncBoundary>
    </div>
  );
}

interface FilterSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: ReadonlyArray<{ value: string; label: string }>;
}

function FilterSelect({ value, onChange, options }: FilterSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-background hover:bg-accent rounded-md border px-3 py-1.5 text-sm"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

"use client";

import useSWR from "swr";

import { AsyncBoundary } from "@/components/async-boundary";
import { CallTable } from "@/components/call-table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { fetcher } from "@/lib/api";
import type { LeadsEnvelope, Tier } from "@/lib/types";

const TIERS: readonly Tier[] = ["HOT", "WARM", "COLD", "DEAD"];

export default function LeadsPage() {
  const { data, error, isLoading } = useSWR<LeadsEnvelope>(
    "/api/leads",
    fetcher,
    { refreshInterval: 5_000 },
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Leads</h1>

      <AsyncBoundary data={data} isLoading={isLoading} error={error}>
        {(d) => {
          const all = TIERS.flatMap((t) => d.data[t]);
          return (
            <Tabs defaultValue="all" className="w-full">
              <TabsList>
                <TabsTrigger value="all">
                  All
                  <span className="text-muted-foreground ml-1.5">
                    {all.length}
                  </span>
                </TabsTrigger>
                {TIERS.map((t) => (
                  <TabsTrigger key={t} value={t}>
                    {t.charAt(0) + t.slice(1).toLowerCase()}
                    <span className="text-muted-foreground ml-1.5">
                      {d.meta[t]}
                    </span>
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="all" className="mt-4">
                {all.length === 0 ? (
                  <EmptyLeads />
                ) : (
                  <CallTable calls={all} />
                )}
              </TabsContent>
              {TIERS.map((t) => (
                <TabsContent key={t} value={t} className="mt-4">
                  {d.data[t].length === 0 ? (
                    <EmptyLeads tier={t} />
                  ) : (
                    <CallTable calls={d.data[t]} />
                  )}
                </TabsContent>
              ))}
            </Tabs>
          );
        }}
      </AsyncBoundary>
    </div>
  );
}

function EmptyLeads({ tier }: { tier?: Tier }) {
  return (
    <div className="text-muted-foreground rounded-md border border-dashed p-8 text-center text-sm">
      {tier ? `No ${tier.toLowerCase()} leads yet.` : "No leads yet."}
    </div>
  );
}

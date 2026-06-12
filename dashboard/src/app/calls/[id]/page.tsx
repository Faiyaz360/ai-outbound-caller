"use client";

import { useParams } from "next/navigation";
import useSWR from "swr";

import { AsyncBoundary } from "@/components/async-boundary";
import { ScoreBadge } from "@/components/score-badge";
import { TranscriptViewer } from "@/components/transcript-viewer";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetcher } from "@/lib/api";
import {
  formatDateTime,
  formatDuration,
  formatOutcome,
} from "@/lib/format";
import type { Call, Envelope } from "@/lib/types";

export default function CallDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  const { data, error, isLoading } = useSWR<Envelope<Call>>(
    id ? `/api/calls/${encodeURIComponent(id)}` : null,
    fetcher,
    { refreshInterval: 5_000 },
  );

  return (
    <div className="space-y-6">
      <AsyncBoundary data={data} isLoading={isLoading} error={error}>
        {({ data: c }) => (
          <>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">
                  {c.contact || "Unknown contact"}
                </h1>
                <p className="text-muted-foreground text-sm">
                  {c.practice || "—"}
                </p>
              </div>
              <ScoreBadge tier={c.tier} score={c.score} />
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
              <Field label="When" value={formatDateTime(c.started_at)} />
              <Field label="Duration" value={formatDuration(c.duration_s)} />
              <Field
                label="Outcome"
                value={formatOutcome(c.outcome) || "—"}
              />
              <Field label="Email" value={c.email || "—"} mono />
            </div>

            {c.summary && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">
                    Summary
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm">{c.summary}</CardContent>
              </Card>
            )}

            <div className="grid gap-6 md:grid-cols-[1fr_280px]">
              <section>
                <h2 className="mb-3 text-lg font-medium">Transcript</h2>
                <TranscriptViewer transcript={c.transcript} />
              </section>

              <aside className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium">
                      Score reasons
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {c.score_reasons.length === 0 ? (
                      <p className="text-muted-foreground text-sm">
                        No factors hit.
                      </p>
                    ) : (
                      <ul className="space-y-1 text-sm">
                        {c.score_reasons.map((r, i) => (
                          <li key={i} className="font-mono text-xs">
                            {r}
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
              </aside>
            </div>
          </>
        )}
      </AsyncBoundary>
    </div>
  );
}

interface FieldProps {
  label: string;
  value: string;
  mono?: boolean;
}

function Field({ label, value, mono }: FieldProps) {
  return (
    <div>
      <div className="text-muted-foreground text-xs uppercase tracking-wide">
        {label}
      </div>
      <div className={`mt-0.5 ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import useSWR from "swr";

import { AsyncBoundary } from "@/components/async-boundary";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fetcher } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Booking, ListEnvelope } from "@/lib/types";

export default function BookingsPage() {
  const { data, error, isLoading } = useSWR<ListEnvelope<Booking>>(
    "/api/bookings/upcoming",
    fetcher,
    { refreshInterval: 30_000 },
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">
          Upcoming bookings
        </h1>
        <div className="text-muted-foreground text-sm">
          {data?.meta.total ?? "—"} scheduled
        </div>
      </div>

      <AsyncBoundary
        data={data}
        isLoading={isLoading}
        error={error}
        isEmpty={(d) => d.data.length === 0}
        empty="No meetings booked yet."
      >
        {(d) => (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Attendee</TableHead>
                <TableHead>Practice</TableHead>
                <TableHead>Call</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.data.map((b) => (
                <TableRow key={b.uid}>
                  <TableCell className="text-sm whitespace-nowrap">
                    {formatDateTime(b.start)}
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">
                      {b.attendee_name || "—"}
                    </div>
                    {b.attendee_email && (
                      <div className="text-muted-foreground font-mono text-xs">
                        {b.attendee_email}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">
                    {b.practice || "—"}
                  </TableCell>
                  <TableCell>
                    {b.conversation_id ? (
                      <Link
                        href={`/calls/${encodeURIComponent(b.conversation_id)}`}
                        className="text-sm hover:underline"
                      >
                        View call →
                      </Link>
                    ) : (
                      <span className="text-muted-foreground text-sm">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </AsyncBoundary>
    </div>
  );
}

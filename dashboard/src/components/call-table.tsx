"use client";

import Link from "next/link";

import { ScoreBadge } from "@/components/score-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDuration, formatOutcome, formatTimeAgo } from "@/lib/format";
import type { Call } from "@/lib/types";

interface CallTableProps {
  calls: Call[];
}

export function CallTable({ calls }: CallTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>When</TableHead>
          <TableHead>Contact</TableHead>
          <TableHead>Practice</TableHead>
          <TableHead>Outcome</TableHead>
          <TableHead className="text-right">Duration</TableHead>
          <TableHead>Tier</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {calls.map((c) => (
          <TableRow key={c.conversation_id} className="hover:bg-accent">
            <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
              <Link
                href={`/calls/${encodeURIComponent(c.conversation_id)}`}
                className="hover:text-foreground hover:underline"
              >
                {formatTimeAgo(c.started_at)}
              </Link>
            </TableCell>
            <TableCell>
              <Link
                href={`/calls/${encodeURIComponent(c.conversation_id)}`}
                className="block"
              >
                <div className="font-medium">{c.contact || "—"}</div>
                {c.email && (
                  <div className="text-muted-foreground text-xs font-mono">
                    {c.email}
                  </div>
                )}
              </Link>
            </TableCell>
            <TableCell className="text-sm">{c.practice || "—"}</TableCell>
            <TableCell className="text-sm capitalize">
              {formatOutcome(c.outcome)}
            </TableCell>
            <TableCell className="text-right text-sm tabular-nums">
              {formatDuration(c.duration_s)}
            </TableCell>
            <TableCell>
              <ScoreBadge tier={c.tier} score={c.score} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

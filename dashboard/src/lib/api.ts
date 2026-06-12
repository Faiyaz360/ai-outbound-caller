// Typed fetch client for the FastAPI dashboard endpoints.
// All requests go through the Next.js rewrite at /api/* -> :8000/api/*.

import type {
  Booking,
  Call,
  Envelope,
  LeadsEnvelope,
  ListEnvelope,
  Metrics,
} from "@/lib/types";

const BASE = "/api";

interface ListCallsParams {
  limit?: number;
  offset?: number;
  outcome?: string;
  tier?: string;
  from_iso?: string;
  to_iso?: string;
}

function qs<T extends object>(params: T): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} -> ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  listCalls: (params: ListCallsParams = {}) =>
    get<ListEnvelope<Call>>(`/calls${qs(params)}`),

  getCall: (conversationId: string) =>
    get<Envelope<Call>>(`/calls/${encodeURIComponent(conversationId)}`),

  listLeads: () => get<LeadsEnvelope>("/leads"),

  listActionQueue: (limit = 50) =>
    get<ListEnvelope<Call>>(`/action-queue${qs({ limit })}`),

  listUpcomingBookings: (limit = 20) =>
    get<ListEnvelope<Booking>>(`/bookings/upcoming${qs({ limit })}`),

  metrics: (range: "today" | "week" | "month" = "today") =>
    get<Envelope<Metrics>>(`/metrics?range=${range}`),
};

// Generic SWR fetcher (used by hooks that prefer SWR's cache/dedup).
export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Fetch ${url} -> ${res.status}`);
  return (await res.json()) as T;
}

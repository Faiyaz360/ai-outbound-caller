// API DTOs matching the FastAPI envelopes in src/emma/dashboard_api.py.

export type Tier = "HOT" | "WARM" | "COLD" | "DEAD";

export type Outcome =
  | "meeting_booked"
  | "pilot_agreed"
  | "follow_up_scheduled"
  | "not_now"
  | "do_not_call"
  | "";

export interface Call {
  conversation_id: string;
  started_at: string | null;
  duration_s: number;
  contact: string;
  email: string;
  practice: string;
  outcome: Outcome;
  summary: string;
  transcript: string;
  analysis: Record<string, unknown>;
  score: number;
  tier: Tier;
  score_reasons: string[];
}

export interface Booking {
  uid: string;
  conversation_id: string;
  start: string;
  attendee_name: string;
  attendee_email: string;
  practice: string;
  created_at: string;
}

export interface Metrics {
  range: "today" | "week" | "month";
  calls: number;
  contact_capture_pct: number;
  booking_rate_pct: number;
  avg_duration_s: number;
}

export type Envelope<T> = {
  data: T;
  meta?: Record<string, unknown>;
};

export type ListEnvelope<T> = {
  data: T[];
  meta: { total: number; limit?: number; offset?: number };
};

export type LeadsByTier = Record<Tier, Call[]>;

export interface LeadsEnvelope {
  data: LeadsByTier;
  meta: Record<Tier, number>;
}

# Emma Dashboard

Next.js 16 + Tailwind v4 + shadcn/ui frontend for the Emma outbound sales
agent. Reads from the FastAPI backend at `localhost:8000` via the rewrite
in `next.config.ts` (no CORS dance).

## Pages

| Path | What it shows |
|---|---|
| `/` | Overview — today/week/month metric cards + recent calls |
| `/calls` | Filterable list of every call (outcome + tier filters) |
| `/calls/[id]` | One call: metadata, summary, transcript, score reasons |
| `/leads` | Lead board grouped by tier (HOT / WARM / COLD / DEAD) |
| `/action-queue` | Hot or warm leads with an email but no booking yet |
| `/bookings` | Upcoming Cal.com meetings |

The persistent header carries an Emma "live" indicator, nav, today's
mini-metrics and a dark/light toggle.

## Run it

Two terminals — backend first, frontend second:

```bash
# Terminal 1 — backend (FastAPI on :8000)
cd ..
.\.venv\Scripts\emma.exe serve

# Terminal 2 — dashboard (Next.js on :3100)
cd dashboard
npm run dev
```

Then open <http://localhost:3100>.

### Empty database? Seed demo data

```bash
cd ..
.\.venv\Scripts\python.exe scripts/seed_dashboard.py
```

Drops 4 sample calls (one of each tier) + a booking into `emma.db`, so
every dashboard view has content.

## Live updates

`<LiveUpdates>` opens a Server-Sent Events connection to
`/api/events`. When the backend publishes a `call_updated` or
`booking_created` event (from the post-call webhook, `log_call_outcome`
tool, or `book_meeting` tool), a single sticky toast appears
("N new events — Refresh"). Clicking Refresh revalidates every SWR query
to `/api/*`. Rows never silently reorder under the user's cursor.

## Optional auth

If `DASHBOARD_TOKEN` is set in the project `.env`, every `/api/*` endpoint
requires `Authorization: Bearer <token>`. The frontend currently makes
unauthenticated requests — flip this on only when wiring the token through
to the client.

## Lead scoring

Rules-based (see `src/emma/scoring.py`). Score persisted on each call
record at write-time (post-call webhook or tool call). Dashboard reads
only.

| Signal | Points |
|---|---|
| `meeting_booked` | +50 |
| `pilot_agreed` | +60 |
| `follow_up_scheduled` | +25 |
| `not_now` | +5 |
| `do_not_call` | -50 |
| Email captured | +20 |
| Duration > 60s | +10 |
| Decision-maker keyword | +15 |

Tier mapping: ≥60 HOT · 30-59 WARM · 1-29 COLD · ≤0 DEAD.

## Stack

- Next.js 16 (app router), React 19, TypeScript strict
- Tailwind v4 + shadcn/ui (zinc base, dark mode default)
- SWR (5-30s polling depending on view) + EventSource for SSE
- Lucide icons, date-fns, next-themes

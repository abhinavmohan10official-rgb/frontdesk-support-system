# Frontdesk

Frontdesk is a Django + MySQL support-ticket system for the Full Stack Developer assessment. It gives support agents one screen for ticket ownership, SLA visibility, customer replies, private team notes, and an audit trail.

## Run locally

Requirements: Python 3.11+ and MySQL 8+ for assessment mode.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a MySQL database and user, then copy `.env.example` to `.env` and set the values in your environment. For a quick UI preview without MySQL, leave `MYSQL_HOST` unset; Django uses SQLite only as a local fallback. The submitted/deployment configuration should set `MYSQL_HOST` and use MySQL.

```powershell
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000.

## Assessment rules implemented

- MySQL-backed Django ORM models for agents, tickets, messages, private notes, and audit events.
- Working hours are 09:30–18:30 IST, Monday–Friday. Festival holidays can be configured through `FESTIVAL_HOLIDAYS` as comma-separated ISO dates.
- Urgent tickets: two-hour first response and same-working-day resolution. Medium tickets: half-day first response and three working days to resolve. Small tickets: one-working-day first response and one working week to resolve.
- Customer waiting time continues to count against SLA targets.
- Waiting tickets are closed after one working week without a customer response. Resolved tickets can be reopened for one week; after that the API explains that a new ticket is required.
- Ticket claiming uses a database transaction and row lock so two agents cannot claim the same ticket.
- Private notes are stored separately and are excluded from the customer-view API. The agent API is intended for authenticated support users in deployment.
- Audit events record what happened, when, and who did it. There is no update endpoint for audit events.

## API overview

- `GET /api/tickets?filter=all|mine|late|waiting`
- `POST /api/tickets/:id/claim`
- `POST /api/tickets/:id/reply` with `{ "body": "...", "actor": "..." }`
- `POST /api/tickets/:id/note` with `{ "body": "...", "actor": "..." }`
- `POST /api/tickets/:id/status` with `{ "status": "waiting_customer|resolved|closed|reopen" }`
- `GET /api/tickets/:id/customer-view` excludes private notes
- `GET /api/tickets/:id/audit`

## Product decision

The source brief asks what should happen when severity changes mid-ticket but does not answer it. Frontdesk recalculates the target from the original creation time using the current severity. This policy is isolated in `tickets/services.py`.

## Submission checklist

- Live URL hosted on a public platform and kept online for one week.
- Public repository link.
- README with setup instructions.
- Completion note describing unfinished items.

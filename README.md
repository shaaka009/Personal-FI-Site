# Personal FI Tracker

Local-first personal finance tracker using React + Django + Plaid.

## Stack
- Frontend: React (Vite)
- Backend: Django + Django REST Framework
- Database: SQLite
- Data source: Plaid (Development environment)

## Setup

### 1) Environment values

Create `backend/.env` from `backend/.env.example` and fill in your Plaid credentials:

- `PLAID_CLIENT_ID`
- `PLAID_SECRET`
- `PLAID_ENV` (`development`, `sandbox`, or `production`)
- `PLAID_PRODUCTS` (default: `transactions,investments`)
- `PLAID_COUNTRY_CODES` (default: `US`)
- `PLAID_TRANSACTION_SYNC_LOOKBACK_DAYS` (optional, default `365`, max `730`) — passed to Plaid as **(a)** `transactions.days_requested` when creating a Link token (how much history Plaid will ever retain for that Item) and **(b)** the `/transactions/get` `start_date` window on each sync. **Important:** if you already linked a bank before increasing this value, Plaid will not retroactively add older transactions for that Item—you must disconnect that institution (Plaid Dashboard or remove the Item) and use **Connect Institution** again so the new depth applies.

Never commit `backend/.env` to source control.

### 2) Bootstrap with make

```bash
make backend-install
make backend-migrate
make frontend-install
```

## Make Commands (Primary Workflow)

Use these from the repository root to avoid repeating long commands:

```bash
make help
make backend-install
make backend-migrate
make frontend-install
make backend-run
make frontend-run
make plaid-sync
make db-summary
make backend-test
```

Most common day-to-day flow:

```bash
make backend-run
# in a second terminal
make frontend-run
```

## API Endpoints
- `POST /api/plaid/link-token`
- `POST /api/plaid/exchange-token`
- `POST /api/plaid/sync` — syncs each linked Plaid item independently; returns `items_failed` if some institutions error while others succeed (HTTP 200). If every item fails, returns HTTP 502 with the same payload shape.
- `GET /api/plaid/sync-status` — per-item last sync time, success flag, and error text for the dashboard.
- `GET /api/accounts`
- `GET /api/transactions` — `{ "results": [...], "count": <matching rows> }`. Optional query params: `date_from`, `date_to` (`YYYY-MM-DD`), `account_id`, `institution` (substring), `category` (substring on primary/detailed), `q` (name or merchant), `pending` (`true` / `false`), `limit` (default 500, max 2000).

## Operator Runbook

### Start local stack

1. Start backend: `make backend-run`
2. Start frontend: `make frontend-run`
3. Open the app at `http://localhost:5173`.

### Connect and sync institutions

1. Click **Connect Institution** and complete Plaid Link.
2. Click **Sync Data**.
3. Validate sync health from UI status banner and institution sync table.

### Verify data in backend (quick checks)

- Summary counts + institutions: `make db-summary`
- Trigger a manual sync: `make plaid-sync`

### Milestone acceptance checklist (Plaid-first)

- At least one real institution links successfully via Plaid.
- `GET /api/accounts` returns current balances.
- `GET /api/transactions` returns filtered rows (see API Endpoints) for the Transactions tab.
- `POST /api/plaid/sync` can be re-run without creating duplicates.
- New machine setup works with only this README + env templates.

### Current project direction

- Plaid covers connected accounts and balances.
- Next work is **personal-use features** you pick (see `.cursor/plans/plaid-first_finance_app_650e43a8.plan.md` Phase 4).

## Notes
- This is currently a single-user local app with no login.
- Keep Plaid credentials in `backend/.env`.

## Extra Info: Manual Commands (Without make)

### Backend manual setup/run
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install django djangorestframework django-cors-headers plaid-python python-dotenv
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

### Frontend manual setup/run
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

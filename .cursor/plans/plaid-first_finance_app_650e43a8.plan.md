---
name: Plaid-First Finance App
overview: Set up a React + Django monorepo for a single-user personal finance app, implement a real-data Plaid Development integration first, and establish a clean path for later market-data and automation features.
todos:
  - id: bootstrap-repo
    content: Create frontend React app and backend Django project with local dev wiring
    status: completed
  - id: plaid-backend
    content: Implement Plaid Development endpoints, client wrapper, and minimal SQLite models
    status: completed
  - id: plaid-frontend
    content: Implement Plaid Link connect flow and account/transaction views in React
    status: completed
  - id: sync-hardening
    content: Add idempotent sync logic, error handling, and endpoint tests
    status: completed
  - id: docs-acceptance
    content: Document setup and verify milestone acceptance criteria end-to-end
    status: completed
isProject: false
---

# Plaid-First Personal Finance Plan

## Goals

- Build a local single-user personal finance site with:
  - React frontend
  - Lightweight Django backend + SQLite
  - Plaid as primary financial data source
- First milestone: connect real institutions in Plaid Development and display linked account balances/transactions.
- Defer automation and Equate Plus modeling until after Plaid connection is stable.

## Architecture (Phase 1)

- **Frontend (React)**
  - UI to start Plaid Link flow.
  - Accounts view (institution, account type, current balance).
  - Recent transactions view (basic date/merchant/amount table).
- **Backend (Django + DRF-style JSON endpoints)**
  - Plaid endpoints only:
    - create link token
    - exchange public token
    - sync accounts and transactions
    - return normalized data to frontend
  - Minimal persistence in SQLite (only what is needed for refresh/sync).
- **Data model (minimal)**
  - `Item` (Plaid item_id, access token encrypted/obfuscated-at-rest strategy)
  - `Account` (plaid_account_id, name, subtype, balances)
  - `Transaction` (plaid_transaction_id, date, name, amount, category)

## Suggested Repository Layout

- [frontend/](frontend/) React app
- [backend/](backend/) Django project
- [backend/app/](backend/app/) Django app for finance APIs
- [backend/app/services/plaid_client.py](backend/app/services/plaid_client.py) Plaid SDK wrapper
- [backend/app/api/views.py](backend/app/api/views.py) API endpoints
- [backend/app/models.py](backend/app/models.py) minimal tables
- [backend/.env.example](backend/.env.example) Plaid + app env vars
- [README.md](README.md) setup and run instructions

## Implementation Phases

### Phase 0: Project bootstrap

- Initialize frontend and backend directories.
- Add environment-variable-based configuration for Plaid Development credentials.
- Add CORS and local dev config so React can call Django.

### Phase 1: Plaid connection (real data)

- Backend:
  - Implement `POST /api/plaid/link-token`.
  - Implement `POST /api/plaid/exchange-token`.
  - Store Plaid item/access token for single-user setup.
  - Implement `POST /api/plaid/sync` to fetch accounts + transactions and persist/refresh local copies.
  - Implement `GET /api/accounts` and `GET /api/transactions` for frontend.
- Frontend:
  - Integrate Plaid Link SDK.
  - Add “Connect Institution” flow.
  - Build simple accounts + transactions pages.

### Phase 2: Stabilization

- Add idempotent sync behavior (upsert by Plaid IDs).
- Add error handling for invalid link tokens, institution auth failures, and expired items.
- Add basic test coverage:
  - Backend endpoint tests with mocked Plaid client
  - Frontend integration check for link flow and table rendering

### Phase 3 (next after MVP): Market data + Equate Plus

- Add market data provider client (e.g., Alpha Vantage, IEX Cloud, or Polygon).
- Model Equate Plus contributions as deterministic recurring events tied to SAP price history.
- Merge projected Equate value into portfolio dashboard as a separate computed source.

## Security and Ops Notes

- Keep Plaid credentials in env vars only.
- For now (single-user), keep authentication off, but guard API with local-only/dev assumptions.
- Plan a future hardening pass before any public deployment (auth, HTTPS, secret management, token encryption policy).

## Acceptance Criteria for Milestone 1

- User can connect at least one real institution through Plaid Development.
- Linked accounts appear in UI with current balances.
- Recent transactions load and display from synced data.
- Sync endpoint can be rerun safely without duplicating records.
- Local setup docs allow reproducible run from clean machine.


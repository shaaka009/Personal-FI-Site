import { useCallback, useEffect, useMemo, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import {
  ApiError,
  createLinkToken,
  exchangePublicToken,
  getAccounts,
  getSyncStatus,
  getTransactions,
  syncData,
} from "./api";
import "./App.css";

const emptyTxnFilters = () => ({
  dateFrom: "",
  dateTo: "",
  accountId: "",
  institution: "",
  category: "",
  q: "",
  pending: "",
});

function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [linkToken, setLinkToken] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [syncStatus, setSyncStatus] = useState([]);
  const [statusMessage, setStatusMessage] = useState("Ready");
  const [loading, setLoading] = useState(false);

  const [txnDraftFilters, setTxnDraftFilters] = useState(emptyTxnFilters);
  const [txnAppliedFilters, setTxnAppliedFilters] = useState(emptyTxnFilters);
  const [txnResults, setTxnResults] = useState([]);
  const [txnTotal, setTxnTotal] = useState(0);
  const [txnLoading, setTxnLoading] = useState(false);
  const [txnError, setTxnError] = useState("");

  const fetchDashboardData = useCallback(async () => {
    const [accountsData, statusData] = await Promise.all([getAccounts(), getSyncStatus()]);
    setAccounts(accountsData);
    setSyncStatus(statusData);
  }, []);

  const loadLinkToken = useCallback(async () => {
    try {
      const data = await createLinkToken();
      setLinkToken(data.link_token);
    } catch (error) {
      setStatusMessage(formatLinkTokenError(error));
    }
  }, []);

  const runSyncAndRefresh = useCallback(async () => {
    try {
      const result = await syncData();
      await fetchDashboardData();
      if (result.items_failed?.length) {
        setStatusMessage(
          `Synced with issues: ${result.items_failed.length} institution(s) failed.${institutionDowntimeHint(result)}`,
        );
      } else {
        const summary = `Data synced (${result.transactions_created} new, ${result.transactions_updated} updated).`;
        const note = result.history_note ? ` ${result.history_note}` : "";
        setStatusMessage(summary + note);
      }
    } catch (error) {
      await fetchDashboardData().catch(() => {});
      if (error instanceof ApiError && error.status === 502 && error.body?.items_failed?.length) {
        setStatusMessage(
          `Sync failed for all linked institutions.${formatItemsFailed(error.body.items_failed)}${institutionDowntimeHint(error.body)}`,
        );
        return;
      }
      throw error;
    }
  }, [fetchDashboardData]);

  const onSuccess = useCallback(
    async (publicToken, metadata) => {
      try {
        setLoading(true);
        setStatusMessage("Exchanging token…");
        await exchangePublicToken(publicToken, metadata.institution?.name || "");
        setStatusMessage("Link saved. Syncing data…");
        await runSyncAndRefresh();
      } catch (error) {
        setStatusMessage(formatActionError("Connection failed", error));
      } finally {
        setLoading(false);
        await loadLinkToken();
      }
    },
    [loadLinkToken, runSyncAndRefresh],
  );

  const institutionOptions = useMemo(() => {
    const names = new Set();
    for (const a of accounts) {
      const n = (a.institution || "").trim();
      if (n) names.add(n);
    }
    return [...names].sort((x, y) => x.localeCompare(y));
  }, [accounts]);

  const txnQueryParams = useCallback((filters) => {
    const p = { limit: 2000 };
    if (filters.dateFrom) p.date_from = filters.dateFrom;
    if (filters.dateTo) p.date_to = filters.dateTo;
    if (filters.accountId) p.account_id = filters.accountId;
    if (filters.institution) p.institution = filters.institution;
    if (filters.category) p.category = filters.category;
    if (filters.q) p.q = filters.q;
    if (filters.pending === "pending") p.pending = true;
    if (filters.pending === "posted") p.pending = false;
    return p;
  }, []);

  useEffect(() => {
    if (activeTab !== "transactions") return undefined;
    let cancelled = false;
    (async () => {
      setTxnLoading(true);
      setTxnError("");
      try {
        const data = await getTransactions(txnQueryParams(txnAppliedFilters));
        if (!cancelled) {
          setTxnResults(data.results || []);
          setTxnTotal(typeof data.count === "number" ? data.count : (data.results || []).length);
        }
      } catch (e) {
        if (!cancelled) {
          setTxnResults([]);
          setTxnTotal(0);
          setTxnError(formatActionError("Could not load transactions", e));
        }
      } finally {
        if (!cancelled) setTxnLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeTab, txnAppliedFilters, txnQueryParams]);

  useEffect(() => {
    loadLinkToken();
    fetchDashboardData().catch(() => {});
  }, [fetchDashboardData, loadLinkToken]);

  const config = useMemo(
    () => ({
      token: linkToken,
      onSuccess,
    }),
    [linkToken, onSuccess],
  );

  const { open, ready } = usePlaidLink(config);

  const handleSync = async () => {
    try {
      setLoading(true);
      setStatusMessage("Syncing latest data…");
      await runSyncAndRefresh();
    } catch (error) {
      setStatusMessage(formatActionError("Sync failed", error));
    } finally {
      setLoading(false);
    }
  };

  const statusClass =
    statusMessage.includes("failed") || statusMessage.includes("issues")
      ? "status--warn"
      : "";

  const applyTxnFilters = () => {
    setTxnAppliedFilters({ ...txnDraftFilters });
  };

  const resetTxnFilters = () => {
    const empty = emptyTxnFilters();
    setTxnDraftFilters(empty);
    setTxnAppliedFilters(empty);
  };

  return (
    <main className="container">
      <header>
        <h1>Personal Finance Tracker</h1>
        <p>Single-user dashboard powered by Plaid + Django + React.</p>
        <div className="actions">
          <button
            type="button"
            onClick={() => open()}
            disabled={!ready || !linkToken || loading}
          >
            Connect Institution
          </button>
          <button type="button" onClick={handleSync} disabled={loading}>
            Sync Data
          </button>
        </div>
        <p className={`status ${statusClass}`}>{statusMessage}</p>
        <p className="hint">
          If a bank shows institution downtime, wait and use Sync Data again. BoA / Schwab outages are
          often temporary on Plaid&apos;s side too.
        </p>
      </header>

      <nav className="tabs" aria-label="Main views">
        <button
          type="button"
          className={`tabs__btn${activeTab === "overview" ? " tabs__btn--active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          Overview
        </button>
        <button
          type="button"
          className={`tabs__btn${activeTab === "transactions" ? " tabs__btn--active" : ""}`}
          onClick={() => setActiveTab("transactions")}
        >
          Transactions
        </button>
      </nav>

      {activeTab === "overview" && (
        <>
          {syncStatus.length > 0 && (
            <section className="sync-panel">
              <h2>Institution sync status</h2>
              <table>
                <thead>
                  <tr>
                    <th>Institution</th>
                    <th>Last sync</th>
                    <th>Status</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {syncStatus.map((row) => (
                    <tr key={row.item_id}>
                      <td>{row.institution || "—"}</td>
                      <td>{formatSyncTime(row.last_sync_at)}</td>
                      <td>
                        {row.last_sync_at === null
                          ? "Never synced"
                          : row.last_sync_success
                            ? "OK"
                            : "Error"}
                      </td>
                      <td className="cell-note">{row.last_sync_error || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <section>
            <h2>Accounts</h2>
            {accounts.length === 0 ? (
              <p>No accounts synced yet.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Institution</th>
                    <th>Account</th>
                    <th>Type</th>
                    <th>Current</th>
                    <th>Available</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.id}>
                      <td>{account.institution || "Unknown"}</td>
                      <td>
                        {account.name}
                        {account.mask ? ` ••••${account.mask}` : ""}
                      </td>
                      <td>{`${account.type}/${account.subtype || "-"}`}</td>
                      <td>{formatCurrency(account.current_balance, account.currency_code)}</td>
                      <td>{formatCurrency(account.available_balance, account.currency_code)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}

      {activeTab === "transactions" && (
        <section className="transactions-panel">
          <h2>Browse transactions</h2>
          <p className="hint transactions-panel__hint">
            Set filters and click <strong>Apply filters</strong>. History depth is set by{" "}
            <code>PLAID_TRANSACTION_SYNC_LOOKBACK_DAYS</code> at <strong>first link</strong>; raising it later
            needs disconnect + <strong>Connect Institution</strong> again (see README).
          </p>

          <div className="filters">
            <label className="filters__field">
              <span>From date</span>
              <input
                type="date"
                value={txnDraftFilters.dateFrom}
                onChange={(e) => setTxnDraftFilters((f) => ({ ...f, dateFrom: e.target.value }))}
              />
            </label>
            <label className="filters__field">
              <span>To date</span>
              <input
                type="date"
                value={txnDraftFilters.dateTo}
                onChange={(e) => setTxnDraftFilters((f) => ({ ...f, dateTo: e.target.value }))}
              />
            </label>
            <label className="filters__field">
              <span>Institution</span>
              <select
                value={txnDraftFilters.institution}
                onChange={(e) => setTxnDraftFilters((f) => ({ ...f, institution: e.target.value }))}
              >
                <option value="">All institutions</option>
                {institutionOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <label className="filters__field">
              <span>Account</span>
              <select
                value={txnDraftFilters.accountId}
                onChange={(e) => setTxnDraftFilters((f) => ({ ...f, accountId: e.target.value }))}
              >
                <option value="">All accounts</option>
                {accounts.map((a) => (
                  <option key={a.id} value={String(a.id)}>
                    {(a.institution || "Bank") + " — " + a.name}
                    {a.mask ? ` (${a.mask})` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="filters__field filters__field--wide">
              <span>Search (name or merchant)</span>
              <input
                type="search"
                placeholder="e.g. Whole Foods"
                value={txnDraftFilters.q}
                onChange={(e) => setTxnDraftFilters((f) => ({ ...f, q: e.target.value }))}
              />
            </label>
            <label className="filters__field">
              <span>Category contains</span>
              <input
                type="text"
                placeholder="e.g. FOOD"
                value={txnDraftFilters.category}
                onChange={(e) => setTxnDraftFilters((f) => ({ ...f, category: e.target.value }))}
              />
            </label>
            <label className="filters__field">
              <span>Status</span>
              <select
                value={txnDraftFilters.pending}
                onChange={(e) => setTxnDraftFilters((f) => ({ ...f, pending: e.target.value }))}
              >
                <option value="">All</option>
                <option value="posted">Posted only</option>
                <option value="pending">Pending only</option>
              </select>
            </label>
            <div className="filters__actions">
              <button type="button" onClick={applyTxnFilters} disabled={txnLoading}>
                Apply filters
              </button>
              <button type="button" className="btn-secondary" onClick={resetTxnFilters} disabled={txnLoading}>
                Reset
              </button>
            </div>
          </div>

          {txnError ? <p className="status status--warn">{txnError}</p> : null}
          <p className="transactions-meta">
            {txnLoading
              ? "Loading…"
              : txnTotal === 0
                ? "No matching transactions."
                : `Showing ${txnResults.length} of ${txnTotal} matching row${txnTotal === 1 ? "" : "s"}.`}
          </p>

          {txnResults.length > 0 && (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Institution</th>
                    <th>Account</th>
                    <th>Name</th>
                    <th>Merchant</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th className="cell-num">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {txnResults.map((txn) => (
                    <tr key={txn.id}>
                      <td>{txn.date}</td>
                      <td>{txn.institution || "—"}</td>
                      <td>{txn.account_name}</td>
                      <td>{txn.name}</td>
                      <td>{txn.merchant_name || "—"}</td>
                      <td className="cell-category">
                        <span className="cell-category__primary">{txn.category_primary || "—"}</span>
                        {txn.category_detailed ? (
                          <span className="cell-category__detail">{txn.category_detailed}</span>
                        ) : null}
                      </td>
                      <td>{txn.pending ? "Pending" : "Posted"}</td>
                      <td className="cell-num">{formatCurrency(txn.amount, "USD")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </main>
  );
}

function formatSyncTime(iso) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function formatItemsFailed(items) {
  if (!items?.length) return "";
  return ` ${items.map((i) => i.institution || i.item_id).join(", ")}.`;
}

function institutionDowntimeHint(body) {
  const codes = (body?.items_failed || [])
    .map((i) => i.error_code || "")
    .join(" ");
  if (
    /INSTITUTION|ITEM_LOGIN|INTERNAL_SERVER|RATE_LIMIT|PRODUCTS_NOT_SUPPORTED/i.test(
      codes,
    )
  ) {
    return " Often caused by institution or Plaid maintenance; retry later.";
  }
  return "";
}

function formatLinkTokenError(error) {
  if (error instanceof ApiError) {
    const code = error.body?.error_code ? ` (${error.body.error_code})` : "";
    return `Unable to create link token: ${error.message}${code}`;
  }
  return `Unable to create link token: ${error.message}`;
}

function formatActionError(prefix, error) {
  if (error instanceof ApiError) {
    const code = error.body?.error_code ? ` [${error.body.error_code}]` : "";
    const detail = error.body?.message || error.body?.details || error.message;
    const tail =
      error.status === 502 || error.status === 503
        ? " The bank or Plaid may be temporarily unavailable; retry later."
        : "";
    return `${prefix}: ${detail}${code}${tail}`;
  }
  return `${prefix}: ${error.message}`;
}

function formatCurrency(value, currencyCode) {
  if (value === null || value === undefined) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode || "USD",
  }).format(Number(value));
}

export default App;

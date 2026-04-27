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

function App() {
  const [linkToken, setLinkToken] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [syncStatus, setSyncStatus] = useState([]);
  const [statusMessage, setStatusMessage] = useState("Ready");
  const [loading, setLoading] = useState(false);

  const fetchDashboardData = useCallback(async () => {
    const [accountsData, transactionsData, statusData] = await Promise.all([
      getAccounts(),
      getTransactions(),
      getSyncStatus(),
    ]);
    setAccounts(accountsData);
    setTransactions(transactionsData);
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
        setStatusMessage(
          `Data synced (${result.transactions_created} new, ${result.transactions_updated} updated).`,
        );
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

      <section>
        <h2>Recent Transactions</h2>
        {transactions.length === 0 ? (
          <p>No transactions synced yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Institution</th>
                <th>Account</th>
                <th>Name</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((txn) => (
                <tr key={txn.id}>
                  <td>{txn.date}</td>
                  <td>{txn.institution || "Unknown"}</td>
                  <td>{txn.account_name}</td>
                  <td>{txn.name}</td>
                  <td>{formatCurrency(txn.amount, "USD")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
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

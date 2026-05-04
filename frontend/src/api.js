const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  constructor(message, { status, body } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body || {};
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message =
      payload.message ||
      payload.error ||
      payload.details ||
      "Request failed";
    throw new ApiError(message, { status: response.status, body: payload });
  }

  return payload;
}

export function createLinkToken() {
  return request("/plaid/link-token", { method: "POST", body: "{}" });
}

export function exchangePublicToken(publicToken, institutionName) {
  return request("/plaid/exchange-token", {
    method: "POST",
    body: JSON.stringify({
      public_token: publicToken,
      institution_name: institutionName,
    }),
  });
}

export function syncData() {
  return request("/plaid/sync", { method: "POST", body: "{}" });
}

export function getSyncStatus() {
  return request("/plaid/sync-status");
}

export function getAccounts() {
  return request("/accounts");
}

/**
 * @param {Record<string, string | number | boolean | undefined | null>} [params]
 */
export function getTransactions(params) {
  const search = new URLSearchParams();
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === "") continue;
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return request(`/transactions${qs ? `?${qs}` : ""}`);
}

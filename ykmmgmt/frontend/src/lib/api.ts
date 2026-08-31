/**
 * Central API client — sends credentials with every request and handles
 * silent token refresh on 401.
 *
 * All backend calls should go through `apiFetch` instead of the raw
 * `fetch`: when the access token expires, one silent POST /api/auth/refresh
 * is attempted and the original request retried. If the refresh also
 * fails, an `auth:expired` event is dispatched (AuthContext listens and
 * clears state / redirects to /login).
 */

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  // Single-flight: concurrent 401s share one refresh call
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "include",
        });
        return res.ok;
      } catch {
        return false;
      } finally {
        // Reset on the next microtask so late listeners don't reuse it
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const doFetch = () =>
    fetch(input, {
      ...init,
      credentials: "include",
    });

  let res = await doFetch();

  if (res.status === 401 && !(typeof input === "string" && input.includes("/api/auth/"))) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      res = await doFetch();
    } else {
      window.dispatchEvent(new CustomEvent("auth:expired"));
    }
  }

  return res;
}

import { clearSession, getSession, getAccessToken, refreshAccessToken } from "./auth";

export class ApiError extends Error {
  status: number;
  body: any;

  constructor(message: string, status = 0, body: any = null) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch(
  path: string,
  options: RequestInit = {},
) {
  const session = getSession();

  const headers = new Headers(options.headers);

  // Omit Content-Type for FormData so the browser can set the boundary automatically
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const accessToken = getAccessToken() || session?.token;

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    throw new Error("NEXT_PUBLIC_API_URL n'est pas configurée.");
  }

  const response = await fetch(`${apiUrl}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // Try a single refresh attempt using refresh token cookie
    const refreshed = await refreshAccessToken().catch(() => null);

    if (refreshed) {
      // retry original request once with new token
      const retryHeaders = new Headers(options.headers);
      retryHeaders.set("Content-Type", "application/json");

      const newToken = getAccessToken() || getSession()?.token;
      if (newToken) retryHeaders.set("Authorization", `Bearer ${newToken}`);

      const retryResp = await fetch(`${apiUrl}${path}`, {
        ...options,
        headers: retryHeaders,
      });

      if (retryResp.ok) return retryResp.json();

      // fallthrough to error handling
    }

    clearSession();

    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }

    throw new ApiError("Session expirée, veuillez vous reconnecter.", 401, null);
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);

    const message = (errorBody && (errorBody.detail || errorBody.message)) ||
      `HTTP ${response.status}`;

    throw new ApiError(message, response.status, errorBody);
  }

  return response.json();
}
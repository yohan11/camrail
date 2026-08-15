export type AuthSession = {
  token?: string;
  role: string;
  email: string;
};

const SESSION_KEY = "camrail_session";
// NOTE: Storing JWTs in JavaScript-accessible storage (localStorage) is
// vulnerable to XSS. Prefer httpOnly secure cookies set by the backend.
// As an intermediate mitigation we use `sessionStorage` (lifetime tied to
// the browser tab) instead of `localStorage` to reduce persistence.
// NOTE: Storing JWTs in JavaScript-accessible storage is vulnerable to XSS.
// Prefer httpOnly secure cookies set by the backend. Here we keep the access
// token only in memory and persist only non-sensitive session info to
// `sessionStorage` (tab-lifetime). The app will attempt a refresh via
// `/auth/refresh` when needed.
let inMemoryToken: string | null = null;

function storageAvailable(): boolean {
  return typeof window !== "undefined" && !!window.sessionStorage;
}

export function saveSession(session: AuthSession): void {
  if (!storageAvailable()) return;

  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // best-effort: swallow storage errors
  }
}

export function getSession(): AuthSession | null {
  if (!storageAvailable()) return null;

  try {
    const storedSession = sessionStorage.getItem(SESSION_KEY);

    if (!storedSession) return null;

    return JSON.parse(storedSession) as AuthSession;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  inMemoryToken = null;

  if (!storageAvailable()) return;

  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // ignore
  }
}

export function setAccessToken(token: string | null) {
  inMemoryToken = token;
}

export function getAccessToken(): string | null {
  const session = getSession();
  return session?.token || inMemoryToken;
}

export async function refreshAccessToken(): Promise<AuthSession | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) return null;

  try {
    const resp = await fetch(`${apiUrl}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!resp.ok) return null;

    const data = await resp.json();

    if (data.access_token) {
      setAccessToken(data.access_token);
    }

    const session: AuthSession = {
      token: undefined,
      role: data.role || "",
      email: data.email || "",
    };

    saveSession(session);

    return session;
  } catch {
    return null;
  }
}

export async function login(
  username: string,
  password: string,
): Promise<AuthSession> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    throw new Error("NEXT_PUBLIC_API_URL n'est pas configurée.");
  }

  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);

  const response = await fetch(`${apiUrl}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: body.toString(),
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Email ou mot de passe incorrect");
    }

    const errorBody = await response.json().catch(() => ({}));

    throw new Error(
      errorBody.detail || "Erreur lors de la connexion.",
    );
  }

  const data = await response.json();

  const session: AuthSession = {
    token: data.access_token,
    role: data.role,
    email: username,
  };

  saveSession(session);

  return session;
}
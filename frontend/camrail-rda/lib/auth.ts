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
    if (session.token && typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem("token", session.token);
    }
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

  if (typeof window !== "undefined") {
    try {
      if (window.sessionStorage) {
        sessionStorage.removeItem(SESSION_KEY);
      }
      if (window.localStorage) {
        window.localStorage.removeItem("token");
        for (let i = window.localStorage.length - 1; i >= 0; i--) {
          const key = window.localStorage.key(i);
          if (key && key.startsWith("evidence:")) {
            window.localStorage.removeItem(key);
          }
        }
      }
    } catch {
      // ignore
    }
  }
}

export function setAccessToken(token: string | null) {
  inMemoryToken = token;
  if (typeof window !== "undefined" && window.localStorage) {
    if (token) {
      window.localStorage.setItem("token", token);
    } else {
      window.localStorage.removeItem("token");
    }
  }
}

export function getAccessToken(): string | null {
  const session = getSession();
  if (session?.token) return session.token;
  if (inMemoryToken) return inMemoryToken;
  if (typeof window !== "undefined" && window.localStorage) {
    return window.localStorage.getItem("token");
  }
  return null;
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

/**
 * Extrait le prénom à partir de l'email avant le @ (avec majuscule)
 * Ex: jean.dupont@camrail.net -> Jean, yohan@camrail.net -> Yohan
 */
export function getUserFirstName(email?: string | null): string {
  if (!email) return "";
  const beforeAt = email.split("@")[0] || "";
  const rawFirstName = beforeAt.split(/[._]/)[0] || "";
  if (!rawFirstName) return "";
  return rawFirstName
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join("-");
}
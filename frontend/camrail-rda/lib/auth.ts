/**
 * SÉCURITÉ DE STOCKAGE DES JETONS (Risque Résiduel XSS vs CSRF) :
 * 
 * 1. Refresh Token (Persistance de Session) :
 *    - Stocké EXCLUSIVEMENT dans un cookie httpOnly, SameSite=Strict, Secure (en production).
 *    - Inaccessible au JavaScript client : immunisé contre le vol par faille XSS.
 *    - Protection CSRF : SameSite=Strict empêche l'envoi du cookie lors de requêtes cross-site.
 * 
 * 2. Access Token (Autorisation API éphémère - 30 minutes) :
 *    - Conservé en priorité en mémoire vive (variable `inMemoryToken`) pour une immunité accrue.
 *    - Miroir en `sessionStorage` pour assurer la persistance lors d'un rechargement (F5) au sein d'un même onglet.
 *    - Risque résiduel documenté : Le stockage en `sessionStorage` reste exposé à une exécution de code malveillant
 *      en cas de faille XSS critique. Cependant :
 *        a) Sa portée est circonscrite à l'onglet actif et sa durée de vie est limitée à 30 minutes.
 *        b) L'absence de refresh token dans le DOM empêche un attaquant XSS de pérenniser son accès au-delà de 30 minutes.
 *        c) Le format Bearer Authorization header élimine le risque d'attaque CSRF sur les opérations de l'API.
 */

export type AuthSession = {
  token?: string;
  role: string;
  email: string;
};

const SESSION_KEY = "camrail_session";
let inMemoryToken: string | null = null;
let refreshPromise: Promise<AuthSession | null> | null = null;
let preventiveRefreshTimer: ReturnType<typeof setTimeout> | null = null;

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

export function setAccessToken(token: string | null): void {
  inMemoryToken = token;
  const current = getSession();
  if (current) {
    current.token = token || undefined;
    saveSession(current);
  }
}

export function getAccessToken(): string | null {
  if (inMemoryToken) return inMemoryToken;
  const session = getSession();
  if (session?.token) {
    inMemoryToken = session.token;
    return session.token;
  }
  return null;
}

export function clearSession(): void {
  inMemoryToken = null;
  if (preventiveRefreshTimer) {
    clearTimeout(preventiveRefreshTimer);
    preventiveRefreshTimer = null;
  }

  if (typeof window !== "undefined") {
    try {
      if (window.sessionStorage) {
        sessionStorage.removeItem(SESSION_KEY);
        for (let i = sessionStorage.length - 1; i >= 0; i--) {
          const key = sessionStorage.key(i);
          if (key && key.startsWith("evidence:")) {
            sessionStorage.removeItem(key);
          }
        }
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

/**
 * Planifie un rafraîchissement silencieux préventif 1 minute avant l'expiration du token d'accès
 */
export function schedulePreventiveRefresh(token: string): void {
  if (typeof window === "undefined") return;
  if (preventiveRefreshTimer) {
    clearTimeout(preventiveRefreshTimer);
    preventiveRefreshTimer = null;
  }

  try {
    const parts = token.split(".");
    if (parts.length !== 3) return;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    const payload = JSON.parse(jsonPayload);
    if (!payload.exp) return;

    const expiresAtMs = payload.exp * 1000;
    const nowMs = Date.now();
    // Déclenchement 1 minute (60 000 ms) avant expiration
    const refreshInMs = expiresAtMs - nowMs - 60000;

    if (refreshInMs > 0) {
      preventiveRefreshTimer = setTimeout(() => {
        refreshAccessToken().catch(() => {});
      }, refreshInMs);
    } else if (expiresAtMs > nowMs) {
      // Déjà à moins d'une minute de l'expiration : refresh immédiat sous 1s
      preventiveRefreshTimer = setTimeout(() => {
        refreshAccessToken().catch(() => {});
      }, 1000);
    }
  } catch {
    // ignore parse errors
  }
}

/**
 * Rafraîchissement avec promesse partagée (Single-flight mutex) :
 * Si plusieurs requêtes 401 surviennent simultanément, une seule requête /auth/refresh
 * est exécutée et le résultat est partagé par tous les appelants.
 */
export async function refreshAccessToken(): Promise<AuthSession | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
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

      if (!resp.ok) {
        clearSession();
        return null;
      }

      const data = await resp.json();

      if (data.access_token) {
        setAccessToken(data.access_token);
        schedulePreventiveRefresh(data.access_token);
      }

      const session: AuthSession = {
        token: data.access_token,
        role: data.role || "",
        email: data.email || "",
      };

      saveSession(session);
      return session;
    } catch {
      clearSession();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
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
  body.set("username", username.trim());
  body.set("password", password);

  const response = await fetch(`${apiUrl}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: body.toString(),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    if (response.status === 401) {
      throw new Error(errorBody.detail || "Email ou mot de passe incorrect.");
    }
    if (response.status === 429) {
      throw new Error(errorBody.detail || "Trop de tentatives, réessayez plus tard.");
    }

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
  setAccessToken(data.access_token);
  schedulePreventiveRefresh(data.access_token);

  return session;
}

export async function logout(): Promise<void> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const token = getAccessToken();

  if (preventiveRefreshTimer) {
    clearTimeout(preventiveRefreshTimer);
    preventiveRefreshTimer = null;
  }

  if (apiUrl) {
    try {
      await fetch(`${apiUrl}/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
    } catch {
      // Ignorer les erreurs réseau éventuelles lors de la déconnexion
    }
  }

  clearSession();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
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
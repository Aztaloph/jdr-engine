/** Session API — lot B1 auth (client web). */

export type AuthRole = "player" | "gm";
export type AuthMode = "disabled" | "required";

export interface AuthSession {
  token: string;
  user_id: string;
  role: AuthRole;
  expires_at: string;
}

export type AuthProbeResult =
  | { status: "ready"; mode: AuthMode; session: AuthSession | null }
  | { status: "unreachable"; message: string };

const TOKEN_STORAGE_KEY = "jdr_api_token";

export function getStoredToken(): string | null {
  try {
    const raw = sessionStorage.getItem(TOKEN_STORAGE_KEY);
    return raw?.trim() || null;
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null): void {
  try {
    if (token?.trim()) {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, token.trim());
    } else {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    /* ignore */
  }
}

/** Fetch avec Bearer si token présent. */
export async function authFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getStoredToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}

export async function devLogin(
  userId: string,
  role: AuthRole,
): Promise<AuthSession> {
  const res = await fetch("/v1/auth/dev-login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId.trim(), role }),
  });
  const payload = (await res.json()) as {
    token?: string;
    user_id?: string;
    role?: AuthRole;
    expires_at?: string;
    error?: { message?: string };
  };
  if (!res.ok || !payload.token) {
    throw new Error(payload.error?.message ?? `Connexion refusée (HTTP ${res.status}).`);
  }
  const session: AuthSession = {
    token: payload.token,
    user_id: payload.user_id ?? userId.trim(),
    role: payload.role ?? role,
    expires_at: payload.expires_at ?? "",
  };
  setStoredToken(session.token);
  return session;
}

export async function logoutApi(): Promise<void> {
  try {
    await authFetch("/v1/auth/logout", { method: "POST" });
  } catch {
    /* ignore */
  }
  setStoredToken(null);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Détecte le mode auth API.
 *
 * - 401 sans session valide → auth **requise** (JDR_API_AUTH=1)
 * - 200 ``authenticated: false`` → auth **désactivée** (banc local)
 * - Erreur réseau → **unreachable** (ne pas confondre avec auth off)
 */
export async function probeAuth(): Promise<AuthProbeResult> {
  const token = getStoredToken();
  let res: Response;
  try {
    res = await authFetch("/v1/auth/me");
  } catch {
    return {
      status: "unreachable",
      message:
        "API injoignable — attendez « Uvicorn running » dans la fenêtre JDR API, puis réessayez.",
    };
  }
  if (res.status === 401) {
    setStoredToken(null);
    return { status: "ready", mode: "required", session: null };
  }
  if (!res.ok) {
    return {
      status: "unreachable",
      message: `API indisponible (HTTP ${res.status}) — vérifiez la fenêtre JDR API.`,
    };
  }
  const data = (await res.json()) as {
    authenticated?: boolean;
    user_id?: string;
    role?: AuthRole;
    expires_at?: string;
  };
  if (data.authenticated && token) {
    return {
      status: "ready",
      mode: "required",
      session: {
        token,
        user_id: data.user_id ?? "",
        role: data.role ?? "player",
        expires_at: data.expires_at ?? "",
      },
    };
  }
  return { status: "ready", mode: "disabled", session: null };
}

/** Sonde avec attente au démarrage (launcher_web_auth.bat). */
export async function probeAuthWithRetry(
  attempts = 20,
  delayMs = 500,
): Promise<AuthProbeResult> {
  for (let i = 0; i < attempts; i += 1) {
    const probe = await probeAuth();
    if (probe.status === "ready") {
      return probe;
    }
    if (i < attempts - 1) {
      await sleep(delayMs);
    }
  }
  return {
    status: "unreachable",
    message:
      "API toujours injoignable — lancez launcher_web_auth.bat et gardez la fenêtre « JDR API » ouverte.",
  };
}

export function isGmRole(
  mode: AuthMode,
  session: AuthSession | null,
): boolean {
  if (mode === "disabled") {
    return true;
  }
  return session?.role === "gm";
}

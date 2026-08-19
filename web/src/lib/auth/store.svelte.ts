/** État auth partagé — lot B1c. */
import {
  isGmRole,
  logoutApi,
  probeAuthWithRetry,
  type AuthMode,
  type AuthSession,
} from "./session";

export const authState = $state({
  ready: false,
  mode: "disabled" as AuthMode,
  session: null as AuthSession | null,
  probeError: null as string | null,
});

export function authIsGm(): boolean {
  return isGmRole(authState.mode, authState.session);
}

export async function initAuth(): Promise<void> {
  authState.ready = false;
  authState.probeError = null;
  const probe = await probeAuthWithRetry();
  if (probe.status === "unreachable") {
    authState.probeError = probe.message;
    authState.ready = true;
    return;
  }
  authState.mode = probe.mode;
  authState.session = probe.session;
  authState.probeError = null;
  authState.ready = true;
}

export async function logoutAndClear(): Promise<void> {
  await logoutApi();
  authState.session = null;
}

export function requireAuthRedirect(): string | null {
  if (!authState.ready || authState.probeError) {
    return null;
  }
  if (authState.mode === "required" && !authState.session) {
    return "/login";
  }
  return null;
}

export function setSessionAfterLogin(session: AuthSession): void {
  authState.mode = "required";
  authState.session = session;
  authState.probeError = null;
  authState.ready = true;
}

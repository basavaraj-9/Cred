"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { API_V1_PATH, BROWSER_API_BASE_URL } from "@/lib/config";
import { apiFetch, SessionIdentity, sessionIdentity, setSession } from "@/lib/http";

export function RuntimeSession() {
  const [user, setUser] = useState<SessionIdentity | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const update = () => setUser(sessionIdentity());
    window.addEventListener("runtime-session", update);
    return () => window.removeEventListener("runtime-session", update);
  }, []);
  async function login(event: React.FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      const response = await apiFetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/auth/token`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) throw new Error("Sign-in is unavailable. Please try again later.");
      const token = (await response.json()).access_token as string;
      setSession(token, null);
      const me = await apiFetch(`${BROWSER_API_BASE_URL}${API_V1_PATH}/auth/me`);
      if (!me.ok) throw new Error("Unable to load your account.");
      setSession(token, await me.json() as SessionIdentity);
    } catch (cause) { setSession(null, null); setError(cause instanceof Error ? cause.message : "Sign-in failed"); }
    finally { setPassword(""); setBusy(false); }
  }
  return <aside aria-label="Account">
    <p className="validation-warning">Research analytics remain non-production. Human credit approval is required.</p>
    {user ? <p>Signed in · {user.role} · {user.environment}
      {user.environment !== "production" && user.environment !== "staging" && <strong> · Development data</strong>}
      {" "}<Link href="/operations">Jobs and system status</Link>{" "}
      <button onClick={() => setSession(null, null)}>Sign out</button></p>
      : <form onSubmit={event => void login(event)}>
        <label>Email <input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required /></label>
        <label>Password <input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
        <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p>Sign in with an account provisioned by your administrator.</p>
      </form>}
    <p role="alert">{error}</p>
  </aside>;
}

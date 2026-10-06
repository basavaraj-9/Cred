import { BROWSER_API_BASE_URL } from "@/lib/config";

export type SessionIdentity = {
  user_id: string; role: string; environment: string; permissions: string[];
};
let accessToken: string | null = null;
let identity: SessionIdentity | null = null;

// Short-lived bearer credentials stay in memory and are cleared on reload/sign-out.
export function setSession(token: string | null, value: SessionIdentity | null) {
  accessToken = token;
  identity = value;
  if (typeof window !== "undefined") window.dispatchEvent(new Event("runtime-session"));
}
export function sessionIdentity() { return identity; }

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const url = new URL(input, BROWSER_API_BASE_URL);
  if (url.origin !== new URL(BROWSER_API_BASE_URL).origin) {
    throw new Error("Unexpected API destination");
  }
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let body = init.body;
  if (identity) {
    for (const name of ["actor_user_id", "actor_id"]) {
      if (url.searchParams.has(name)) url.searchParams.set(name, identity.user_id);
    }
    if (typeof body === "string" && headers.get("Content-Type")?.includes("application/json")) {
      const data = JSON.parse(body);
      for (const name of ["actor_user_id", "actor_id"]) {
        if (Object.hasOwn(data, name)) data[name] = identity.user_id;
      }
      body = JSON.stringify(data);
    }
  }
  const response = await fetch(url, { ...init, body, headers, cache: "no-store" });
  if (response.status === 401) {
    setSession(null, null);
    throw new Error("Sign in to continue. Your session may have expired.");
  }
  if (response.status === 403) throw new Error("Your account does not have access to this action or company.");
  if (response.status === 429) throw new Error("Request limit reached. Please try again in a minute.");
  return response;
}

export async function downloadArtifact(url: string, filename: string) {
  const response = await apiFetch(url);
  if (!response.ok) throw new Error("The artifact could not be downloaded.");
  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = objectUrl; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

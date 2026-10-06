"use client";

import { useSyncExternalStore } from "react";
import { sessionIdentity } from "@/lib/http";

function subscribe(listener: () => void) {
  window.addEventListener("runtime-session", listener);
  return () => window.removeEventListener("runtime-session", listener);
}

export function RuntimeAccess({ children }: { children: React.ReactNode }) {
  const identity = useSyncExternalStore(subscribe, sessionIdentity, () => null);
  // Unmount private workspaces on sign-out/expiry so cached component state is cleared.
  return identity ? children : <p role="status">Sign in to open your authorized workspaces.</p>;
}

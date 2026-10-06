"use client";
import { useSyncExternalStore } from "react";
import { sessionIdentity } from "@/lib/http";

function subscribe(listener: () => void) {
  window.addEventListener("runtime-session", listener);
  return () => window.removeEventListener("runtime-session", listener);
}
export function useRuntimeActor(): [string, (value: string) => void] {
  const id = useSyncExternalStore(subscribe, () => sessionIdentity()?.user_id ?? "", () => "");
  // Legacy forms display the authenticated actor. The API independently verifies it.
  return [id, () => {}];
}

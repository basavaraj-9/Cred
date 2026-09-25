const configuredUrl =
  process.env.API_INTERNAL_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000";

export const API_BASE_URL = configuredUrl.replace(/\/$/, "");
export const BROWSER_API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");
export const API_V1_PATH = "/api/v1";

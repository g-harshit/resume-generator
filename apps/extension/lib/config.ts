// Set at build time (WXT_* env vars); dev defaults otherwise.
export const API_URL: string = import.meta.env.WXT_API_URL ?? "http://localhost:8100";
export const WEB_URL: string = import.meta.env.WXT_WEB_URL ?? "http://localhost:3100";
export const APP_NAME: string = import.meta.env.WXT_APP_NAME ?? "Tailor";

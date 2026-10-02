// The login the website hands over (see entrypoints/background.ts). Kept in
// extension storage, which pages can't read.
const KEY = "rg:token";

export async function getToken(): Promise<string | null> {
  const stored = await browser.storage.local.get(KEY);
  return (stored[KEY] as string | undefined) ?? null;
}

export async function setToken(token: string | null) {
  if (token) await browser.storage.local.set({ [KEY]: token });
  else await browser.storage.local.remove(KEY);
}

export function onTokenChange(listener: (token: string | null) => void) {
  const handler = (changes: Record<string, { newValue?: unknown }>, area: string) => {
    if (area === "local" && KEY in changes) listener((changes[KEY]!.newValue as string | undefined) ?? null);
  };
  browser.storage.onChanged.addListener(handler);
  return () => browser.storage.onChanged.removeListener(handler);
}

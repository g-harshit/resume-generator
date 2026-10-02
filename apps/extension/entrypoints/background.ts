import { WEB_URL } from "@/lib/config";
import { setToken } from "@/lib/session";

export default defineBackground(() => {
  // Clicking the toolbar icon opens the side panel (and grants activeTab for that tab).
  void browser.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

  // The website's /extension/connect page sends the login here. The manifest's
  // externally_connectable already limits who can send; the origin is checked again
  // because a token is a credential.
  const web = new URL(WEB_URL);
  const allowed = new Set([web.origin]);
  // In dev the site is also reachable on 127.0.0.1 (as in the manifest's dev patterns).
  if (web.hostname === "localhost") allowed.add(`${web.protocol}//127.0.0.1:${web.port}`);
  browser.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
    const origin = sender.origin ?? (sender.url ? new URL(sender.url).origin : "");
    if (!allowed.has(origin)) {
      sendResponse({ ok: false, error: "not allowed" });
      return;
    }
    if (message?.type === "connect" && typeof message.token === "string") {
      void setToken(message.token).then(() => sendResponse({ ok: true }));
      return true; // async response
    }
    if (message?.type === "disconnect") {
      void setToken(null).then(() => sendResponse({ ok: true }));
      return true;
    }
    if (message?.type === "ping") sendResponse({ ok: true });
  });
});

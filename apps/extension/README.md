# QuickFit CV — Chrome extension

A side panel that reads the job posting in the current tab and tailors the user's
resume to it (WXT, React, Manifest V3).

## Builds

| Command | What | ID |
|---|---|---|
| `pnpm dev:extension` | Dev, against the local stack (API 8100, web 3100) | fixed `pjdd…` |
| `pnpm build:extension:prod` | Production, unpacked → `apps/extension/.output/chrome-mv3` | fixed `pjdd…` |
| `pnpm zip:extension:store` | Chrome Web Store upload (no `key`) → `.output/*-chrome.zip` | the Store's |

The fixed ID comes from the public key in `wxt.config.ts`; the website
(`NEXT_PUBLIC_EXTENSION_IDS`) and the API (`CORS_ORIGINS`) trust that ID and, once
published, the Store's.

## Load it unpacked

`chrome://extensions` → turn on **Developer mode** → **Load unpacked** → choose the
`chrome-mv3` folder. Click the toolbar icon on a job posting; "Sign in" opens the
website, which hands the login to the extension.

## Tests

- `pnpm --filter @rg/extension test` — job-description extraction (vitest + jsdom).
- `E2E_TOKEN=<local test account token> pnpm e2e:extension` — the whole flow in real
  Chromium (Playwright): sign-in handoff, reading a posting, tailoring, PDF download.
  Needs `make dev` running. Screenshots land in `e2e/out/`.

## Store listing

`store/LISTING.md` has every field of the Developer Dashboard, ready to paste, and
`store/` the icon, screenshots and promo tile.

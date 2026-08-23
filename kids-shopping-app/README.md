# 🎒 Back to School HQ

A shared back-to-school shopping dashboard for Aiden (5, size 7) and Aliya (3, size 3-4/4T).
Built with Vite + React, deployed on Netlify, shared list synced through a Netlify
Function backed by Netlify Blobs.

## How it works

- **Kid toggle** — switch between Aiden and Aliya; every size note, link, and
  filter follows the active kid.
- **Six Canadian retailers** — Old Navy, H&M, Zara, OshKosh B'gosh (Carter's
  OshKosh Canada), Joe Fresh, and Walmart. Retailers don't offer public
  stock APIs and actively block scraping, so the board is a curated catalog of
  typical back-to-school items; every card and list row links to a **live,
  size-scoped search on the retailer's Canadian site**, where real stock,
  price, and checkout live. The per-store size cheat-sheet (e.g. "H&M: 6-7Y or
  7-8Y" for Aiden) travels with every link.
- **Filters** — store, category, price band, colour, on-sale, text search, sort.
- **Shared list** — both parents sign in with the family PIN; picks sync
  across devices via `/api/list` (Netlify Function + Blobs, last-write-wins
  merge per entry). Without the PIN (or when running the plain Vite dev
  server) the app degrades gracefully to a device-local list.
- **Checkout** — the list is grouped by store with subtotals; open each item
  link, add to the store cart, then hit that store's Checkout button once.

## Configuration

| Env var | Purpose |
| --- | --- |
| `FAMILY_PIN` | Shared PIN required by `/api/list`. Unset = no auth (not recommended). |

## Local development

```bash
cd kids-shopping-app
npm install
npx netlify dev   # full stack incl. the function + blobs emulation
# or: npm run dev # UI only; list stays local to the browser
```

## Google SSO upgrade path

The PIN gate keeps things simple. If you want real Google sign-in later:
create a Google OAuth client (Google Cloud Console → Credentials), then either
use Google Identity Services on the login screen and have `/api/list` verify
the ID token against an allowlist of your two Gmail addresses, or drop in
Supabase Auth. The `profile` object in `src/App.jsx` is the only thing that
would change shape.

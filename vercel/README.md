# FXMacroData – FX Market Intelligence (Vercel / Next.js)

A Next.js example app that visualises FX market data from the
**[FXMacroData API](https://fxmacrodata.com)** — deployable to Vercel in one click.

> **The calendar tab is public, while precious metals and COT require an API key.**  
> Get paid access via [FXMacroData Subscribe](https://fxmacrodata.com/subscribe), then
> manage keys in [API management](https://fxmacrodata.com/api-management).

---

## Features

| Tab | What it shows | API key needed? |
|---|---|---|
| 💎 Precious Metals | Gold, silver & platinum price history with metrics | No |
| 📊 COT Positioning | CFTC Commitment of Traders net positions for 8 major FX futures | Yes |
| 📅 Economic Calendar | Upcoming economic data releases — previous, forecast & actual | No |

---

## Run locally

```bash
# 1. Install dependencies
npm install

# 2. (Optional) add your API key
cp .env.local.example .env.local
# then edit .env.local and set FXMACRODATA_API_KEY=your_key

# 3. Start the dev server
npm run dev
```

Open <http://localhost:3000> in your browser.

---

## Deploy to Vercel (free, one click)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Ffxmacrodata%2Fexamples%2Ftree%2Fmain%2Fvercel)

**Manual steps:**

1. Fork or copy this directory into a **public** GitHub repository.
2. Sign in at <https://vercel.com> with your GitHub account.
3. Click **Add New → Project**, import the repository, and set the
   **Root Directory** to `examples/vercel` (if you copied just this folder,
   skip this step).
4. *(Optional)* Add your API key as a Vercel environment variable:
   - In the project settings open **Settings → Environment Variables** and add:
     ```
     FXMACRODATA_API_KEY = your_key_here
     ```
   - The key is used server-side only — it is never exposed to the browser.
5. Click **Deploy** — a live `*.vercel.app` URL is generated automatically.

---

## How the API key is kept secure

The three Next.js API Route Handlers (`app/api/metals/`, `app/api/cot/`,
`app/api/calendar/`) act as a lightweight proxy.  Requests from the browser go
to `/api/*` on the same origin; the Route Handler adds the
`FXMACRODATA_API_KEY` environment variable before forwarding to
`https://fxmacrodata.com/api`.  The key is **never** sent to the browser.

Users can also paste a key directly into the UI input — it is passed through
the same proxy but stored only in React state (not `localStorage`) and cleared
on page refresh.

---

## API endpoints used

| Route handler | FXMacroData endpoint | Auth | Description |
|---|---|---|---|
| `GET /api/metals` | `GET /v1/commodities/{indicator}` | API key | Precious metal spot prices |
| `GET /api/cot` | `GET /v1/cot/{currency}` | API key | CFTC COT positioning |
| `GET /api/calendar` | `GET /v1/calendar/{currency}` | Free | Economic release calendar |

Full API reference: <https://fxmacrodata.com/documentation>

---

## Tech stack

| Library | Purpose |
|---|---|
| [Next.js 15](https://nextjs.org) | React framework + API Route Handlers |
| [React 18](https://react.dev) | UI rendering |
| [Recharts 2](https://recharts.org) | Line & bar charts |

---

## Links

- 🌐 [FXMacroData](https://fxmacrodata.com)
- 📖 [API Docs](https://fxmacrodata.com/documentation)
- 💳 [Subscribe](https://fxmacrodata.com/subscribe)
- 🔑 [Get an API key](https://fxmacrodata.com/api-management)

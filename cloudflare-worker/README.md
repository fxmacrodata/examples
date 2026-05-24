# FXMacroData Cloudflare Worker Example

Edge proxy + landing page for public FXMacroData endpoints.

## Run locally

```bash
npm install
npm run dev
```

## Deploy

```bash
npm run deploy
```

## Routes

- `/` - landing page with subscribe CTA
- `/usd/latest` - public USD latest values
- `/calendar/usd` - public USD calendar
- `/subscribe` - redirects to https://fxmacrodata.com/subscribe

## Key safety

- No real key included.
- If you need protected routes, add a Worker secret and append it server-side only.

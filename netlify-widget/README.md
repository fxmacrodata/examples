# FXMacroData Netlify Widget

A static widget landing page with Netlify Functions that proxy public FXMacroData endpoints.

## Run locally

```bash
npm install
npm run dev
```

## Deploy

- Import into Netlify
- Base dir: `netlify-widget/`
- Build command: `npm run build`
- Publish dir: `dist`

## Conversion path

- https://fxmacrodata.com/subscribe

## Key safety

- Example uses public USD endpoint only.
- For protected routes, configure environment variable in Netlify UI.
- Do not commit real keys.

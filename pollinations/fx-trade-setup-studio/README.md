# FX Trade Setup Studio (Pollinations App)

Trading-focused visual generator that turns structured FX setup inputs into
polished image cards using the Pollinations image API.

Built for:
- FX creators posting setups on X/Discord/Telegram
- Trade journals and weekly review decks
- Analysts who want a consistent visual style

## Why this app is showcase-fit

- Clear domain-specific workflow (FX trade setup -> visual card)
- Fast one-click generation of multiple variants
- No backend required; easy to deploy anywhere
- Explicit Pollinations attribution in UI and docs

## Run locally

```bash
python -m http.server 8080
```

Then open:
- http://localhost:8080/pollinations/fx-trade-setup-studio/

## Deploy options

- GitHub Pages
- Netlify (static)
- Vercel static
- Cloudflare Pages

## Pollinations integration

The app calls Pollinations image generation directly through generated URLs:

- `https://image.pollinations.ai/p/{prompt}?width=...&height=...&seed=...&nologo=true`

## Links

- Pollinations home: https://pollinations.ai
- Pollinations app showcase: https://pollinations.ai/apps
- FXMacroData: https://fxmacrodata.com

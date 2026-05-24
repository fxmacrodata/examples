# FXMacroData Flask Example

Simple Flask landing app for public USD macro data, designed for distribution and conversion.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:8080.

## Deploy

Use Render/Railway with start command:

```bash
gunicorn app:app
```

## Conversion path

Every view includes a direct CTA to:

- https://fxmacrodata.com/subscribe

## Key safety

- No API key required for this example.
- If you add protected endpoints, use `FXMACRODATA_API_KEY` as an env var only.
- Never commit `.env` with real keys.

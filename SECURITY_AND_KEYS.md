# Examples Security and Key Handling

This examples suite is intended for public GitHub distribution.

## Hard rules

- Never commit real API keys, tokens, or secrets.
- Never include screenshots with visible keys.
- Never put keys in client-side source files.
- Never write keys into README snippets as real values.

## Approved patterns

- Environment variables only: `FXMACRODATA_API_KEY`
- Host secret managers (Vercel, Netlify, Render, Cloudflare, Streamlit, HF)
- Optional user input fields that remain in memory (not localStorage)
- `.env.example` files with placeholders only

## Pre-publish checks

Run from repo root:

```bash
grep -RInE "(sk-|AIza|api_key\s*=\s*['\"][^'\"]+|FXMACRODATA_API_KEY\s*=\s*['\"][^'\"]+)" examples || true
```

Also verify:

- `.env` is gitignored
- Deploy logs do not echo secrets
- Server handlers append keys server-side only

## Incident response

If a key is exposed:

1. Revoke the key in API management immediately.
2. Remove committed secret from git history.
3. Rotate all downstream host variables.
4. Re-run scans and republish clean commits.

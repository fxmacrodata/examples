# Public Examples Repo Publishing Playbook

Target public repo: https://github.com/fxmacrodata/examples

Goal: maximize developer distribution and convert traffic to
https://fxmacrodata.com/subscribe.

## 1. Keep examples current

- Mirror app folders from this workspace `examples/` into the public repo.
- Every app must include:
  - clear product positioning
  - deploy steps
  - key-safety instructions
  - visible subscribe CTA

## 2. Add conversion touchpoints

In each app:

- Header or hero CTA: `Subscribe`
- Footer links: docs + subscribe
- Upgrade copy for protected endpoints (non-USD, COT, commodities)

## 3. Publish where builders discover tools

For each deployed app, submit to:

- Vercel templates/community examples
- Streamlit community apps
- Hugging Face Spaces
- Netlify examples
- Cloudflare Workers examples
- Plotly Dash community gallery
- Quant/finance communities and social channels

## 4. Track distribution performance

Use a simple sheet or issue template with:

- app name
- deployment URL
- community URL
- publish date
- click-through to subscribe
- signups attributed

## 5. Suggested weekly cadence

- Monday: ship one app update or new framework starter
- Tuesday: publish social thread + docs snippet
- Wednesday: submit to one directory/gallery
- Thursday: post short integration tutorial
- Friday: measure traffic and signups, keep top performers pinned

## 6. Safe copy-paste commands

```bash
# from the public examples repo
python -m pip install -r requirements.txt
npm install
```

Never include real keys in command snippets.

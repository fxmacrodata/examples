# FXMacroData - Conversational Dash MCP Monitor

A Plotly Dash 4.3+ example that exposes an FX dashboard through **Dash MCP**.
Users can explore the app visually in the browser or connect an MCP-compatible
assistant to the same app through `/_mcp`.

This example is based on the FXMacroData Public Macro Monitor workflow:

- FX spot chart for a selected pair
- Cross-pair correlation matrix
- Rolling risk-regime chart
- MCP-enabled Dash callback
- Custom MCP snapshot tool

Live reference app: <https://fxmacrodata.com/app-gallery/dash/public-macro-monitor>

---

## Requirements

```bash
pip install -r requirements.txt
```

Dash MCP requires Dash 4.3.0 or newer.

FX spot history requires a Professional API key. Keep it server-side:

```bash
set FXMACRODATA_API_KEY=YOUR_API_KEY
```

On macOS/Linux:

```bash
export FXMACRODATA_API_KEY=YOUR_API_KEY
```

The app also accepts `FXMD_API_KEY` as a fallback for local compatibility, but
`FXMACRODATA_API_KEY` is the preferred examples-repo variable.

---

## Run locally

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8050
```

The MCP endpoint is:

```text
http://127.0.0.1:8050/_mcp
```

---

## MCP client configuration

Some MCP clients use a JSON shape like this:

```json
{
  "mcpServers": {
    "fx-macro-monitor": {
      "type": "http",
      "url": "http://127.0.0.1:8050/_mcp"
    }
  }
}
```

The exact setup screen or command varies by client. Use HTTP transport and the
Dash `_mcp` URL for your running app.

Try prompts such as:

- "Use the FX Macro Monitor to summarize EUR/USD over the 3M window."
- "Switch the dashboard to USD/JPY and explain the risk-regime chart."
- "Compare EUR/USD with GBP/USD and summarize the correlation view."
- "Call `get_public_macro_monitor_snapshot` for EUR_USD with a 6M window."

---

## Deploy to Render

1. Fork or copy this repository.
2. Create a Render Web Service.
3. Set the root directory to `dash-mcp/`.
4. Use this start command:

```bash
gunicorn app:server
```

5. Add `FXMACRODATA_API_KEY` as an environment variable.

You can also use the included `render.yaml` blueprint.

---

## API endpoints used

| Endpoint | Auth | Description |
|---|---|---|
| `GET /v1/forex/{base}/{quote}` | API key | FX spot history for charting, correlations, and risk-regime analysis |

Full API reference: <https://fxmacrodata.com/documentation>

---

## Security

- Never commit real API keys.
- Keep `FXMACRODATA_API_KEY` in host environment variables or secret managers.
- Do not put API keys in client-side JavaScript, Dash component state, or URLs shown to users.

See the repo-wide key policy: [`../SECURITY_AND_KEYS.md`](../SECURITY_AND_KEYS.md).

---

## Links

- [FXMacroData](https://fxmacrodata.com)
- [API documentation](https://fxmacrodata.com/documentation)
- [Subscribe](https://fxmacrodata.com/subscribe)
- [Public Macro Monitor](https://fxmacrodata.com/app-gallery/dash/public-macro-monitor)

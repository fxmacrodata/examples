const API_BASE = 'https://fxmacrodata.com/api/v1';
const SUBSCRIBE_URL = 'https://fxmacrodata.com/subscribe';

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'public, max-age=300',
      'access-control-allow-origin': '*',
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === '/health') {
      return json({ ok: true });
    }

    if (url.pathname === '/subscribe') {
      return Response.redirect(SUBSCRIBE_URL, 302);
    }

    if (url.pathname === '/usd/latest') {
      const upstream = `${API_BASE}/announcements/usd/latest`;
      const res = await fetch(upstream, { cf: { cacheTtl: 300, cacheEverything: true } });
      const payload = await res.json();
      return json(payload, res.status);
    }

    if (url.pathname === '/calendar/usd') {
      const upstream = `${API_BASE}/calendar/usd`;
      const res = await fetch(upstream, { cf: { cacheTtl: 300, cacheEverything: true } });
      const payload = await res.json();
      return json(payload, res.status);
    }

    if (url.pathname === '/') {
      const html = `<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
    <title>FXMacroData Cloudflare Worker</title>
    <style>
      body{font-family:ui-sans-serif,system-ui,sans-serif;background:#ecfeff;color:#0f172a;margin:0}
      .wrap{max-width:820px;margin:24px auto;padding:0 16px}
      .card{background:white;border:1px solid #bae6fd;border-radius:12px;padding:18px}
      a.btn{display:inline-block;margin-top:8px;padding:10px 14px;border-radius:8px;background:#0f766e;color:white;text-decoration:none;font-weight:700}
      code{background:#e2e8f0;padding:2px 6px;border-radius:6px}
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <div class=\"card\">
        <h1>FXMacroData Edge Starter</h1>
        <p>Fast edge proxy for public endpoints using Cloudflare Workers.</p>
        <p>Try <code>/usd/latest</code> and <code>/calendar/usd</code>.</p>
        <a class=\"btn\" href=\"${SUBSCRIBE_URL}\" target=\"_blank\" rel=\"noopener noreferrer\">Subscribe for full API coverage</a>
      </div>
    </div>
  </body>
</html>`;
      return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8' } });
    }

    return json({ error: 'Not found' }, 404);
  },
};

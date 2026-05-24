import { NextResponse } from 'next/server';

const API_BASE = 'https://fxmacrodata.com/api';

/**
 * GET /api/calendar?currency=USD[&api_key=...]
 *
 * Proxies to the FXMacroData /v1/calendar/{currency} endpoint.
 * USD is served free of charge. Other currencies require a Professional API key.
 */
export async function GET(request) {
  const { searchParams } = new URL(request.url);

  const currency = searchParams.get('currency');
  const clientApiKey = searchParams.get('api_key');

  if (!currency) {
    return NextResponse.json({ error: 'currency is required' }, { status: 400 });
  }

  const apiKey = clientApiKey || process.env.FXMACRODATA_API_KEY;

  const upstream = new URL(
    `${API_BASE}/v1/calendar/${encodeURIComponent(currency.toLowerCase())}`,
  );
  if (apiKey) upstream.searchParams.set('api_key', apiKey);

  try {
    const res = await fetch(upstream.toString(), {
      next: { revalidate: 1800 },
    });
    const json = await res.json();

    if (!res.ok) {
      return NextResponse.json(
        { error: json.detail || `API error ${res.status}` },
        { status: res.status },
      );
    }

    return NextResponse.json(json);
  } catch {
    return NextResponse.json({ error: 'Failed to reach FXMacroData API' }, { status: 502 });
  }
}

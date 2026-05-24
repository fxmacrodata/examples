import { NextResponse } from 'next/server';

const API_BASE = 'https://fxmacrodata.com/api';

/**
 * GET /api/metals?indicator=gold&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD[&api_key=...]
 *
 * Proxies to the FXMacroData /v1/commodities/{indicator} endpoint.
 * The server-side FXMACRODATA_API_KEY env var is used if no api_key is
 * provided in the query string, keeping the key out of the browser.
 */
export async function GET(request) {
  const { searchParams } = new URL(request.url);

  const indicator = searchParams.get('indicator');
  const startDate = searchParams.get('start_date');
  const endDate = searchParams.get('end_date');
  const clientApiKey = searchParams.get('api_key');

  if (!indicator) {
    return NextResponse.json({ error: 'indicator is required' }, { status: 400 });
  }

  const apiKey = clientApiKey || process.env.FXMACRODATA_API_KEY;

  const upstream = new URL(`${API_BASE}/v1/commodities/${encodeURIComponent(indicator)}`);
  if (startDate) upstream.searchParams.set('start_date', startDate);
  if (endDate) upstream.searchParams.set('end_date', endDate);
  if (apiKey) upstream.searchParams.set('api_key', apiKey);

  try {
    const res = await fetch(upstream.toString(), {
      next: { revalidate: 3600 },
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

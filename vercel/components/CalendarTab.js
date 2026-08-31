'use client';

import { useState, useEffect, useCallback } from 'react';

const API_KEYS_URL = 'https://api.fxmacrodata.com-management';

const CURRENCIES = [
  { code: 'USD', flag: '🇺🇸', free: true },
  { code: 'EUR', flag: '🇪🇺', free: false },
  { code: 'GBP', flag: '🇬🇧', free: false },
  { code: 'JPY', flag: '🇯🇵', free: false },
  { code: 'AUD', flag: '🇦🇺', free: false },
  { code: 'CAD', flag: '🇨🇦', free: false },
  { code: 'CHF', flag: '🇨🇭', free: false },
  { code: 'NZD', flag: '🇳🇿', free: false },
  { code: 'CNY', flag: '🇨🇳', free: false },
  { code: 'NOK', flag: '🇳🇴', free: false },
  { code: 'SEK', flag: '🇸🇪', free: false },
  { code: 'DKK', flag: '🇩🇰', free: false },
  { code: 'PLN', flag: '🇵🇱', free: false },
  { code: 'KRW', flag: '🇰🇷', free: false },
  { code: 'SGD', flag: '🇸🇬', free: false },
  { code: 'HKD', flag: '🇭🇰', free: false },
  { code: 'BRL', flag: '🇧🇷', free: false },
  { code: 'MXN', flag: '🇲🇽', free: false },
];

const INDICATOR_LABELS = {
  policy_rate: 'Policy Rate',
  inflation: 'CPI Inflation',
  gdp: 'GDP Growth',
  unemployment: 'Unemployment',
  non_farm_payrolls: 'Non-Farm Payrolls',
  retail_sales: 'Retail Sales',
  pmi: 'PMI',
  trade_balance: 'Trade Balance',
};

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function fmtVal(v) {
  if (v == null || v === '') return '—';
  const n = Number(v);
  return isNaN(n) ? String(v) : n.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function relativeDay(iso) {
  if (!iso) return '';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(iso);
  target.setHours(0, 0, 0, 0);
  const diff = Math.round((target - today) / 86_400_000);
  if (diff === 0) return <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Today</span>;
  if (diff === 1) return <span style={{ color: 'var(--accent)' }}>Tomorrow</span>;
  if (diff === -1) return <span style={{ color: 'var(--text-dim)' }}>Yesterday</span>;
  if (diff > 0) return <span style={{ color: 'var(--text-muted)' }}>in {diff}d</span>;
  return <span style={{ color: 'var(--text-dim)' }}>{Math.abs(diff)}d ago</span>;
}

export default function CalendarTab({ apiKey }) {
  const [currency, setCurrency] = useState('USD');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const currMeta = CURRENCIES.find((c) => c.code === currency);
  const needsKey = !currMeta?.free;

  const load = useCallback(async () => {
    if (needsKey && !apiKey) return;
    setLoading(true);
    setError(null);

    const params = new URLSearchParams({ currency });
    if (apiKey) params.set('api_key', apiKey);

    try {
      const res = await fetch(`/api/calendar?${params}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
      setData(json.data || json.releases || json.events || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [currency, apiKey, needsKey]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      {/* Currency selector */}
      <div className="selector-row" style={{ marginBottom: '8px' }}>
        {CURRENCIES.map((c) => (
          <button
            key={c.code}
            className={`seg-btn${currency === c.code ? ' selected' : ''}`}
            onClick={() => setCurrency(c.code)}
            title={!c.free ? 'Requires API key' : 'Free — no API key needed'}
            style={
              !c.free && !apiKey
                ? { opacity: 0.5 }
                : {}
            }
          >
            {c.flag} {c.code}
          </button>
        ))}
      </div>

      {/* Key hint */}
      {needsKey && !apiKey && (
        <div className="state-box info" style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '16px', marginBottom: '8px' }}>🔑 API key required</div>
          <p>
            {currency} release calendar requires a{' '}
            <a href={API_KEYS_URL} target="_blank" rel="noopener noreferrer">
              Professional API key
            </a>
            . USD is always free — select it above to explore without a key.
          </p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="state-box">
          Loading {currMeta?.flag} {currency} release calendar…
        </div>
      )}

      {/* Error */}
      {error && <div className="state-box error">⚠ {error}</div>}

      {/* Table */}
      {!loading && !error && data.length > 0 && (
        <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Release Date</th>
                <th></th>
                <th>Indicator</th>
                <th style={{ textAlign: 'right' }}>Previous</th>
                <th style={{ textAlign: 'right' }}>Forecast</th>
                <th style={{ textAlign: 'right' }}>Actual</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => {
                const label =
                  row.indicator_label ||
                  INDICATOR_LABELS[row.indicator] ||
                  row.indicator ||
                  '—';

                const actual = row.actual ?? row.val ?? null;
                const forecast = row.forecast ?? null;
                const previous = row.previous ?? row.prev ?? null;

                let surprise = null;
                if (actual != null && forecast != null) {
                  surprise = Number(actual) - Number(forecast);
                }

                return (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>{fmtDate(row.date)}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{relativeDay(row.date)}</td>
                    <td>
                      <strong>{label}</strong>
                      {row.unit && (
                        <span style={{ color: 'var(--text-dim)', fontSize: '11px', marginLeft: '6px' }}>
                          {row.unit}
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>{fmtVal(previous)}</td>
                    <td style={{ textAlign: 'right' }}>{fmtVal(forecast)}</td>
                    <td style={{ textAlign: 'right' }}>
                      {actual != null ? (
                        <span
                          className={
                            surprise == null ? '' : surprise > 0 ? 'up' : surprise < 0 ? 'down' : ''
                          }
                        >
                          {fmtVal(actual)}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-dim)' }}>pending</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && data.length === 0 && (!needsKey || apiKey) && (
        <div className="state-box">No calendar entries found for {currency}.</div>
      )}

      {/* Caption */}
      {!loading && !error && data.length > 0 && (
        <p style={{ color: 'var(--text-dim)', fontSize: '11px', marginTop: '12px' }}>
          Showing {data.length} scheduled release{data.length !== 1 ? 's' : ''} for{' '}
          {currMeta?.flag} {currency}. Actual values turn green (beat) or red (miss) vs forecast.
        </p>
      )}
    </div>
  );
}

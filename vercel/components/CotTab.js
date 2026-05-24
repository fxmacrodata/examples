'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';

const API_KEYS_URL = 'https://fxmacrodata.com/api-management';

const CURRENCIES = [
  { code: 'EUR', flag: '🇪🇺', label: 'Euro' },
  { code: 'GBP', flag: '🇬🇧', label: 'British Pound' },
  { code: 'JPY', flag: '🇯🇵', label: 'Japanese Yen' },
  { code: 'AUD', flag: '🇦🇺', label: 'Australian Dollar' },
  { code: 'CAD', flag: '🇨🇦', label: 'Canadian Dollar' },
  { code: 'CHF', flag: '🇨🇭', label: 'Swiss Franc' },
  { code: 'NZD', flag: '🇳🇿', label: 'New Zealand Dollar' },
  { code: 'MXN', flag: '🇲🇽', label: 'Mexican Peso' },
];

const RANGES = [
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
];

function fmtK(v) {
  if (v == null) return '—';
  const n = Number(v);
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function shortDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.toLocaleString('default', { month: 'short' })} '${String(d.getFullYear()).slice(-2)}`;
}

export default function CotTab({ apiKey }) {
  const [currency, setCurrency] = useState('EUR');
  const [range, setRange] = useState(365);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!apiKey) return;
    setLoading(true);
    setError(null);

    const end = new Date().toISOString().slice(0, 10);
    const start = new Date(Date.now() - range * 86_400_000).toISOString().slice(0, 10);

    const params = new URLSearchParams({ currency, start_date: start, end_date: end, api_key: apiKey });

    try {
      const res = await fetch(`/api/cot?${params}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
      setData(json.data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [currency, range, apiKey]);

  useEffect(() => {
    load();
  }, [load]);

  const latest = data.length ? data[data.length - 1] : null;
  const prev = data.length > 1 ? data[data.length - 2] : null;
  const netChange =
    latest && prev
      ? Number(latest.net_positions ?? latest.net) - Number(prev.net_positions ?? prev.net)
      : null;

  const net = latest ? Number(latest.net_positions ?? latest.net ?? 0) : null;
  const currMeta = CURRENCIES.find((c) => c.code === currency);

  if (!apiKey) {
    return (
      <div className="state-box info">
        <div style={{ fontSize: '18px', marginBottom: '12px' }}>🔑 API key required</div>
        <p>
          COT positioning data requires a{' '}
          <a href={API_KEYS_URL} target="_blank" rel="noopener noreferrer">
            Professional API key
          </a>
          .
        </p>
        <p style={{ marginTop: '8px', fontSize: '13px', color: 'var(--text-muted)' }}>
          Paste your key in the top-right input to unlock COT data for 8 major FX futures.
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Controls */}
      <div className="selector-row">
        {CURRENCIES.map((c) => (
          <button
            key={c.code}
            className={`seg-btn${currency === c.code ? ' selected' : ''}`}
            onClick={() => setCurrency(c.code)}
            title={c.label}
          >
            {c.flag} {c.code}
          </button>
        ))}

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '2px' }}>
          {RANGES.map((r) => (
            <button
              key={r.days}
              className={`range-btn${range === r.days ? ' selected' : ''}`}
              onClick={() => setRange(r.days)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics */}
      {latest && net != null && (
        <div className="card-grid">
          <div className="metric-card">
            <div className="metric-label">Net Positions</div>
            <div className={`metric-value ${net >= 0 ? 'up' : 'down'}`}>
              {net >= 0 ? '+' : ''}{fmtK(net)}
            </div>
            <div className="metric-sub">{fmtDate(latest.date)} contracts</div>
          </div>

          {netChange != null && (
            <div className="metric-card">
              <div className="metric-label">Week-on-Week</div>
              <div className={`metric-value ${netChange >= 0 ? 'up' : 'down'}`}>
                {netChange >= 0 ? '+' : ''}{fmtK(netChange)}
              </div>
              <div className="metric-sub">contracts change</div>
            </div>
          )}

          {latest.long_positions != null && (
            <div className="metric-card">
              <div className="metric-label">Long Positions</div>
              <div className="metric-value up">{fmtK(latest.long_positions)}</div>
              <div className="metric-sub">contracts</div>
            </div>
          )}

          {latest.short_positions != null && (
            <div className="metric-card">
              <div className="metric-label">Short Positions</div>
              <div className="metric-value down">{fmtK(latest.short_positions)}</div>
              <div className="metric-sub">contracts</div>
            </div>
          )}
        </div>
      )}

      {/* Chart */}
      {loading && (
        <div className="state-box">
          Loading {currMeta?.flag} {currency} COT data…
        </div>
      )}

      {error && <div className="state-box error">⚠ {error}</div>}

      {!loading && !error && data.length > 0 && (
        <div className="card" style={{ padding: '16px 8px 8px' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '12px', marginBottom: '8px', paddingLeft: '8px' }}>
            {currMeta?.flag} {currency} · Net speculative positions (non-commercial, contracts) · CFTC COT report
          </p>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.map((d) => ({
                  date: d.date,
                  net: Number(d.net_positions ?? d.net ?? 0),
                }))}
                margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickLine={false}
                  tickFormatter={shortDate}
                  interval="preserveStartEnd"
                  minTickGap={60}
                />
                <YAxis
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickLine={false}
                  tickFormatter={fmtK}
                  width={56}
                />
                <ReferenceLine y={0} stroke="#374151" strokeWidth={1} />
                <Tooltip
                  contentStyle={{
                    background: '#111827',
                    border: '1px solid #374151',
                    borderRadius: '6px',
                    fontSize: '13px',
                  }}
                  labelStyle={{ color: '#9ca3af', marginBottom: '4px' }}
                  labelFormatter={(v) => fmtDate(v)}
                  formatter={(v) => [
                    `${v >= 0 ? '+' : ''}${Number(v).toLocaleString()} contracts`,
                    'Net positions',
                  ]}
                />
                <Bar
                  dataKey="net"
                  fill="#3b82f6"
                  radius={[2, 2, 0, 0]}
                  // color bars by sign
                  label={false}
                  isAnimationActive={false}
                  // recharts doesn't support per-bar fill via prop directly;
                  // use Cell pattern via custom shape or a single colour
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!loading && !error && data.length === 0 && apiKey && (
        <div className="state-box">No COT data returned for {currency}.</div>
      )}

      {/* Recent data table */}
      {!loading && !error && data.length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <h3 style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Recent Reports
          </h3>
          <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Report Date</th>
                  <th>Net Positions</th>
                  <th>Long</th>
                  <th>Short</th>
                </tr>
              </thead>
              <tbody>
                {[...data].reverse().slice(0, 10).map((row) => {
                  const rowNet = Number(row.net_positions ?? row.net ?? 0);
                  return (
                    <tr key={row.date}>
                      <td>{fmtDate(row.date)}</td>
                      <td className={rowNet >= 0 ? 'up' : 'down'}>
                        {rowNet >= 0 ? '+' : ''}{Number(rowNet).toLocaleString()}
                      </td>
                      <td className="up">{row.long_positions != null ? Number(row.long_positions).toLocaleString() : '—'}</td>
                      <td className="down">{row.short_positions != null ? Number(row.short_positions).toLocaleString() : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

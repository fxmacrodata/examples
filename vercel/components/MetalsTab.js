'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const METALS = [
  { key: 'gold',     label: 'Gold (XAU)',     color: '#f59e0b', unit: 'USD/oz' },
  { key: 'silver',   label: 'Silver (XAG)',   color: '#94a3b8', unit: 'USD/oz' },
  { key: 'platinum', label: 'Platinum (XPT)', color: '#c084fc', unit: 'USD/oz' },
];

const RANGES = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
  { label: '3Y', days: 1095 },
];

function fmt(v) {
  if (v == null) return '—';
  return `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
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

export default function MetalsTab({ apiKey }) {
  const [metal, setMetal] = useState('gold');
  const [range, setRange] = useState(365);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    const end = new Date().toISOString().slice(0, 10);
    const start = new Date(Date.now() - range * 86_400_000).toISOString().slice(0, 10);

    const params = new URLSearchParams({ indicator: metal, start_date: start, end_date: end });
    if (apiKey) params.set('api_key', apiKey);

    try {
      const res = await fetch(`/api/metals?${params}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
      setData(json.data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [metal, range, apiKey]);

  useEffect(() => {
    load();
  }, [load]);

  const meta = METALS.find((m) => m.key === metal);
  const latest = data.length ? data[data.length - 1] : null;
  const prev = data.length > 1 ? data[data.length - 2] : null;
  const change = latest && prev ? Number(latest.val) - Number(prev.val) : null;
  const changePct = change != null && prev ? (change / Number(prev.val)) * 100 : null;
  const high = data.length ? Math.max(...data.map((d) => Number(d.val))) : null;
  const low = data.length ? Math.min(...data.map((d) => Number(d.val))) : null;

  return (
    <div>
      {/* Metal selector */}
      <div className="selector-row">
        {METALS.map((m) => (
          <button
            key={m.key}
            className={`seg-btn${metal === m.key ? ' selected' : ''}`}
            style={metal === m.key ? { background: m.color, borderColor: m.color } : {}}
            onClick={() => setMetal(m.key)}
          >
            {m.label}
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
      {latest && (
        <div className="card-grid">
          <div className="metric-card">
            <div className="metric-label">Latest Close</div>
            <div className="metric-value" style={{ color: meta.color }}>{fmt(latest.val)}</div>
            <div className="metric-sub">{fmtDate(latest.date)} · {meta.unit}</div>
          </div>

          {change != null && (
            <div className="metric-card">
              <div className="metric-label">Daily Change</div>
              <div className={`metric-value ${change >= 0 ? 'up' : 'down'}`}>
                {change >= 0 ? '+' : ''}{fmt(change).replace('$', '')}
              </div>
              <div className="metric-sub">
                {changePct != null && `${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%`}
              </div>
            </div>
          )}

          {high != null && (
            <div className="metric-card">
              <div className="metric-label">Period High</div>
              <div className="metric-value">{fmt(high)}</div>
              <div className="metric-sub">{RANGES.find((r) => r.days === range)?.label} range</div>
            </div>
          )}

          {low != null && (
            <div className="metric-card">
              <div className="metric-label">Period Low</div>
              <div className="metric-value">{fmt(low)}</div>
              <div className="metric-sub">{RANGES.find((r) => r.days === range)?.label} range</div>
            </div>
          )}
        </div>
      )}

      {/* Chart */}
      {loading && <div className="state-box">Loading {meta.label}…</div>}

      {error && <div className="state-box error">⚠ {error}</div>}

      {!loading && !error && data.length > 0 && (
        <div className="card" style={{ padding: '16px 8px 8px' }}>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
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
                  tickFormatter={(v) => `$${Number(v).toLocaleString()}`}
                  width={76}
                  domain={['auto', 'auto']}
                />
                <Tooltip
                  contentStyle={{
                    background: '#111827',
                    border: '1px solid #374151',
                    borderRadius: '6px',
                    fontSize: '13px',
                  }}
                  labelStyle={{ color: '#9ca3af', marginBottom: '4px' }}
                  labelFormatter={(v) => fmtDate(v)}
                  formatter={(v) => [fmt(v), meta.label]}
                />
                <Line
                  type="monotone"
                  dataKey="val"
                  stroke={meta.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: meta.color }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!loading && !error && data.length === 0 && (
        <div className="state-box">
          No data returned.{!apiKey && ' Some metals may require an API key.'}
        </div>
      )}
    </div>
  );
}

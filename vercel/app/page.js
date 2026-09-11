'use client';

import { useState } from 'react';
import './globals.css';
import MetalsTab from '../components/MetalsTab';
import CotTab from '../components/CotTab';
import CalendarTab from '../components/CalendarTab';

const SITE_URL = 'https://fxmacrodata.com';
const DOCS_URL = 'https://fxmacrodata.com/documentation';
const SUBSCRIBE_URL = 'https://fxmacrodata.com/subscribe';
const API_KEYS_URL = 'https://api.fxmacrodata.com-management';

const TABS = [
  { key: 'metals', label: '💎 Precious Metals' },
  { key: 'cot', label: '📊 COT Positioning' },
  { key: 'calendar', label: '📅 Economic Calendar' },
];

export default function Home() {
  const [apiKey, setApiKey] = useState('');
  const [activeTab, setActiveTab] = useState('metals');

  return (
    <>
      {/* ── Nav bar ──────────────────────────────────── */}
      <nav className="navbar">
        <div className="wrapper navbar-inner">
          <a href={SITE_URL} target="_blank" rel="noopener noreferrer" className="navbar-brand">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="https://fxmacrodata.com/static/images/logo.png" alt="FXMacroData" />
            FX Market Intelligence
          </a>

          <div className="api-key-row">
            <input
              className="api-key-input"
              type="password"
              placeholder="API key (optional)"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value.trim())}
              aria-label="FXMacroData API key"
            />
            {!apiKey && (
              <a href={SUBSCRIBE_URL} target="_blank" rel="noopener noreferrer">
                <button className="btn-link">Subscribe</button>
              </a>
            )}
          </div>
        </div>
      </nav>

      {/* ── Main ─────────────────────────────────────── */}
      <main>
        <div className="wrapper">
          {/* Hero */}
          <section className="hero">
            <h1>FX Market Intelligence</h1>
            <p>
              Precious metals prices, CFTC COT positioning, and economic release
              calendars — all sourced from the{' '}
              <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">
                FXMacroData API
              </a>
              .<br />
              <span style={{ fontSize: '13px' }}>
                Gold, silver, and platinum data are free. COT and full calendar
                data require a paid plan. Start at{' '}
                <a href={SUBSCRIBE_URL} target="_blank" rel="noopener noreferrer">
                  FXMacroData Subscribe
                </a>
                {' '}and manage keys in{' '}
                <a href={API_KEYS_URL} target="_blank" rel="noopener noreferrer">API management</a>
                .
              </span>
            </p>
          </section>

          {/* Tabs */}
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={activeTab === t.key}
                className={`tab-btn${activeTab === t.key ? ' active' : ''}`}
                onClick={() => setActiveTab(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {activeTab === 'metals' && <MetalsTab apiKey={apiKey} />}
          {activeTab === 'cot' && <CotTab apiKey={apiKey} />}
          {activeTab === 'calendar' && <CalendarTab apiKey={apiKey} />}
        </div>
      </main>

      {/* ── Footer ────────────────────────────────────── */}
      <footer className="footer">
        <div className="wrapper">
          <a href={SITE_URL} target="_blank" rel="noopener noreferrer">
            FXMacroData
          </a>{' '}
          ·{' '}
          <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">
            API Docs
          </a>{' '}
          ·{' '}
          <a href={API_KEYS_URL} target="_blank" rel="noopener noreferrer">
            Get API key
          </a>
          {' '}·{' '}
          <a href={SUBSCRIBE_URL} target="_blank" rel="noopener noreferrer">
            Subscribe
          </a>
          <br />
          <span style={{ marginTop: '6px', display: 'block' }}>
            This example app is open-source — fork it, extend it, and deploy it
            on{' '}
            <a href="https://vercel.com" target="_blank" rel="noopener noreferrer">
              Vercel
            </a>{' '}
            for free.
          </span>
        </div>
      </footer>
    </>
  );
}

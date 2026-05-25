const styleHints = {
  "Institutional Brief": "clean editorial finance layout, dark navy background, restrained accents, high contrast typography",
  "Macro War Room": "cinematic trading desk mood, layered market screens, dramatic lighting, deep shadows",
  "Minimal Journal": "minimalist technical report style, white and graphite palette, subtle grid, clean chart aesthetic",
  "High-Volatility": "intense market turbulence visuals, strong reds and blues, kinetic motion streaks",
  "Calm Swing": "soft gradients, balanced composition, medium contrast, modern trading infographic style",
};

const POLLINATIONS_CLIENT_ID = "pk_zhpd0jwsCKfNyGQO";
const SESSION_KEY = "pollinations_user_api_key";

function byId(id) {
  return document.getElementById(id);
}

function rr(entry, stop, target) {
  const risk = Math.abs(entry - stop);
  const reward = Math.abs(target - entry);
  if (!risk) return "N/A";
  return `${(reward / risk).toFixed(2)}R`;
}

function buildPrompt(data) {
  return [
    `FX trade setup card for ${data.pair}, ${data.direction} bias, ${data.timeframe} timeframe.`,
    `Show clear entry ${data.entry}, stop ${data.stop}, TP1 ${data.tp1}, TP2 ${data.tp2}.`,
    `Display risk-reward ratios near ${rr(data.entry, data.stop, data.tp1)} and ${rr(data.entry, data.stop, data.tp2)}.`,
    `Thesis: ${data.thesis}.`,
    `Catalyst: ${data.catalyst}.`,
    `Visual direction: ${styleHints[data.style]}.`,
    "No broker logos, no watermark, no gibberish text, no extra paragraphs.",
    "Design should be premium, sharp, and social-media ready for FX trading communities.",
  ].join(" ");
}

function buildUrl(prompt, seed, aspect) {
  const [width, height] = aspect.split("x");
  const encoded = encodeURIComponent(prompt);
  return `https://image.pollinations.ai/p/${encoded}?width=${width}&height=${height}&seed=${seed}&nologo=true`;
}

function getAuthLink() {
  const params = new URLSearchParams({
    client_id: POLLINATIONS_CLIENT_ID,
    redirect_uri: `${window.location.origin}${window.location.pathname}`,
    scope: "usage",
    budget: "10",
    expiry: "30",
    state: "fx-trade-setup-studio",
  });
  return `https://enter.pollinations.ai/authorize?${params.toString()}`;
}

function persistApiKeyFromHash() {
  const hash = new URLSearchParams(window.location.hash.slice(1));
  const apiKey = hash.get("api_key");
  const err = hash.get("error");
  if (err) {
    updateAuthStatus(`Authorization failed: ${err}`);
  }
  if (apiKey && apiKey.startsWith("sk_")) {
    sessionStorage.setItem(SESSION_KEY, apiKey);
    updateAuthStatus("Connected: using your Pollinations account");
  }
  if (apiKey || err) {
    history.replaceState({}, "", window.location.pathname + window.location.search);
  }
}

function getUserApiKey() {
  return sessionStorage.getItem(SESSION_KEY) || "";
}

function updateAuthStatus(message) {
  const node = byId("authStatus");
  if (node) node.textContent = message;
}

function collectInputs() {
  return {
    pair: byId("pair").value,
    direction: byId("direction").value,
    timeframe: byId("timeframe").value,
    style: byId("style").value,
    entry: Number(byId("entry").value),
    stop: Number(byId("stop").value),
    tp1: Number(byId("tp1").value),
    tp2: Number(byId("tp2").value),
    thesis: byId("thesis").value.trim(),
    catalyst: byId("catalyst").value.trim(),
    aspect: byId("aspect").value,
    variants: Math.max(1, Math.min(8, Number(byId("variants").value) || 1)),
  };
}

function renderMetrics(data) {
  const root = byId("metrics");
  root.innerHTML = "";

  const items = [
    ["R:R to TP1", rr(data.entry, data.stop, data.tp1)],
    ["R:R to TP2", rr(data.entry, data.stop, data.tp2)],
    ["Direction", data.direction],
  ];

  items.forEach(([k, v]) => {
    const card = document.createElement("div");
    card.className = "metric";
    card.innerHTML = `<div class="k">${k}</div><div class="v">${v}</div>`;
    root.appendChild(card);
  });
}

function renderGallery(urls, seeds) {
  const gallery = byId("gallery");
  gallery.innerHTML = "";

  urls.forEach((url, i) => {
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <a href="${url}" target="_blank" rel="noreferrer">
        <img src="${url}" alt="FX setup variant ${i + 1}" loading="lazy" />
      </a>
      <div class="meta">Variant ${i + 1} • seed ${seeds[i]}</div>
    `;
    gallery.appendChild(card);
  });
}

function makeSeeds(count) {
  return Array.from({ length: count }, () => Math.floor(Math.random() * 999999) + 1);
}

function generate() {
  const data = collectInputs();
  const prompt = buildPrompt(data);
  const seeds = makeSeeds(data.variants);
  const apiKey = getUserApiKey();
  const urls = seeds.map((seed) => {
    let url = buildUrl(prompt, seed, data.aspect);
    if (apiKey) {
      url += `&api_key=${encodeURIComponent(apiKey)}`;
    }
    return url;
  });

  byId("promptPreview").textContent = prompt;
  renderMetrics(data);
  renderGallery(urls, seeds);
}

function setupAuthUi() {
  persistApiKeyFromHash();
  const current = getUserApiKey();
  if (current) {
    updateAuthStatus("Connected: using your Pollinations account");
  } else {
    updateAuthStatus("Not connected (guest mode)");
  }

  byId("connectBtn").addEventListener("click", () => {
    window.location.href = getAuthLink();
  });

  byId("disconnectBtn").addEventListener("click", () => {
    sessionStorage.removeItem(SESSION_KEY);
    updateAuthStatus("Not connected (guest mode)");
  });
}

byId("generateBtn").addEventListener("click", generate);
byId("randomBtn").addEventListener("click", generate);
setupAuthUi();

generate();

const API_URL = 'https://api.fxmacrodata.com/v1/announcements/usd/latest';

exports.handler = async () => {
  try {
    const res = await fetch(API_URL);
    const payload = await res.json();
    return {
      statusCode: res.status,
      headers: { 'content-type': 'application/json; charset=utf-8' },
      body: JSON.stringify(payload),
    };
  } catch (err) {
    return {
      statusCode: 502,
      headers: { 'content-type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ error: `Upstream fetch failed: ${err.message}` }),
    };
  }
};

# FXMacroData FastAPI Example

A minimal FastAPI app exposing ready-to-fork endpoints built on FXMacroData public data.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8010
```

Open http://localhost:8010.

## Endpoints

- `GET /api/usd/latest`
- `GET /api/usd/inflation?days=365`

## Conversion path

- https://fxmacrodata.com/subscribe

## Key safety

- This starter uses only public endpoints by default.
- For protected data, add `FXMACRODATA_API_KEY` at host env level only.

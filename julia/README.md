# FXMacroData + Fastback.jl

This example runs a release-aware EUR/USD backtest with [Fastback.jl](https://github.com/rbeeli/Fastback.jl) and the FXMacroData Julia client. It uses the publication timestamp of every economic release and revision, so a value is eligible for a simulated decision only after it was published.

The strategy is deliberately simple: when a newly available USD policy-rate decision is higher than the one before it, the account goes short EUR/USD (long USD); when it is lower, it goes long; an unchanged decision keeps the current position. It is a research example, not investment advice or a live-trading system.

## Run it

Install Julia 1.11 or later, then run:

```bash
cd julia
julia --project -e 'using Pkg; Pkg.instantiate()'
julia --project fastback_release_aware_backtest.jl
```

Set `FXMACRODATA_API_KEY` (or `FXMD_API_KEY`) in your shell before running the example. The client reads the key at runtime and sends it as an `X-API-Key` request header, never in the URL. Do not put keys in `Project.toml`, scripts, or notebooks.

The example needs a key: EUR/USD rates always require one, and without a key USD announcements are limited to the most recent 90 days, which is outside the 2024 to 2025 backtest window.

The project pins both unregistered Julia dependencies through Julia 1.11's
`[sources]` support.

Run the deterministic parser, pagination and look-ahead tests without making network calls:

```bash
julia --project test/runtests.jl
```

## How it avoids look-ahead bias

- `announcement_datetime` (Unix seconds, UTC) is the publication time. The row `date` is the reference period and is never treated as a publication time.
- The request uses `revisions=all`, and each revision that carries an `epoch` becomes its own timestamped event. A row without timestamped revisions falls back to its `announcement_datetime`.
- Daily bars are stamped at 00:00 UTC, and a release is applied only when its timestamp is strictly earlier, so a result published during the day is first used on the next day's bar.
- List endpoints return at most 100 rows per request, so both the release history and the FX history are read page by page until `pagination.has_more` is false.

## Key handling

The example gives the client a small request wrapper around `HTTP.get`. It does not follow redirects, because HTTP.jl would otherwise re-send the `X-API-Key` header to the redirect target. It also removes the key from any transport error message before rethrowing it.

## Capability coverage

This is a consumer example for a data-independent backtesting library, so data
access remains in the standalone FXMacroData Julia client rather than being
embedded in Fastback.

| FXMacroData capability | Fastback workflow | Authentication | Status |
| --- | --- | --- | --- |
| Data catalogue | Select indicator names before a run | No key needed | Available through `data_catalogue` in FXMacroData.jl |
| Macro indicator history | Point-in-time policy-rate events | USD for the last 90 days without a key; otherwise a key | Used by this example |
| Release calendar | Event schedule for blackout rules | USD without a key | Available through `release_calendar` in FXMacroData.jl |
| FX spot history | Daily EUR/USD valuation bars | API key | Used by this example |
| COT positioning | Weekly strategy feature | USD without a key | Available through `cot` in FXMacroData.jl |
| Commodities | Macro-context time series | API key | Available through `commodity` in FXMacroData.jl |

For the API client source and endpoint coverage, see [FXMacroData.jl](https://github.com/fxmacrodata/FXMacroData.jl). Explore the [FXMacroData API documentation](https://fxmacrodata.com/documentation?utm_source=github&utm_medium=referral&utm_campaign=examples&utm_content=julia-fastback) or [subscribe for protected datasets](https://fxmacrodata.com/subscribe?utm_source=github&utm_medium=referral&utm_campaign=examples&utm_content=julia-fastback).

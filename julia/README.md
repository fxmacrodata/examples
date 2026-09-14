# FXMacroData + Fastback.jl

This example runs a release-aware EUR/USD backtest with [Fastback.jl](https://github.com/rbeeli/Fastback.jl) and the FXMacroData Julia client. It uses the source timestamp of every economic release and revision, so a value is eligible for a simulated decision only after it was published.

The strategy is deliberately simple: it changes a simulated EUR/USD position when a newly available USD policy-rate observation differs from the preceding one. It is a research example, not investment advice or a live-trading system.

## Run it

Install Julia 1.11 or later, then run:

```bash
cd julia
julia --project -e 'using Pkg; Pkg.instantiate()'
julia --project fastback_release_aware_backtest.jl
```

Set `FXMACRODATA_API_KEY` (or `FXMD_API_KEY`) in your shell before running the example. The client reads the key at runtime and sends it only as an `api_key` query parameter; do not put keys in `Project.toml`, scripts, or notebooks.

The project pins both unregistered Julia dependencies through Julia 1.11's
`[sources]` support. The macro release history is part of FXMacroData's public
USD baseline, while the EUR/USD price history used by the backtest requires an
API key.

Run the deterministic parser and look-ahead tests without making network calls:

```bash
julia --project test/runtests.jl
```

## How it avoids look-ahead bias

- The client requests `revisions=all` and expands each nested `{epoch, val}` revision into a timestamped event.
- The loop applies a release only when its timestamp is strictly earlier than the daily valuation timestamp, so same-day daily bars cannot use a result published later that day.
- It consumes FXMacroData's daily reference rates and processes orders only inside Fastback's simulated account.

## Capability coverage

This is a consumer example for a data-independent backtesting library, so data
access remains in the standalone FXMacroData Julia client rather than being
embedded in Fastback.

| FXMacroData capability | Fastback workflow | Authentication | Status |
| --- | --- | --- | --- |
| Discovery/catalogue | Select indicator names before a run | Public USD | Available through `data_catalogue` in FXMacroData.jl |
| Macro indicator history | Point-in-time policy-rate events | Public USD | Used by this example |
| Release calendar | Event schedule for blackout rules | Public USD | Available through `release_calendar` in FXMacroData.jl |
| Event predictions | Optional strategy feature | Verify current service access | Not used by this focused example |
| Macro news | Optional text/context feature | Verify current service access | Not used by this focused example |
| FX spot history | Daily EUR/USD valuation bars | API key | Used by this example |
| FX market sessions | Intraday session filter | Verify current service access | Not applicable to daily bars |
| COT positioning | Weekly strategy feature | API key where required | Available through `cot` in FXMacroData.jl |
| Commodities | Macro-context time series | API key | Available through `commodity` in FXMacroData.jl |
| Seasonality | Optional research feature | Verify current service access | Not used by this focused example |

For the API client source and endpoint coverage, see [FXMacroData.jl](https://github.com/fxmacrodata/FXMacroData.jl). Explore the [FXMacroData API documentation](https://fxmacrodata.com/documentation) or [subscribe for protected datasets](https://fxmacrodata.com/subscribe).

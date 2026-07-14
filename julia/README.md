# FXMacroData + Fastback.jl

This example runs a release-aware EUR/USD backtest with [Fastback.jl](https://github.com/rbeeli/Fastback.jl) and the FXMacroData Julia client. It uses the source timestamp of every economic release and revision, so a value is eligible for a simulated decision only after it was published.

The strategy is deliberately simple: it changes a simulated EUR/USD position when a newly available USD policy-rate observation differs from the preceding one. It is a research example, not investment advice or a live-trading system.

## Run it

Install Julia 1.9 or later, then run:

```bash
cd julia
julia --project -e 'using Pkg; Pkg.instantiate()'
julia --project fastback_release_aware_backtest.jl
```

Set `FXMACRODATA_API_KEY` (or `FXMD_API_KEY`) in your shell before running the example. The client reads the key at runtime and sends it only as an `api_key` query parameter; do not put keys in `Project.toml`, scripts, or notebooks.

## How it avoids look-ahead bias

- The client requests `revisions=all`, preserving the publication time of each initial result and later revision.
- The loop applies a release only when its timestamp is strictly earlier than the daily valuation timestamp, so same-day daily bars cannot use a result published later that day.
- It consumes FXMacroData's daily reference rates and processes orders only inside Fastback's simulated account.

For the API client source and endpoint coverage, see [FXMacroData.jl](https://github.com/fxmacrodata/FXMacroData.jl). Explore the [FXMacroData API documentation](https://fxmacrodata.com/documentation) or [subscribe for protected datasets](https://fxmacrodata.com/subscribe).

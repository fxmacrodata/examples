using Dates
using Fastback
using FXMacroData
using HTTP

const START_DATE = Date(2024, 1, 1)
const END_DATE = Date(2025, 12, 31)
const POSITION_SIZE_EUR = 10_000.0
const PAGE_SIZE = 100
const MAX_PAGES = 200

"""Return the first non-empty value for any of `keys` in an API row."""
function row_value(row, keys)
    for key in keys
        value = get(row, key, nothing)
        if value !== nothing && value != ""
            return value
        end
    end
    return nothing
end

"""Parse a daily observation date from an FXMacroData row."""
function observation_date(row)
    value = row_value(row, ("date", "observation_date", "timestamp"))
    value === nothing && throw(ArgumentError("FX row does not contain a date"))
    return Date(first(split(String(value), 'T')))
end

"""Parse a Unix epoch or ISO-8601 timestamp as a UTC `DateTime`."""
function publication_time_value(value)
    value isa DateTime && return value
    value isa Date && return DateTime(value)
    value isa Number && return unix2datetime(Float64(value))

    text = String(value)
    epoch = tryparse(Float64, text)
    epoch !== nothing && return unix2datetime(epoch)

    normalized = replace(text, r"Z$" => "")
    offset = match(r"^(.*)([+-])(\d\d):(\d\d)$", normalized)
    offset === nothing && return DateTime(normalized)

    local_time = DateTime(offset.captures[1])
    displacement = Hour(parse(Int, offset.captures[3])) + Minute(parse(Int, offset.captures[4]))
    return offset.captures[2] == "+" ? local_time - displacement : local_time + displacement
end

"""Parse a numeric field while preserving API values represented as JSON strings."""
function numeric_value(value)
    value isa Number && return Float64(value)
    return parse(Float64, String(value))
end

"""
Normalise API release rows into timestamp-ordered values, including revisions.

`announcement_datetime` is the publication time (Unix seconds, UTC). The row
`date` is the reference period and is never used as a publication time. With
`revisions=all`, each revision that carries an `epoch` becomes its own event.
A row whose revisions carry no `epoch` falls back to the row's own
`announcement_datetime` and value.
"""
function policy_rate_events(rows)
    events = NamedTuple{(:released_at, :value),Tuple{DateTime,Float64}}[]
    for row in rows
        revision_events = 0
        revisions = get(row, "revisions", nothing)
        if revisions isa AbstractVector
            for revision in revisions
                released_at = get(revision, "epoch", nothing)
                actual = row_value(revision, ("val", "value"))
                (released_at === nothing || actual === nothing) && continue
                push!(
                    events,
                    (released_at=publication_time_value(released_at), value=numeric_value(actual)),
                )
                revision_events += 1
            end
        end
        revision_events > 0 && continue

        released_at = get(row, "announcement_datetime", nothing)
        actual = row_value(row, ("val", "value"))
        (released_at === nothing || actual === nothing) && continue
        push!(events, (released_at=publication_time_value(released_at), value=numeric_value(actual)))
    end
    sort!(events; by=event -> event.released_at)
    unique!(events)
    return events
end

"""Normalise daily FX rows into date-ordered EUR/USD valuation bars."""
function fx_bars(rows)
    bars = NamedTuple{(:date, :price),Tuple{Date,Float64}}[]
    for row in rows
        price = row_value(row, ("val", "value", "rate", "close"))
        price === nothing && continue
        push!(bars, (date=observation_date(row), price=numeric_value(price)))
    end
    sort!(bars; by=bar -> bar.date)
    return bars
end

"""
Return the target EUR/USD quantity after the latest policy-rate event.

A higher USD policy rate than the one before it opens a short EUR/USD position
(long USD), a lower rate opens a long one, and an unchanged decision keeps the
current position.
"""
function target_quantity(active_rate, preceding_rate, held_quantity)
    (active_rate === nothing || preceding_rate === nothing) && return held_quantity
    active_rate == preceding_rate && return held_quantity
    return active_rate > preceding_rate ? -POSITION_SIZE_EUR : POSITION_SIZE_EUR
end

"""
Read every page of a list endpoint.

List endpoints return at most 100 rows per request, so the loop follows
`pagination.next_offset` until `pagination.has_more` is false.
"""
function fetch_all(client, path; params=Dict{String,Any}())
    rows = Any[]
    offset = 0
    for _ in 1:MAX_PAGES
        page_params = Dict{String,Any}(params)
        page_params["limit"] = PAGE_SIZE
        page_params["offset"] = offset
        payload = get_json(client, path; params=page_params)
        data = get(payload, "data", Any[])
        data isa AbstractVector || throw(ArgumentError("FXMacroData response data must be an array"))
        append!(rows, data)

        pagination = get(payload, "pagination", nothing)
        pagination isa AbstractDict || return rows
        get(pagination, "has_more", false) == true || return rows
        next_offset = get(pagination, "next_offset", nothing)
        next_offset isa Integer && next_offset > offset ||
            throw(ArgumentError("FXMacroData pagination did not advance past offset $(offset)"))
        offset = next_offset
    end
    throw(ArgumentError("Stopped after $(MAX_PAGES) pages of $(path)"))
end

"""
Wrap `HTTP.get` so the API key stays on the API host and out of error text.

Redirects are not followed, because HTTP.jl would re-send the `X-API-Key`
header to the redirect target. Transport errors are rethrown with the key
removed from the message.
"""
function guarded_request(api_key)
    return function (url; kwargs...)
        response = try
            HTTP.get(url; kwargs..., redirect=false)
        catch err
            message = sprint(showerror, err)
            api_key === nothing || (message = replace(message, api_key => "***"))
            throw(ErrorException("Request to the FXMacroData API failed: " * message))
        end
        300 <= response.status < 400 && throw(ErrorException(
            "The FXMacroData API answered with HTTP $(response.status); the redirect was not followed.",
        ))
        return response
    end
end

"""Run the release-aware EUR/USD policy-rate demonstration in a Fastback account."""
function run_backtest(; start_date=START_DATE, end_date=END_DATE)
    api_key = resolve_api_key()
    api_key === nothing && throw(ArgumentError(
        "Set FXMACRODATA_API_KEY before running this example. EUR/USD rates and " *
        "USD history older than 90 days need an API key.",
    ))
    api_key = String(strip(api_key))
    client = Client(;
        api_key=api_key,
        base_url="https://api.fxmacrodata.com",
        request=guarded_request(api_key),
    )
    dates = Dict{String,Any}(
        "start_date" => Dates.format(start_date, dateformat"yyyy-mm-dd"),
        "end_date" => Dates.format(end_date, dateformat"yyyy-mm-dd"),
    )
    release_rows = fetch_all(
        client,
        "/v1/announcements/usd/policy_rate";
        params=merge(dates, Dict{String,Any}("revisions" => "all")),
    )
    price_rows = fetch_all(client, "/v1/forex/eur/usd"; params=dates)

    events = policy_rate_events(release_rows)
    bars = fx_bars(price_rows)
    isempty(events) && throw(ArgumentError("No policy-rate releases returned for the selected period"))
    isempty(bars) && throw(ArgumentError("No EUR/USD observations returned for the selected period"))

    account = Account(
        ;
        funding=AccountFunding.Margined,
        base_currency=CashSpec(:USD),
        broker=FlatFeeBroker(; pct=0.0002),
    )
    usd = cash_asset(account, :USD)
    deposit!(account, :USD, 100_000.0)
    eurusd = register_instrument!(account, spot_instrument(Symbol("EUR/USD"), :EUR, :USD))
    collect_equity, equity_history = periodic_collector(Float64, Day(1))

    event_index = 1
    active_policy_rate = nothing
    preceding_policy_rate = nothing
    held_quantity = 0.0

    for bar in bars
        # Daily bars are stamped at 00:00 UTC, so only releases published
        # before the bar's date can drive that day's decision.
        valuation_time = DateTime(bar.date)
        while event_index <= length(events) && events[event_index].released_at < valuation_time
            preceding_policy_rate = active_policy_rate
            active_policy_rate = events[event_index].value
            event_index += 1
        end

        desired_quantity = target_quantity(active_policy_rate, preceding_policy_rate, held_quantity)
        if desired_quantity != held_quantity
            delta = desired_quantity - held_quantity
            order = Order(oid!(account), eurusd, valuation_time, bar.price, delta)
            fill_order!(
                account,
                order;
                dt=valuation_time,
                fill_price=bar.price,
                bid=bar.price,
                ask=bar.price,
                last=bar.price,
            )
            held_quantity = desired_quantity
        end

        update_marks!(account, eurusd, valuation_time, bar.price, bar.price, bar.price)
        if should_collect(equity_history, valuation_time)
            collect_equity(valuation_time, equity(account, usd))
        end
    end

    return (account=account, equity_history=equity_history, releases_processed=event_index - 1)
end

if abspath(PROGRAM_FILE) == @__FILE__
    result = run_backtest()
    println("Processed $(result.releases_processed) policy-rate releases.")
    println("Final simulated equity: $(equity(result.account, cash_asset(result.account, :USD))) USD")
end

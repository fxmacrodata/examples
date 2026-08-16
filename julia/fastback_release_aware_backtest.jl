using Dates
using Fastback
using FXMacroData

const START_DATE = Date(2024, 1, 1)
const END_DATE = Date(2025, 12, 31)
const POSITION_SIZE_EUR = 10_000.0

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

"""Parse an announcement or revision timestamp from an FXMacroData row."""
function publication_time(row)
    value = row_value(row, ("epoch", "announcement_datetime", "published_at", "release_datetime"))
    value === nothing && throw(ArgumentError("Release row does not contain a publication timestamp"))
    return publication_time_value(value)
end

"""Parse a numeric field while preserving API values represented as JSON strings."""
function numeric_value(value)
    value isa Number && return Float64(value)
    return parse(Float64, String(value))
end

"""Normalise API release rows into timestamp-ordered values, including revisions."""
function policy_rate_events(rows)
    events = NamedTuple{(:released_at, :value),Tuple{DateTime,Float64}}[]
    for row in rows
        revisions = get(row, "revisions", nothing)
        if revisions isa AbstractVector && !isempty(revisions)
            for revision in revisions
                released_at = row_value(revision, ("epoch", "announcement_datetime"))
                actual = row_value(revision, ("val", "actual", "value"))
                released_at === nothing && continue
                actual === nothing && continue
                push!(
                    events,
                    (released_at=publication_time(revision), value=numeric_value(actual)),
                )
            end
            continue
        end

        released_at = row_value(row, ("announcement_datetime", "published_at", "release_datetime"))
        actual = row_value(row, ("val", "actual", "value"))
        released_at === nothing && continue
        actual === nothing && continue
        push!(events, (released_at=publication_time(row), value=numeric_value(actual)))
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

"""Run the release-aware EUR/USD policy-rate demonstration in a Fastback account."""
function run_backtest(; start_date=START_DATE, end_date=END_DATE)
    client = Client(; base_url="https://api.fxmacrodata.com")
    release_rows = announcements(
        client,
        "usd",
        "policy_rate";
        start_date=start_date,
        end_date=end_date,
        revisions="all",
    )
    price_rows = forex(client, "eur", "usd"; start_date=start_date, end_date=end_date)

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
        valuation_time = DateTime(bar.date)
        while event_index <= length(events) && events[event_index].released_at < valuation_time
            preceding_policy_rate = active_policy_rate
            active_policy_rate = events[event_index].value
            event_index += 1
        end

        if active_policy_rate !== nothing && preceding_policy_rate !== nothing
            desired_quantity = active_policy_rate > preceding_policy_rate ? POSITION_SIZE_EUR : -POSITION_SIZE_EUR
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

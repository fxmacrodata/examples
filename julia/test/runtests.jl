using Dates
using Test

include(joinpath(@__DIR__, "..", "fastback_release_aware_backtest.jl"))

@testset "FXMacroData release parsing" begin
    rows = [
        Dict{String,Any}(
            "date" => "2023-12-31",
            "announcement_datetime" => 1_704_067_200,
            "val" => 5.25,
            "revisions" => Any[
                Dict{String,Any}("epoch" => 1_704_067_200, "val" => 5.25),
                Dict{String,Any}("epoch" => 1_704_067_200, "val" => 5.25),
                Dict{String,Any}("epoch" => 1_704_153_600, "val" => "5.50"),
            ],
        ),
        Dict{String,Any}(
            "date" => "2024-01-31",
            "announcement_datetime" => "2024-02-01T14:30:00+00:00",
            "val" => "5.75",
        ),
        # Revisions without an epoch fall back to the row's announcement time.
        Dict{String,Any}(
            "date" => "2024-02-29",
            "announcement_datetime" => "2024-03-20T14:00:00-04:00",
            "val" => 5.5,
            "revisions" => Any[Dict{String,Any}("val" => 5.5)],
        ),
    ]

    events = policy_rate_events(rows)

    @test length(events) == 4
    @test events[1] == (released_at=DateTime(2024, 1, 1), value=5.25)
    @test events[2] == (released_at=DateTime(2024, 1, 2), value=5.50)
    @test events[3] == (released_at=DateTime(2024, 2, 1, 14, 30), value=5.75)
    @test events[4] == (released_at=DateTime(2024, 3, 20, 18, 0), value=5.5)
end

@testset "FXMacroData FX-bar parsing" begin
    rows = [
        Dict{String,Any}("date" => "2024-01-03T00:00:00Z", "val" => "1.0950"),
        Dict{String,Any}("date" => "2024-01-02", "value" => 1.0900),
    ]

    bars = fx_bars(rows)

    @test bars == [
        (date=Date(2024, 1, 2), price=1.0900),
        (date=Date(2024, 1, 3), price=1.0950),
    ]
end

@testset "daily bars cannot see same-day releases" begin
    release_time = publication_time_value("2024-03-20T18:00:00Z")

    @test !(release_time < DateTime(Date(2024, 3, 20)))
    @test release_time < DateTime(Date(2024, 3, 21))
end

@testset "position only changes when the rate changes" begin
    @test target_quantity(nothing, nothing, 0.0) == 0.0
    @test target_quantity(5.25, nothing, 0.0) == 0.0
    @test target_quantity(5.50, 5.25, 0.0) == -POSITION_SIZE_EUR
    @test target_quantity(5.25, 5.50, -POSITION_SIZE_EUR) == POSITION_SIZE_EUR
    @test target_quantity(5.25, 5.25, POSITION_SIZE_EUR) == POSITION_SIZE_EUR
end

@testset "every page is read and the key stays in the header" begin
    key = "test-key-not-real"
    requested = String[]
    headers_seen = Any[]
    pages = Dict(
        0 => """{"data": [{"date": "2024-01-03", "val": 1.095}],
                "pagination": {"has_more": true, "next_offset": 100}}""",
        100 => """{"data": [{"date": "2024-01-02", "val": 1.09}],
                  "pagination": {"has_more": false}}""",
    )
    function fake_request(url; headers=Pair{String,String}[], kwargs...)
        push!(requested, url)
        push!(headers_seen, headers)
        offset = parse(Int, match(r"offset=(\d+)", url).captures[1])
        return (status=200, body=Vector{UInt8}(pages[offset]))
    end
    client = Client(; api_key=key, base_url="https://api.fxmacrodata.com", request=fake_request)

    rows = fetch_all(client, "/v1/forex/eur/usd"; params=Dict{String,Any}("start_date" => "2024-01-01"))

    @test length(rows) == 2
    @test length(requested) == 2
    @test all(url -> occursin("limit=100", url), requested)
    @test all(url -> !occursin(key, url), requested)
    @test all(headers -> ("X-API-Key" => key) in headers, headers_seen)
end

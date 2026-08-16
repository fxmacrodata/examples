using Dates
using Test

include(joinpath(@__DIR__, "..", "fastback_release_aware_backtest.jl"))

@testset "FXMacroData release parsing" begin
    rows = [
        Dict{String,Any}(
            "announcement_datetime" => 1_704_067_200,
            "val" => 5.25,
            "revisions" => Any[
                Dict{String,Any}("epoch" => 1_704_067_200, "val" => 5.25),
                Dict{String,Any}("epoch" => 1_704_153_600, "val" => "5.50"),
            ],
        ),
        Dict{String,Any}(
            "announcement_datetime" => "2024-02-01T14:30:00+00:00",
            "val" => "5.75",
        ),
    ]

    events = policy_rate_events(rows)

    @test length(events) == 3
    @test events[1] == (released_at=DateTime(2024, 1, 1), value=5.25)
    @test events[2] == (released_at=DateTime(2024, 1, 2), value=5.50)
    @test events[3] == (released_at=DateTime(2024, 2, 1, 14, 30), value=5.75)
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

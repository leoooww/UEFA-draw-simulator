using Test
using Random
using DrawService

const CL = LEAGUES["CHAMPIONS_LEAGUE"]
const EL = LEAGUES["EUROPA_LEAGUE"]

@testset "league data" begin
    for lg in values(LEAGUES)
        @test length(lg.teams) == 36
        @test length(lg.index) == 36
    end
end

@testset "draw validity" begin
    for (lg, seed, order) in ((CL, 1, :by_pot), (CL, 2, :random), (EL, 3, :by_pot))
        r = run_draw(lg; seed, order)
        @test validate_draw(lg, r) == String[]
        @test length(unique(fixtures(r))) == 144
        @test r.solver_calls > 0
    end
end

@testset "determinism" begin
    a = run_draw(CL; seed = 42)
    b = run_draw(CL; seed = 42)
    c = run_draw(CL; seed = 43)
    @test a.host == b.host && a.visit == b.visit
    @test a.host != c.host || a.visit != c.visit
end

@testset "exhaustive selection reports options" begin
    r = run_draw(CL; seed = 7, selection = :enumeration)
    @test validate_draw(CL, r) == String[]
    drawn = filter(s -> !s.fixed, r.steps)
    @test !isempty(drawn) && all(s -> s.options !== nothing && s.options >= 1, drawn)
end

@testset "validator catches broken draws" begin
    r = run_draw(CL; seed = 5)
    broken = DrawResult(r.seed, copy(r.host), copy(r.visit), r.steps, r.solver_calls, r.seconds)
    broken.host[1, 1] = 0
    @test !isempty(validate_draw(CL, broken))
end

@testset "bad options are rejected" begin
    @test_throws ArgumentError run_draw(CL; seed = 1, order = :nope)
    @test_throws ArgumentError run_draw(CL; seed = 1, selection = :nope)
end

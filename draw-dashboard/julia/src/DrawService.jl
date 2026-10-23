"""
    DrawService

Pure-Julia core of the UEFA league-phase draw simulator (36 clubs, 4 pots, 8 matches each).

This is a side-effect-free port of `draw-backend/draw_matchups_first.jl`:
no globals, no file/stdin I/O, an explicit RNG, and the open-source SCIP solver
(the original defaulted to the licensed Gurobi).

Conventions
- Teams are numbered `1:36`; pot `p` holds teams `9(p-1)+1 : 9p`.
- A draw step for team `s` against pot `op` picks a pair `(h, a)`:
  `s` plays **at home** against `h` and **away** against `a`.
"""
module DrawService

using JuMP
using Random
import MathOptInterface as MOI
import SCIP

export Team, League, LEAGUES, DrawResult, Step, run_draw, validate_draw, fixtures, pot_of

# ----------------------------------------------------------------------------- data

struct Team
    club::String
    nationality::String
    elo::Int
    uefa::Float64
end

struct League
    key::String
    label::String
    teams::Vector{Team}                  # 36 teams, pot A first
    nat_id::Vector{Int}                  # nationality index of each team
    nat_names::Vector{String}
    nat_members::Vector{Vector{Int}}
    forbidden::Vector{Tuple{Int,Int}}    # (i, j) pairs that can never meet (same nationality, i == j)
    index::Dict{String,Int}
end

const POT_SIZE = 9
const N_POTS = 4
const N_TEAMS = POT_SIZE * N_POTS
const MAX_SAME_NATIONALITY = 2

pot_of(i::Int) = (i - 1) ÷ POT_SIZE + 1
pot_range(p::Int) = (POT_SIZE * (p - 1) + 1):(POT_SIZE * p)

function League(key::String, label::String, pots::NTuple{4,Vector{Team}})
    all(length(p) == POT_SIZE for p in pots) || error("every pot must hold $POT_SIZE teams")
    teams = reduce(vcat, pots)
    nat_names = sort!(unique(t.nationality for t in teams))
    nat_lookup = Dict(n => k for (k, n) in enumerate(nat_names))
    nat_id = [nat_lookup[t.nationality] for t in teams]
    members = [findall(==(k), nat_id) for k in eachindex(nat_names)]
    forbidden = [(i, j) for i in 1:N_TEAMS for j in 1:N_TEAMS if i == j || nat_id[i] == nat_id[j]]
    index = Dict(t.club => i for (i, t) in enumerate(teams))
    return League(key, label, teams, nat_id, nat_names, members, forbidden, index)
end

const CHAMPIONS_LEAGUE = League(
    "CHAMPIONS_LEAGUE", "Champions League",
    (
        [
            Team("Real", "Spain", 1985, 136), Team("ManCity", "England", 2057, 148),
            Team("Bayern", "Germany", 1904, 144), Team("PSG", "France", 1893, 116),
            Team("Liverpool", "England", 1908, 114), Team("Inter", "Italy", 1960, 101),
            Team("Dortmund", "Germany", 1874, 97), Team("Leipzig", "Germany", 1849, 97),
            Team("Barcelona", "Spain", 1894, 91),
        ],
        [
            Team("Leverkusen", "Germany", 1929, 90), Team("Atlético", "Spain", 1830, 89),
            Team("Atalanta", "Italy", 1879, 81), Team("Juventus", "Italy", 1839, 80),
            Team("Benfica", "Portugal", 1824, 79), Team("Arsenal", "England", 1957, 72),
            Team("Brugge", "Belgium", 1703, 64), Team("Shakhtar", "Ukraine", 1573, 63),
            Team("Milan", "Italy", 1821, 59),
        ],
        [
            Team("Feyenoord", "Netherlands", 1747, 57), Team("Sporting", "Portugal", 1824, 54.5),
            Team("Eindhoven", "Netherlands", 1794, 54), Team("Dinamo", "Croatia", 1584, 50),
            Team("Salzburg", "Austria", 1693, 50), Team("Lille", "France", 1785, 47),
            Team("Crvena", "Serbia", 1734, 40), Team("YB", "Switzerland", 1566, 34.5),
            Team("Celtic", "Scotland", 1646, 32),
        ],
        [
            Team("Bratislava", "Slovakia", 1703, 30.5), Team("Monaco", "France", 1780, 24),
            Team("Sparta", "Czech Republic", 1716, 22.5), Team("Aston Villa", "England", 1772, 20.86),
            Team("Bologna", "Italy", 1777, 18.056), Team("Girona", "Spain", 1791, 17.897),
            Team("Stuttgart", "Germany", 1795, 17.324), Team("Sturm Graz", "Austria", 1610, 14.5),
            Team("Brest", "France", 1685, 13.366),
        ],
    ),
)

const EUROPA_LEAGUE = League(
    "EUROPA_LEAGUE", "Europa League",
    (
        [
            Team("Roma", "Italy", 1812, 101), Team("Man Utd", "England", 1779, 92),
            Team("Porto", "Portugal", 1778, 77), Team("Ajax", "Netherlands", 1619, 67),
            Team("Rangers", "Scotland", 1618, 63), Team("Frankfurt", "Germany", 1697, 60),
            Team("Lazio", "Italy", 1785, 54), Team("Tottenham", "England", 1791, 54),
            Team("Slavia Praha", "Czech Republic", 1702, 53),
        ],
        [
            Team("Real Sociedad", "Spain", 1767, 51), Team("Olympiacos", "Greece", 1639, 50),
            Team("AZ Alkmaar", "Netherlands", 1591, 50), Team("Braga", "Portugal", 1636, 49),
            Team("Lyon", "France", 1713, 44), Team("PAOK", "Greece", 1639, 37),
            Team("Fenerbahçe", "Turkey", 1714, 36), Team("M. Tel-Aviv", "Israel", 1614, 35.5),
            Team("Ferencvaros", "Hungary", 1479, 35),
        ],
        [
            Team("Qarabag", "Azerbaijan", 1597, 33), Team("Galatasaray", "Turkey", 1721, 31.5),
            Team("Viktoria Plzen", "Czech Republic", 1572, 28), Team("Bodo/Glimt", "Norway", 1598, 28),
            Team("Union SG", "Belgium", 1701, 27), Team("Dynamo Kyiv", "Ukraine", 1517, 26.5),
            Team("Ludogorets", "Bulgaria", 1512, 26), Team("Midtjylland", "Denmark", 1624, 25.5),
            Team("Malmo", "Sweden", 1493, 18.5),
        ],
        [
            Team("Athletic Club", "Spain", 1764, 17.897), Team("Hoffenheim", "Germany", 1683, 17.324),
            Team("Nice", "France", 1703, 17), Team("Anderlecht", "Belgium", 1640, 14.5),
            Team("Twente", "Netherlands", 1627, 12.65), Team("Besiktas", "Turkey", 1484, 12),
            Team("FCSB", "Romania", 1434, 10.5), Team("RFS", "Latvia", 1225, 8),
            Team("Elfsborg", "Sweden", 1403, 4.3),
        ],
    ),
)

const LEAGUES = Dict{String,League}(
    CHAMPIONS_LEAGUE.key => CHAMPIONS_LEAGUE,
    EUROPA_LEAGUE.key => EUROPA_LEAGUE,
)

# ----------------------------------------------------------------------------- state

"""
Mutable draw state.
- `host[i, p]`  : team of pot `p` that visits `i` (i plays at home against it), 0 if undecided.
- `visit[i, p]` : team of pot `p` that hosts `i` (i plays away at it), 0 if undecided.
- `nat[i, n]`   : number of opponents of nationality `n` already assigned to `i`
                  (a team's own nationality starts at the cap so it can never be drawn).
"""
mutable struct DrawState
    host::Matrix{Int}
    visit::Matrix{Int}
    nat::Matrix{Int}
end

function DrawState(lg::League)
    nat = zeros(Int, N_TEAMS, length(lg.nat_names))
    for i in 1:N_TEAMS
        nat[i, lg.nat_id[i]] = MAX_SAME_NATIONALITY
    end
    return DrawState(zeros(Int, N_TEAMS, N_POTS), zeros(Int, N_TEAMS, N_POTS), nat)
end

"Record that `home` hosts `away`. Idempotent; throws if it contradicts an earlier decision."
function link!(lg::League, st::DrawState, home::Int, away::Int)
    ph, pa = pot_of(home), pot_of(away)
    if st.host[home, pa] == away && st.visit[away, ph] == home
        return nothing
    elseif st.host[home, pa] != 0 || st.visit[away, ph] != 0
        error("Inconsistent draw state: $(lg.teams[home].club) vs $(lg.teams[away].club)")
    end
    st.host[home, pa] = away
    st.visit[away, ph] = home
    st.nat[home, lg.nat_id[away]] += 1
    st.nat[away, lg.nat_id[home]] += 1
    return nothing
end

function assign!(lg::League, st::DrawState, s::Int, h::Int, a::Int)
    link!(lg, st, s, h)   # s hosts h
    link!(lg, st, a, s)   # a hosts s
    return nothing
end

fixed_matches(st::DrawState) =
    [(i, st.host[i, p]) for i in 1:N_TEAMS for p in 1:N_POTS if st.host[i, p] != 0]

# ----------------------------------------------------------------------------- feasibility

mutable struct Ctx
    lg::League
    st::DrawState
    rng::AbstractRNG
    time_limit::Float64
    calls::Int
end

"""
Cheap rule-based filter: all `(home_vs, away_vs)` couples from pot `op` that do not obviously
break a rule for team `s`. The MILP in [`feasible`](@ref) has the final word.
"""
function prefilter(lg::League, st::DrawState, s::Int, op::Int)
    sp, ns = pot_of(s), lg.nat_id[s]
    kh, ka = st.host[s, op], st.visit[s, op]
    kh != 0 && ka != 0 && return [(kh, ka)]

    ok_nat(j) = j != s && lg.nat_id[j] != ns &&
                st.nat[s, lg.nat_id[j]] < MAX_SAME_NATIONALITY &&
                st.nat[j, ns] < MAX_SAME_NATIONALITY
    # j would travel to s: it must not have travelled to s's pot already
    ok_visitor(j) = ok_nat(j) && st.visit[j, sp] == 0
    # j would host s: it must not have hosted a team of s's pot already
    ok_host(j) = ok_nat(j) && st.host[j, sp] == 0

    hs = kh != 0 ? [kh] : filter(ok_visitor, collect(pot_range(op)))
    as = ka != 0 ? [ka] : filter(ok_host, collect(pot_range(op)))
    out = Tuple{Int,Int}[]
    for h in hs, a in as
        h == a && continue
        # two opponents of one nationality are fine only if s has met none of that nationality yet
        if kh == 0 && ka == 0 && lg.nat_id[h] == lg.nat_id[a] && st.nat[s, lg.nat_id[h]] >= 1
            continue
        end
        push!(out, (h, a))
    end
    return out
end

"""
Exact check by MILP: can the draw still be completed if `s` hosts `h` and visits `a`
on top of the matches already fixed?
(The original 3-D model's matchday index was never constrained, so it is equivalent to this 2-D one.)
"""
function feasible(ctx::Ctx, s::Int, h::Int, a::Int)::Bool
    ctx.calls += 1
    lg, st = ctx.lg, ctx.st
    m = Model(SCIP.Optimizer)
    set_silent(m)
    set_time_limit_sec(m, ctx.time_limit)
    @variable(m, x[1:N_TEAMS, 1:N_TEAMS], Bin)

    for (i, j) in lg.forbidden
        @constraint(m, x[i, j] == 0)
    end
    for i in 1:N_TEAMS, p in 1:N_POTS
        r = pot_range(p)
        @constraint(m, sum(x[i, j] for j in r) == 1)   # one home match against each pot
        @constraint(m, sum(x[j, i] for j in r) == 1)   # one away match against each pot
    end
    for i in 1:(N_TEAMS - 1), j in (i + 1):N_TEAMS
        @constraint(m, x[i, j] + x[j, i] <= 1)         # a pair meets at most once
    end
    for i in 1:N_TEAMS, members in lg.nat_members
        length(members) >= 3 || continue               # smaller groups cannot exceed the cap
        @constraint(m, sum(x[i, j] + x[j, i] for j in members) <= MAX_SAME_NATIONALITY)
    end
    for (home, away) in fixed_matches(st)
        @constraint(m, x[home, away] == 1)
    end
    @constraint(m, x[s, h] == 1)
    @constraint(m, x[a, s] == 1)

    optimize!(m)
    status = termination_status(m)
    if status in (MOI.INFEASIBLE, MOI.INFEASIBLE_OR_UNBOUNDED)
        return false
    elseif status in (MOI.OPTIMAL, MOI.FEASIBLE_POINT, MOI.LOCALLY_SOLVED)
        return true
    end
    error("Unexpected solver status: $status")
end

# ----------------------------------------------------------------------------- draw

struct Step
    team::Int
    pot::Int
    home_vs::Int
    away_vs::Int
    options::Union{Int,Nothing}   # admissible couples (exhaustive selection only)
    fixed::Bool                   # already imposed by earlier steps, nothing was drawn
end

struct DrawResult
    seed::Int
    host::Matrix{Int}
    visit::Matrix{Int}
    steps::Vector{Step}
    solver_calls::Int
    seconds::Float64
end

"""
Pick the `(home_vs, away_vs)` couple for team `s` against pot `op`, uniformly among the
admissible ones. `:enumeration` solves every prefiltered couple; `:rejection` samples and
only solves until one passes (same distribution, far fewer solves).
"""
function choose_match(ctx::Ctx, s::Int, op::Int, selection::Symbol)
    cands = prefilter(ctx.lg, ctx.st, s, op)
    s_name, op_name = ctx.lg.teams[s].club, "pot $(Char('A' + op - 1))"
    isempty(cands) && error("No candidate opponents for $s_name in $op_name")

    if ctx.st.host[s, op] != 0 && ctx.st.visit[s, op] != 0   # settled by earlier steps
        return cands[1], nothing, true
    end
    if selection === :enumeration
        ok = [c for c in cands if feasible(ctx, s, c[1], c[2])]
        isempty(ok) && error("Dead end: no admissible couple for $s_name in $op_name")
        return rand(ctx.rng, ok), length(ok), false
    end
    pool = copy(cands)
    while !isempty(pool)
        k = rand(ctx.rng, 1:length(pool))
        feasible(ctx, s, pool[k][1], pool[k][2]) && return pool[k], nothing, false
        deleteat!(pool, k)
    end
    error("Dead end: no admissible couple for $s_name in $op_name")
end

"""
    run_draw(lg; seed, order=:by_pot, selection=:rejection, time_limit=30.0) -> DrawResult

- `order = :by_pot`   : pots A to D in order, each team draws pots greater than or equal to its own.
- `order = :random`   : random team order and random opponent-pot order.
- `selection`         : `:rejection` (fast) or `:enumeration` (evaluates all candidate couples).
"""
function run_draw(lg::League; seed::Integer, order::Symbol = :by_pot,
                  selection::Symbol = :rejection, time_limit::Real = 30.0)::DrawResult
    order in (:by_pot, :random) || throw(ArgumentError("order must be :by_pot or :random"))
    selection in (:rejection, :enumeration) ||
        throw(ArgumentError("selection must be :rejection or :enumeration"))

    ctx = Ctx(lg, DrawState(lg), Xoshiro(seed), Float64(time_limit), 0)
    steps = Step[]
    t0 = time()

    plan = Tuple{Int,Int}[]   # (selected team, opponent pot)
    if order === :by_pot
        for p in 1:N_POTS, s in shuffle(ctx.rng, collect(pot_range(p))), op in p:N_POTS
            push!(plan, (s, op))
        end
    else
        for s in shuffle(ctx.rng, collect(1:N_TEAMS)), op in shuffle(ctx.rng, collect(1:N_POTS))
            push!(plan, (s, op))
        end
    end

    for (s, op) in plan
        (h, a), options, fixed = choose_match(ctx, s, op, selection)
        assign!(lg, ctx.st, s, h, a)
        push!(steps, Step(s, op, h, a, options, fixed))
    end

    return DrawResult(Int(seed), copy(ctx.st.host), copy(ctx.st.visit), steps, ctx.calls, time() - t0)
end

# ----------------------------------------------------------------------------- inspection

"All 144 fixtures of a draw as `(home, away)` team-index pairs."
fixtures(r::DrawResult) = [(i, r.host[i, p]) for i in 1:N_TEAMS for p in 1:N_POTS]

"Independent rule check of a finished draw. Returns a list of violations (empty = valid)."
function validate_draw(lg::League, r::DrawResult)::Vector{String}
    errs = String[]
    name(i) = lg.teams[i].club
    for i in 1:N_TEAMS, p in 1:N_POTS
        h, a = r.host[i, p], r.visit[i, p]
        (h == 0 || a == 0) && (push!(errs, "$(name(i)) has no opponent in pot $p"); continue)
        pot_of(h) == p && pot_of(a) == p || push!(errs, "$(name(i)): wrong pot in slot $p")
        r.visit[h, pot_of(i)] == i || push!(errs, "$(name(i))/$(name(h)): home match not mirrored")
        r.host[a, pot_of(i)] == i || push!(errs, "$(name(i))/$(name(a)): away match not mirrored")
    end
    fx = fixtures(r)
    length(unique(Set(f) for f in fx)) == length(fx) || push!(errs, "a pair meets more than once")
    for i in 1:N_TEAMS
        opps = vcat(r.host[i, :], r.visit[i, :])
        length(unique(opps)) == 8 || push!(errs, "$(name(i)) meets a team twice")
        for n in eachindex(lg.nat_names)
            c = count(j -> j != 0 && lg.nat_id[j] == n, opps)
            n == lg.nat_id[i] && c > 0 && push!(errs, "$(name(i)) plays a compatriot")
            c > MAX_SAME_NATIONALITY && push!(errs, "$(name(i)) meets $c teams from $(lg.nat_names[n])")
        end
    end
    return errs
end

end # module

# HTTP bridge exposing the DrawService core to the Streamlit frontend.
#
#   julia --project=. -t auto server.jl
#
# Env: JULIA_API_HOST (default 127.0.0.1), JULIA_API_PORT (default 8080), MAX_DRAWS (default 25)

using DrawService
using Oxygen
using HTTP
using JSON3

const HOST = get(ENV, "JULIA_API_HOST", "127.0.0.1")
const PORT = parse(Int, get(ENV, "JULIA_API_PORT", "8080"))
const MAX_DRAWS = parse(Int, get(ENV, "MAX_DRAWS", "25"))

const ORDERS = Dict("by_pot" => :by_pot, "random" => :random)
const SELECTIONS = Dict("rejection" => :rejection, "enumeration" => :enumeration)

const DRAW_LOCK = ReentrantLock()   # SCIP draws run one at a time; /health stays responsive
const WARM = Ref(false)

struct BadRequest <: Exception
    msg::String
end

json_response(status::Int, body) =
    HTTP.Response(status, ["Content-Type" => "application/json"], JSON3.write(body))

pot_label(p::Int) = string(Char('A' + p - 1))

function team_payload(lg::League, i::Int)
    t = lg.teams[i]
    return (club = t.club, nationality = t.nationality, elo = t.elo, uefa = t.uefa, pot = pot_label(pot_of(i)))
end

function league_payload(lg::League)
    return (
        key = lg.key,
        label = lg.label,
        pots = [[team_payload(lg, i) for i in (9 * (p - 1) + 1):(9 * p)] for p in 1:4],
    )
end

function draw_payload(lg::League, r::DrawResult)
    club(i) = lg.teams[i].club
    teams = map(1:36) do i
        opps = [(pot = pot_label(p), home_vs = club(r.host[i, p]), away_vs = club(r.visit[i, p])) for p in 1:4]
        ids = vcat(r.host[i, :], r.visit[i, :])
        merge(team_payload(lg, i), (
            opponents = opps,
            elo_sum = sum(lg.teams[j].elo for j in ids),
            uefa_sum = sum(lg.teams[j].uefa for j in ids),
        ))
    end
    steps = [(team = club(s.team), pot = pot_label(s.pot), home_vs = club(s.home_vs),
              away_vs = club(s.away_vs), options = s.options, fixed = s.fixed) for s in r.steps]
    return (
        seed = r.seed,
        seconds = r.seconds,
        solver_calls = r.solver_calls,
        violations = validate_draw(lg, r),
        teams = teams,
        steps = steps,
    )
end

function parse_request(req::HTTP.Request)
    raw = Oxygen.text(req)
    body = isempty(strip(raw)) ? JSON3.Object() : JSON3.read(raw)
    body isa JSON3.Object || throw(BadRequest("request body must be a JSON object"))

    league = String(get(body, :league, "CHAMPIONS_LEAGUE"))
    haskey(LEAGUES, league) || throw(BadRequest("unknown league '$league'; expected one of $(sort(collect(keys(LEAGUES))))"))

    order = String(get(body, :order, "by_pot"))
    haskey(ORDERS, order) || throw(BadRequest("unknown order '$order'; expected one of $(sort(collect(keys(ORDERS))))"))

    selection = String(get(body, :selection, "rejection"))
    haskey(SELECTIONS, selection) || throw(BadRequest("unknown selection '$selection'; expected one of $(sort(collect(keys(SELECTIONS))))"))

    n_draws = get(body, :n_draws, 1)
    (n_draws isa Integer && 1 <= n_draws <= MAX_DRAWS) || throw(BadRequest("n_draws must be an integer in 1:$MAX_DRAWS"))

    seed = get(body, :seed, rand(1:(2^31 - 1)))
    seed isa Integer || throw(BadRequest("seed must be an integer"))

    return (; league, order, selection, n_draws = Int(n_draws), seed = Int(seed))
end

@get "/health" function (req::HTTP.Request)
    return json_response(200, (status = "ok", ready = WARM[], threads = Threads.nthreads()))
end

@get "/api/leagues" function (req::HTTP.Request)
    return json_response(200, [league_payload(LEAGUES[k]) for k in sort(collect(keys(LEAGUES)))])
end

@post "/api/draw" function (req::HTTP.Request)
    try
        p = parse_request(req)
        lg = LEAGUES[p.league]
        t0 = time()
        draws = lock(DRAW_LOCK) do
            # run on a worker thread so the HTTP listener keeps serving /health meanwhile
            fetch(Threads.@spawn [
                run_draw(lg; seed = p.seed + d - 1, order = ORDERS[p.order], selection = SELECTIONS[p.selection])
                for d in 1:p.n_draws
            ])
        end
        return json_response(200, (
            league = p.league, order = p.order, selection = p.selection,
            n_draws = p.n_draws, seed = p.seed, seconds = time() - t0,
            draws = [draw_payload(lg, r) for r in draws],
        ))
    catch err
        err = err isa TaskFailedException ? err.task.result : err
        if err isa BadRequest
            return json_response(422, (error = err.msg,))
        elseif err isa JSON3.Error || err isa ArgumentError
            return json_response(400, (error = "invalid request: $(sprint(showerror, err))",))
        end
        @error "draw failed" exception = (err, catch_backtrace())
        return json_response(500, (error = "draw failed: $(sprint(showerror, err))",))
    end
end

server = serve(; host = HOST, port = PORT, async = true, show_banner = false, metrics = false)

# JIT warm-up so the first user request is fast; /health reports `ready` once done.
Threads.@spawn begin
    try
        run_draw(LEAGUES["CHAMPIONS_LEAGUE"]; seed = 0)
        @info "warm-up complete"
    catch err
        @error "warm-up failed" exception = (err, catch_backtrace())
    finally
        WARM[] = true
    end
end

try
    wait(server)
catch err
    err isa InterruptException || rethrow()
finally
    close(server)
end

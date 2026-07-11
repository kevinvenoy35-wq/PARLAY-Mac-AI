from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

NFL_SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
BET_LOG = Path(__file__).parent / "bet_log.csv"

st.set_page_config(
    page_title="Parlay Mac AI Phase 2",
    page_icon="🏈",
    layout="wide",
)

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
.pm-title {font-size:2.2rem;font-weight:900;margin-bottom:.1rem;}
.pm-sub {opacity:.72;margin-bottom:1rem;}
div[data-testid="stMetric"] {
    border:1px solid rgba(130,130,130,.25);
    border-radius:14px;
    padding:.75rem;
}
</style>
""", unsafe_allow_html=True)

def implied_probability(odds: int) -> float:
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)

def decimal_odds(odds: int) -> float:
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))

def profit(stake: float, odds: int) -> float:
    return stake * (odds / 100 if odds > 0 else 100 / abs(odds))

def expected_value(stake: float, odds: int, probability: float) -> float:
    return probability * profit(stake, odds) - (1 - probability) * stake

def kelly_fraction(odds: int, probability: float) -> float:
    b = decimal_odds(odds) - 1
    return max(0.0, (b * probability - (1 - probability)) / b) if b > 0 else 0.0

def decision_label(edge: float, confidence: float) -> str:
    if edge >= 0.05 and confidence >= 0.70:
        return "BET"
    if edge >= 0.02 and confidence >= 0.58:
        return "LEAN"
    return "PASS"

@st.cache_data(ttl=3600)
def load_schedule() -> pd.DataFrame:
    return pd.read_csv(NFL_SCHEDULE_URL, low_memory=False)

def build_team_form(data: pd.DataFrame, season: int) -> pd.DataFrame:
    games = data[
        (data["season"] == season)
        & (data["game_type"] == "REG")
        & data["home_score"].notna()
        & data["away_score"].notna()
    ].copy()

    if games.empty:
        return pd.DataFrame()

    home = pd.DataFrame({
        "team": games["home_team"],
        "pf": games["home_score"],
        "pa": games["away_score"],
        "win": (games["home_score"] > games["away_score"]).astype(int),
    })
    away = pd.DataFrame({
        "team": games["away_team"],
        "pf": games["away_score"],
        "pa": games["home_score"],
        "win": (games["away_score"] > games["home_score"]).astype(int),
    })
    combined = pd.concat([home, away], ignore_index=True)

    form = combined.groupby("team", as_index=False).agg(
        games=("win", "size"),
        wins=("win", "sum"),
        pf_pg=("pf", "mean"),
        pa_pg=("pa", "mean"),
    )
    form["win_pct"] = form["wins"] / form["games"]
    form["margin_pg"] = form["pf_pg"] - form["pa_pg"]
    return form

def matchup_projection(away_row: pd.Series, home_row: pd.Series) -> tuple[float, float, float]:
    margin_component = float(home_row["margin_pg"] - away_row["margin_pg"])
    win_component = float((home_row["win_pct"] - away_row["win_pct"]) * 7.0)
    projected_home_margin = 0.55 * margin_component + 0.45 * win_component + 1.5
    home_win_probability = 1 / (1 + math.exp(-projected_home_margin / 6.5))
    confidence = min(0.90, 0.55 + abs(projected_home_margin) / 20)
    return projected_home_margin, home_win_probability, confidence

def get_api_key() -> str:
    try:
        return st.secrets.get("ODDS_API_KEY", "")
    except Exception:
        return ""

@st.cache_data(ttl=300)
def fetch_live_odds(api_key: str) -> pd.DataFrame:
    if not api_key:
        return pd.DataFrame()

    response = requests.get(
        "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds",
        params={
            "apiKey": api_key,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "dateFormat": "iso",
        },
        timeout=20,
    )
    response.raise_for_status()

    rows = []
    for game in response.json():
        for book in game.get("bookmakers", []):
            for market in book.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "commence_time": game.get("commence_time"),
                        "bookmaker": book.get("title"),
                        "market": market.get("key"),
                        "outcome": outcome.get("name"),
                        "price": outcome.get("price"),
                        "point": outcome.get("point"),
                    })
    return pd.DataFrame(rows)

def load_bets() -> pd.DataFrame:
    cols = ["Date","League","Market","Pick","Odds","Stake","Result","Profit/Loss"]
    if BET_LOG.exists():
        try:
            return pd.read_csv(BET_LOG)
        except Exception:
            pass
    return pd.DataFrame(columns=cols)

def save_bets(df: pd.DataFrame) -> None:
    df.to_csv(BET_LOG, index=False)

st.markdown('<div class="pm-title">🏈 Parlay Mac AI — Phase 2</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="pm-sub">Automatic NFL schedule, matchup model, confidence grades, EV, Kelly sizing, parlays, and tracking.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    page = st.radio(
        "Choose a tool",
        [
            "Weekly NFL Board",
            "Best Bets Board",
            "Matchup Analyzer",
            "Live Odds",
            "No-Vig + EV",
            "Parlay Builder",
            "Bet Tracker",
            "Bankroll Plan",
        ],
    )
    st.divider()
    st.caption("Phase 2 is a decision-support model. It does not guarantee winning bets.")

try:
    nfl = load_schedule()
    seasons = sorted(nfl["season"].dropna().astype(int).unique(), reverse=True)
except Exception as exc:
    nfl = pd.DataFrame()
    seasons = [2026]
    st.error(f"Schedule data could not load: {exc}")

if page == "Weekly NFL Board":
    st.subheader("Automatic Weekly NFL Board")
    season = st.selectbox("Season", seasons)
    games = nfl[(nfl["season"] == season) & (nfl["game_type"] == "REG")].copy()
    weeks = sorted(games["week"].dropna().astype(int).unique())
    week = st.selectbox("Week", weeks if weeks else [1])
    board = games[games["week"] == week].copy()

    if board.empty:
        st.info("No games found for this week.")
    else:
        board["Matchup"] = board["away_team"] + " at " + board["home_team"]
        board["Kickoff"] = board["gameday"].astype(str) + " " + board["gametime"].fillna("")
        board["Venue"] = board["stadium"].fillna("TBD")
        st.dataframe(board[["Matchup","Kickoff","Venue"]], use_container_width=True, hide_index=True)

elif page == "Best Bets Board":
    st.subheader("Best Bets Board")
    season = st.selectbox("Season", seasons)
    games = nfl[(nfl["season"] == season) & (nfl["game_type"] == "REG")].copy()
    weeks = sorted(games["week"].dropna().astype(int).unique())
    week = st.selectbox("Week", weeks if weeks else [1])

    week_games = games[games["week"] == week].copy()
    prior_form = build_team_form(nfl, season - 1)

    rows = []
    for _, game in week_games.iterrows():
        away, home = game["away_team"], game["home_team"]
        a = prior_form[prior_form["team"] == away]
        h = prior_form[prior_form["team"] == home]
        if a.empty or h.empty:
            continue

        projected_margin, home_prob, confidence = matchup_projection(a.iloc[0], h.iloc[0])
        rows.append({
            "Matchup": f"{away} at {home}",
            "Home win probability": home_prob,
            "Projected home margin": projected_margin,
            "Confidence": confidence,
        })

    if not rows:
        st.info("Not enough data is available yet for this board.")
    else:
        board = pd.DataFrame(rows)
        board["Home win probability"] = board["Home win probability"].map(lambda x: f"{x:.1%}")
        board["Projected home margin"] = board["Projected home margin"].map(lambda x: f"{x:+.1f}")
        board["Confidence"] = board["Confidence"].map(lambda x: f"{x:.1%}")
        st.dataframe(board, use_container_width=True, hide_index=True)
        st.caption("This board ranks model confidence only. Enter sportsbook prices in the EV tool before betting.")

elif page == "Matchup Analyzer":
    st.subheader("Matchup Analyzer")
    season = st.selectbox("Season", seasons)
    games = nfl[(nfl["season"] == season) & (nfl["game_type"] == "REG")].copy()
    weeks = sorted(games["week"].dropna().astype(int).unique())
    week = st.selectbox("Week", weeks if weeks else [1])
    week_games = games[games["week"] == week].copy()
    week_games["label"] = week_games["away_team"] + " at " + week_games["home_team"]

    if week_games.empty:
        st.info("No games found.")
    else:
        selection = st.selectbox("Game", week_games["label"].tolist())
        game = week_games[week_games["label"] == selection].iloc[0]
        away, home = game["away_team"], game["home_team"]

        form = build_team_form(nfl, season - 1)
        away_row = form[form["team"] == away]
        home_row = form[form["team"] == home]

        if away_row.empty or home_row.empty:
            st.warning("Prior-season form is unavailable for this matchup.")
        else:
            ar, hr = away_row.iloc[0], home_row.iloc[0]
            projected_margin, home_prob, confidence = matchup_projection(ar, hr)
            away_prob = 1 - home_prob

            comp = pd.DataFrame({
                "Team":[away, home],
                "Record":[
                    f'{int(ar["wins"])}-{int(ar["games"]-ar["wins"])}',
                    f'{int(hr["wins"])}-{int(hr["games"]-hr["wins"])}',
                ],
                "Win %":[f'{ar["win_pct"]:.1%}', f'{hr["win_pct"]:.1%}'],
                "Points/game":[f'{ar["pf_pg"]:.1f}', f'{hr["pf_pg"]:.1f}'],
                "Allowed/game":[f'{ar["pa_pg"]:.1f}', f'{hr["pa_pg"]:.1f}'],
                "Margin/game":[f'{ar["margin_pg"]:+.1f}', f'{hr["margin_pg"]:+.1f}'],
            })
            st.dataframe(comp, use_container_width=True, hide_index=True)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"{away} win probability", f"{away_prob:.1%}")
            c2.metric(f"{home} win probability", f"{home_prob:.1%}")
            c3.metric("Projected home margin", f"{projected_margin:+.1f}")
            c4.metric("Model confidence", f"{confidence:.1%}")

            sportsbook_home_spread = st.number_input(
                f"Sportsbook spread for {home}",
                value=-2.5,
                step=0.5,
            )
            model_edge_points = projected_margin + sportsbook_home_spread
            edge_probability = min(0.15, abs(model_edge_points) / 28)
            decision = decision_label(edge_probability, confidence)

            st.metric("Decision", decision)
            if decision == "PASS":
                st.warning("PASS: the model edge is too small.")
            elif model_edge_points > 0:
                st.success(f"{decision}: {home} {sportsbook_home_spread:+.1f}")
            else:
                st.success(f"{decision}: {away} {-sportsbook_home_spread:+.1f}")

            st.caption("Always adjust for quarterbacks, injuries, coaching changes, weather, and current line movement.")

elif page == "Live Odds":
    st.subheader("Live NFL Odds")
    api_key = get_api_key()

    if not api_key:
        st.info("Live odds are ready, but an API key has not been added yet.")
        st.code('ODDS_API_KEY = "your_key_here"')
        st.caption("Add it under Streamlit → Manage app → Settings → Secrets.")
    else:
        try:
            odds = fetch_live_odds(api_key)
            market = st.selectbox("Market", ["h2h","spreads","totals"])
            st.dataframe(
                odds[odds["market"] == market],
                use_container_width=True,
                hide_index=True,
            )
        except Exception as exc:
            st.error(f"Live odds could not load: {exc}")

elif page == "No-Vig + EV":
    st.subheader("No-Vig, EV, and Kelly Calculator")
    left, right = st.columns(2)
    with left:
        side1 = st.text_input("Side 1", "Favorite")
        odds1 = st.number_input("Side 1 odds", value=-125, step=5)
    with right:
        side2 = st.text_input("Side 2", "Underdog")
        odds2 = st.number_input("Side 2 odds", value=105, step=5)

    p1 = implied_probability(int(odds1))
    p2 = implied_probability(int(odds2))
    total = p1 + p2

    st.dataframe(pd.DataFrame({
        "Side":[side1, side2],
        "Book implied":[f"{p1:.2%}", f"{p2:.2%}"],
        "No-vig probability":[f"{p1/total:.2%}", f"{p2/total:.2%}"],
    }), use_container_width=True, hide_index=True)

    selected = st.radio("Evaluate", [side1, side2], horizontal=True)
    chosen_odds = int(odds1 if selected == side1 else odds2)
    true_probability = st.slider("Your true probability", 1, 99, 55) / 100
    stake = st.number_input("Stake", min_value=1.0, value=100.0, step=10.0)
    bankroll = st.number_input("Bankroll", min_value=1.0, value=1000.0, step=100.0)

    edge = true_probability - implied_probability(chosen_odds)
    ev = expected_value(stake, chosen_odds, true_probability)
    quarter_kelly = bankroll * kelly_fraction(chosen_odds, true_probability) * 0.25
    decision = decision_label(edge, 0.80)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Edge", f"{edge:.2%}")
    c2.metric("Expected value", f"${ev:,.2f}")
    c3.metric("Quarter-Kelly", f"${quarter_kelly:,.2f}")
    c4.metric("Decision", decision)

elif page == "Parlay Builder":
    st.subheader("Parlay Builder")
    legs = st.slider("Number of legs", 2, 8, 3)
    probabilities, odds_list = [], []

    for i in range(legs):
        a, b, c = st.columns([2,1,1])
        with a:
            st.text_input(f"Leg {i+1}", f"Leg {i+1}", key=f"name{i}")
        with b:
            odds_list.append(int(st.number_input("Odds", value=-110, step=5, key=f"odds{i}")))
        with c:
            probabilities.append(st.slider("True %", 1, 99, 60, key=f"prob{i}") / 100)

    hit_probability = math.prod(probabilities)
    sportsbook_decimal = math.prod(decimal_odds(o) for o in odds_list)
    sportsbook_american = (sportsbook_decimal - 1) * 100 if sportsbook_decimal >= 2 else -100 / (sportsbook_decimal - 1)
    fair_decimal = 1 / hit_probability
    fair_american = (fair_decimal - 1) * 100 if fair_decimal >= 2 else -100 / (fair_decimal - 1)

    c1, c2, c3 = st.columns(3)
    c1.metric("Estimated hit probability", f"{hit_probability:.2%}")
    c2.metric("Sportsbook parlay odds", f"{sportsbook_american:+.0f}")
    c3.metric("Fair odds", f"{fair_american:+.0f}")

    if legs > 4:
        st.warning("Long parlays carry heavy variance. Keep the stake small.")

elif page == "Bet Tracker":
    st.subheader("Bet Tracker")
    bets = load_bets()

    with st.form("bet_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            bet_date = st.date_input("Date", date.today())
            league = st.selectbox("League", ["NFL","College Football","Other"])
        with c2:
            market = st.selectbox("Market", ["Spread","Moneyline","Total","Player Prop","Parlay","Other"])
            pick = st.text_input("Pick")
        with c3:
            odds = st.number_input("Odds", value=-110, step=5)
            stake = st.number_input("Stake", min_value=0.0, value=100.0, step=10.0)
        result = st.selectbox("Result", ["Pending","Win","Loss","Push"])
        submitted = st.form_submit_button("Add bet")

    if submitted and pick.strip():
        pnl = profit(stake, int(odds)) if result == "Win" else (-stake if result == "Loss" else 0.0)
        new_row = pd.DataFrame([{
            "Date":str(bet_date),
            "League":league,
            "Market":market,
            "Pick":pick.strip(),
            "Odds":int(odds),
            "Stake":float(stake),
            "Result":result,
            "Profit/Loss":round(pnl,2),
        }])
        bets = pd.concat([bets, new_row], ignore_index=True)
        save_bets(bets)
        st.success("Bet added.")

    if bets.empty:
        st.info("No bets recorded yet.")
    else:
        st.dataframe(bets, use_container_width=True, hide_index=True)
        settled = bets[bets["Result"].isin(["Win","Loss"])]
        wins = int((settled["Result"] == "Win").sum())
        losses = int((settled["Result"] == "Loss").sum())
        total_stake = pd.to_numeric(bets["Stake"], errors="coerce").fillna(0).sum()
        total_pnl = pd.to_numeric(bets["Profit/Loss"], errors="coerce").fillna(0).sum()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Record", f"{wins}-{losses}")
        c2.metric("Win rate", f"{wins/(wins+losses):.1%}" if wins+losses else "0.0%")
        c3.metric("Profit/Loss", f"${total_pnl:,.2f}")
        c4.metric("ROI", f"{total_pnl/total_stake:.1%}" if total_stake else "0.0%")

elif page == "Bankroll Plan":
    st.subheader("Bankroll Plan")
    bankroll = st.number_input("Starting bankroll", min_value=1.0, value=1000.0, step=100.0)
    unit_pct = st.slider("Standard unit percentage", 0.5, 3.0, 1.0, 0.25) / 100
    unit = bankroll * unit_pct

    c1, c2, c3 = st.columns(3)
    c1.metric("0.5 unit", f"${unit*0.5:,.2f}")
    c2.metric("1 unit", f"${unit:,.2f}")
    c3.metric("2 units", f"${unit*2:,.2f}")

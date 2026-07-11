import math
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_FILE = Path(__file__).parent / "bet_log.csv"

st.set_page_config(page_title="Parlay Mac AI Football", page_icon="🏈", layout="wide")
st.title("🏈 Parlay Mac AI Football")
st.caption("NFL and college-football betting workspace: matchup grades, no-vig, EV, Kelly sizing, parlays, and tracking.")

def implied_probability(odds):
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)

def decimal_odds(odds):
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))

def profit(stake, odds):
    return stake * (odds / 100 if odds > 0 else 100 / abs(odds))

def expected_value(stake, odds, probability):
    return probability * profit(stake, odds) - (1 - probability) * stake

def kelly_fraction(odds, probability):
    b = decimal_odds(odds) - 1
    return max(0.0, (b * probability - (1 - probability)) / b) if b > 0 else 0.0

def load_bets():
    columns = ["Date","League","Market","Pick","Odds","Stake","Result","Profit/Loss"]
    if DATA_FILE.exists():
        try:
            return pd.read_csv(DATA_FILE)
        except Exception:
            pass
    return pd.DataFrame(columns=columns)

def save_bets(df):
    df.to_csv(DATA_FILE, index=False)

page = st.sidebar.radio("Choose a tool", [
    "Football Matchup Card",
    "No-Vig + EV",
    "Parlay Builder",
    "Bet Tracker",
    "Bankroll Plan",
])
st.sidebar.caption("This tool supports decisions. It cannot guarantee winners.")

if page == "Football Matchup Card":
    st.subheader("Football Matchup Card")
    left, right = st.columns(2)
    with left:
        league = st.selectbox("League", ["NFL", "College Football"])
        away = st.text_input("Away team", "Away Team")
        away_line = st.number_input("Away spread", value=3.0, step=0.5)
    with right:
        week = st.text_input("Week / Date", "Week 1")
        home = st.text_input("Home team", "Home Team")
        home_line = st.number_input("Home spread", value=-3.0, step=0.5)

    st.write("Rate each category from 1 to 10.")
    factors = ["Quarterback","Offensive line","Defense","Coaching","Injuries","Recent form","Rest / travel"]
    away_scores, home_scores = [], []
    for factor in factors:
        a, h = st.columns(2)
        with a:
            away_scores.append(st.slider(f"{away}: {factor}", 1, 10, 5, key="a_"+factor))
        with h:
            home_scores.append(st.slider(f"{home}: {factor}", 1, 10, 5, key="h_"+factor))

    away_avg = sum(away_scores) / len(away_scores)
    home_avg = sum(home_scores) / len(home_scores)
    diff = away_avg - home_avg

    c1, c2, c3 = st.columns(3)
    c1.metric(f"{away} rating", f"{away_avg:.2f}/10")
    c2.metric(f"{home} rating", f"{home_avg:.2f}/10")
    c3.metric("Difference", f"{diff:+.2f}")

    if abs(diff) < 0.35:
        st.warning("Close matchup: PASS unless price, injuries, or line movement create a clear edge.")
    elif diff > 0:
        st.success(f"Your ratings lean {away} {away_line:+.1f}.")
    else:
        st.success(f"Your ratings lean {home} {home_line:+.1f}.")

elif page == "No-Vig + EV":
    st.subheader("No-Vig, EV, and Kelly Calculator")
    a, b = st.columns(2)
    with a:
        side1 = st.text_input("Side 1", "Favorite")
        odds1 = st.number_input("Side 1 odds", value=-125, step=5)
    with b:
        side2 = st.text_input("Side 2", "Underdog")
        odds2 = st.number_input("Side 2 odds", value=105, step=5)

    p1 = implied_probability(int(odds1))
    p2 = implied_probability(int(odds2))
    total = p1 + p2
    novig1, novig2 = p1 / total, p2 / total

    st.dataframe(pd.DataFrame({
        "Side":[side1, side2],
        "Book implied":[f"{p1:.2%}", f"{p2:.2%}"],
        "No-vig probability":[f"{novig1:.2%}", f"{novig2:.2%}"],
    }), use_container_width=True, hide_index=True)
    st.metric("Book hold / vig", f"{total - 1:.2%}")

    selected = st.radio("Evaluate", [side1, side2], horizontal=True)
    chosen_odds = int(odds1 if selected == side1 else odds2)
    true_prob = st.slider("Your estimated true probability", 1, 99, 55) / 100
    stake = st.number_input("Example stake", min_value=1.0, value=100.0, step=10.0)
    bankroll = st.number_input("Bankroll", min_value=1.0, value=1000.0, step=100.0)

    edge = true_prob - implied_probability(chosen_odds)
    ev = expected_value(stake, chosen_odds, true_prob)
    quarter_kelly = bankroll * kelly_fraction(chosen_odds, true_prob) * 0.25

    c1, c2, c3 = st.columns(3)
    c1.metric("Edge", f"{edge:.2%}")
    c2.metric("Expected value", f"${ev:,.2f}")
    c3.metric("Quarter-Kelly size", f"${quarter_kelly:,.2f}")

    if edge <= 0:
        st.warning("PASS: your probability does not beat the sportsbook implied probability.")
    else:
        st.success("Positive edge based on your estimate.")

elif page == "Parlay Builder":
    st.subheader("Parlay Builder")
    legs = st.slider("Number of legs", 2, 8, 3)
    probabilities, odds_list = [], []

    for i in range(legs):
        c1, c2, c3 = st.columns([2,1,1])
        with c1:
            st.text_input(f"Leg {i+1}", f"Leg {i+1}", key=f"name{i}")
        with c2:
            odds_list.append(int(st.number_input("Odds", value=-110, step=5, key=f"odds{i}")))
        with c3:
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
    st.caption("This assumes the legs are independent.")

elif page == "Bet Tracker":
    st.subheader("Bet Tracker")
    bets = load_bets()

    with st.form("add_bet", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            bet_date = st.date_input("Date", date.today())
            league = st.selectbox("League", ["NFL","College Football","Other"])
        with c2:
            market = st.selectbox("Market", ["Spread","Moneyline","Total","Player Prop","Parlay","Other"])
            pick = st.text_input("Pick")
        with c3:
            odds = st.number_input("American odds", value=-110, step=5)
            stake = st.number_input("Stake", min_value=0.0, value=100.0, step=10.0)
        result = st.selectbox("Result", ["Pending","Win","Loss","Push"])
        submitted = st.form_submit_button("Add bet")

    if submitted and pick.strip():
        pnl = profit(stake, int(odds)) if result == "Win" else (-stake if result == "Loss" else 0.0)
        new_row = pd.DataFrame([{
            "Date":str(bet_date), "League":league, "Market":market, "Pick":pick.strip(),
            "Odds":int(odds), "Stake":float(stake), "Result":result, "Profit/Loss":round(pnl,2)
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
        win_rate = wins / (wins + losses) if wins + losses else 0
        roi = total_pnl / total_stake if total_stake else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Record", f"{wins}-{losses}")
        c2.metric("Win rate", f"{win_rate:.1%}")
        c3.metric("Profit/Loss", f"${total_pnl:,.2f}")
        c4.metric("ROI", f"{roi:.1%}")

        st.download_button("Download bet log", bets.to_csv(index=False).encode("utf-8"),
                           "parlay_mac_bet_log.csv", "text/csv")

elif page == "Bankroll Plan":
    st.subheader("Bankroll Plan")
    bankroll = st.number_input("Starting bankroll", min_value=1.0, value=1000.0, step=100.0)
    unit_percent = st.slider("Standard unit percentage", 0.5, 3.0, 1.0, 0.25) / 100
    unit = bankroll * unit_percent

    c1, c2, c3 = st.columns(3)
    c1.metric("0.5 unit", f"${unit * 0.5:,.2f}")
    c2.metric("1 unit", f"${unit:,.2f}")
    c3.metric("2 units", f"${unit * 2:,.2f}")

    st.markdown('''
- Standard play: 1 unit
- Small lean: 0.5 unit
- Strongest qualified edge: up to 2 units
- Do not chase losses
- Keep long parlays small
- Track closing line value, not only wins and losses
''')

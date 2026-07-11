
import math
from datetime import date

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Parlay Mac AI", page_icon="📊", layout="wide")

st.title("📊 Parlay Mac AI — Matchup & Bet Tracker")
st.caption("Phase 1 prototype: manual odds entry, no-vig probability, EV, bet grading, and results tracking.")

def american_to_decimal(odds: int) -> float:
    if odds == 0:
        return 1.0
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))

def implied_probability(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)

def profit_for_stake(stake: float, odds: int) -> float:
    return stake * (odds / 100 if odds > 0 else 100 / abs(odds))

def grade_edge(edge: float) -> str:
    if edge >= 0.06:
        return "Strong edge"
    if edge >= 0.03:
        return "Moderate edge"
    if edge > 0:
        return "Small edge"
    return "No edge / Skip"

tab1, tab2, tab3 = st.tabs(["Matchup Analyzer", "Parlay Calculator", "Bet Tracker"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        sport = st.selectbox("Sport", ["NBA", "WNBA", "NFL", "MLB", "NCAA Basketball", "NCAA Football"])
        team_a = st.text_input("Team A", "Team A")
        odds_a = st.number_input("Team A American odds", value=-110, step=5)
        model_a = st.slider("Your estimated Team A win probability", 1, 99, 55) / 100
    with c2:
        market = st.selectbox("Market", ["Moneyline", "Spread", "Total", "Player Prop"])
        team_b = st.text_input("Team B", "Team B")
        odds_b = st.number_input("Team B American odds", value=-110, step=5)
        model_b = st.slider("Your estimated Team B win probability", 1, 99, 45) / 100

    imp_a = implied_probability(int(odds_a))
    imp_b = implied_probability(int(odds_b))
    total_imp = imp_a + imp_b
    no_vig_a = imp_a / total_imp
    no_vig_b = imp_b / total_imp
    edge_a = model_a - imp_a
    edge_b = model_b - imp_b

    st.subheader("Market comparison")
    result = pd.DataFrame({
        "Side": [team_a, team_b],
        "Sportsbook implied %": [imp_a, imp_b],
        "No-vig market %": [no_vig_a, no_vig_b],
        "Your model %": [model_a, model_b],
        "Edge": [edge_a, edge_b],
        "Grade": [grade_edge(edge_a), grade_edge(edge_b)],
    })
    for col in ["Sportsbook implied %", "No-vig market %", "Your model %", "Edge"]:
        result[col] = result[col].map(lambda x: f"{x:.1%}")
    st.dataframe(result, use_container_width=True, hide_index=True)

    stake = st.number_input("Example stake", min_value=1.0, value=100.0, step=10.0)
    selected = st.radio("Side to evaluate", [team_a, team_b], horizontal=True)
    if selected == team_a:
        chosen_odds, chosen_prob = int(odds_a), model_a
    else:
        chosen_odds, chosen_prob = int(odds_b), model_b

    possible_profit = profit_for_stake(stake, chosen_odds)
    ev = chosen_prob * possible_profit - (1 - chosen_prob) * stake
    roi = ev / stake

    m1, m2, m3 = st.columns(3)
    m1.metric("Potential profit", f"${possible_profit:,.2f}")
    m2.metric("Expected value", f"${ev:,.2f}")
    m3.metric("Expected ROI", f"{roi:.1%}")

    if ev > 0:
        st.success(f"{selected} shows positive expected value based on your probability estimate.")
    else:
        st.warning(f"{selected} does not show positive expected value. Consider skipping it.")

with tab2:
    st.subheader("Parlay probability calculator")
    st.write("Enter each leg's estimated true probability. This assumes the legs are independent.")
    num_legs = st.slider("Number of legs", 2, 8, 3)
    probs = []
    for i in range(num_legs):
        p = st.slider(f"Leg {i+1} probability", 1, 99, 60, key=f"p{i}") / 100
        probs.append(p)
    combined = math.prod(probs)
    fair_decimal = 1 / combined
    fair_american = (fair_decimal - 1) * 100 if fair_decimal >= 2 else -100 / (fair_decimal - 1)
    st.metric("Estimated parlay hit probability", f"{combined:.2%}")
    st.metric("Fair American odds", f"{fair_american:+.0f}")
    st.caption("Correlated legs can make this estimate inaccurate. Avoid treating every leg as independent.")

with tab3:
    st.subheader("Bet tracker")
    st.write("Use this table as a starter log. Export it to CSV after entering your bets.")
    rows = st.number_input("Number of bets to enter", min_value=1, max_value=20, value=5)
    data = []
    for i in range(int(rows)):
        cols = st.columns([1, 1.5, 1.5, 1, 1, 1])
        with cols[0]:
            d = st.date_input("Date", date.today(), key=f"d{i}", label_visibility="collapsed")
        with cols[1]:
            s = st.text_input("Sport", key=f"s{i}", placeholder="Sport", label_visibility="collapsed")
        with cols[2]:
            pick = st.text_input("Pick", key=f"pick{i}", placeholder="Pick", label_visibility="collapsed")
        with cols[3]:
            odds = st.number_input("Odds", value=-110, step=5, key=f"o{i}", label_visibility="collapsed")
        with cols[4]:
            wager = st.number_input("Stake", min_value=0.0, value=0.0, step=10.0, key=f"w{i}", label_visibility="collapsed")
        with cols[5]:
            outcome = st.selectbox("Result", ["Pending", "Win", "Loss", "Push"], key=f"r{i}", label_visibility="collapsed")
        data.append([d, s, pick, odds, wager, outcome])

    df = pd.DataFrame(data, columns=["Date", "Sport", "Pick", "Odds", "Stake", "Result"])

    def pnl(row):
        if row["Result"] == "Win":
            return profit_for_stake(row["Stake"], int(row["Odds"]))
        if row["Result"] == "Loss":
            return -row["Stake"]
        return 0.0

    df["Profit/Loss"] = df.apply(pnl, axis=1)
    st.dataframe(df, use_container_width=True, hide_index=True)

    total_staked = df["Stake"].sum()
    total_pnl = df["Profit/Loss"].sum()
    wins = (df["Result"] == "Win").sum()
    losses = (df["Result"] == "Loss").sum()
    settled = wins + losses
    win_rate = wins / settled if settled else 0
    tracker_roi = total_pnl / total_staked if total_staked else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Record", f"{wins}-{losses}")
    k2.metric("Win rate", f"{win_rate:.1%}")
    k3.metric("Profit/Loss", f"${total_pnl:,.2f}")
    k4.metric("ROI", f"{tracker_roi:.1%}")

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download bet log CSV", csv, "parlay_mac_bet_log.csv", "text/csv")


from pathlib import Path
from datetime import date
import math
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_FILE = APP_DIR / "bet_log.csv"

st.set_page_config(
    page_title="Parlay Mac AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    .big-title {font-size: 2.2rem; font-weight: 800; margin-bottom: 0.2rem;}
    .subtitle {opacity: 0.75; margin-bottom: 1.2rem;}
    .pm-card {
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

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

def edge_grade(edge: float) -> str:
    if edge >= 0.06:
        return "Strong edge"
    if edge >= 0.03:
        return "Moderate edge"
    if edge > 0:
        return "Small edge"
    return "No edge / Skip"

def load_bets():
    if DATA_FILE.exists():
        try:
            return pd.read_csv(DATA_FILE)
        except Exception:
            pass
    return pd.DataFrame(columns=["Date","Sport","Market","Pick","Odds","Stake","Result","Profit/Loss"])

def save_bets(df):
    df.to_csv(DATA_FILE, index=False)

st.markdown('<div class="big-title">📊 Parlay Mac AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">One-click sports betting analysis and tracking dashboard</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Parlay Mac AI")
    page = st.radio(
        "Choose a tool",
        ["Matchup Analyzer", "No-Vig Calculator", "Parlay Calculator", "Bet Tracker", "Bankroll Guide"]
    )
    st.divider()
    st.caption("This tool does not guarantee wins. It helps organize odds, probability, EV, and betting records.")

if page == "Matchup Analyzer":
    st.subheader("Matchup Analyzer")
    st.write("Enter two sides and your estimated probabilities. The app compares them with sportsbook odds.")

    c1, c2 = st.columns(2)
    with c1:
        sport = st.selectbox("Sport", ["NBA","WNBA","NFL","MLB","NCAA Basketball","NCAA Football"])
        side_a = st.text_input("Side A", "Team A")
        odds_a = st.number_input("Side A American odds", value=-110, step=5)
        model_a = st.slider("Your estimated Side A probability", 1, 99, 55) / 100
    with c2:
        market = st.selectbox("Market", ["Moneyline","Spread","Total","Player Prop"])
        side_b = st.text_input("Side B", "Team B")
        odds_b = st.number_input("Side B American odds", value=-110, step=5)
        model_b = st.slider("Your estimated Side B probability", 1, 99, 45) / 100

    imp_a = implied_probability(int(odds_a))
    imp_b = implied_probability(int(odds_b))
    total_imp = imp_a + imp_b
    novig_a = imp_a / total_imp if total_imp else 0
    novig_b = imp_b / total_imp if total_imp else 0
    edge_a = model_a - imp_a
    edge_b = model_b - imp_b

    result = pd.DataFrame({
        "Side":[side_a, side_b],
        "Book Implied %":[f"{imp_a:.1%}", f"{imp_b:.1%}"],
        "No-Vig Market %":[f"{novig_a:.1%}", f"{novig_b:.1%}"],
        "Your Probability %":[f"{model_a:.1%}", f"{model_b:.1%}"],
        "Edge":[f"{edge_a:.1%}", f"{edge_b:.1%}"],
        "Grade":[edge_grade(edge_a), edge_grade(edge_b)]
    })
    st.dataframe(result, use_container_width=True, hide_index=True)

    st.markdown("### Bet Value Check")
    stake = st.number_input("Example stake", min_value=1.0, value=100.0, step=10.0)
    selected = st.radio("Evaluate", [side_a, side_b], horizontal=True)
    chosen_odds = int(odds_a if selected == side_a else odds_b)
    chosen_prob = model_a if selected == side_a else model_b
    potential_profit = profit_for_stake(stake, chosen_odds)
    ev = chosen_prob * potential_profit - (1 - chosen_prob) * stake
    roi = ev / stake

    m1, m2, m3 = st.columns(3)
    m1.metric("Potential Profit", f"${potential_profit:,.2f}")
    m2.metric("Expected Value", f"${ev:,.2f}")
    m3.metric("Expected ROI", f"{roi:.1%}")

    if ev > 0:
        st.success(f"{selected} shows positive expected value based on your estimate.")
    else:
        st.warning(f"{selected} does not show positive expected value. Consider skipping it.")

elif page == "No-Vig Calculator":
    st.subheader("No-Vig Calculator")
    st.write("Remove the sportsbook margin from a two-way market.")

    a, b = st.columns(2)
    with a:
        label1 = st.text_input("Side 1", "Favorite")
        o1 = st.number_input("Side 1 odds", value=-130, step=5)
    with b:
        label2 = st.text_input("Side 2", "Underdog")
        o2 = st.number_input("Side 2 odds", value=110, step=5)

    p1 = implied_probability(int(o1))
    p2 = implied_probability(int(o2))
    overround = p1 + p2
    nv1 = p1 / overround
    nv2 = p2 / overround

    out = pd.DataFrame({
        "Side":[label1,label2],
        "Implied Probability":[f"{p1:.2%}",f"{p2:.2%}"],
        "No-Vig Probability":[f"{nv1:.2%}",f"{nv2:.2%}"]
    })
    st.dataframe(out, use_container_width=True, hide_index=True)
    st.metric("Sportsbook Hold / Vig", f"{(overround-1):.2%}")

elif page == "Parlay Calculator":
    st.subheader("Parlay Calculator")
    st.write("Estimate hit probability and fair odds for 2 to 8 legs.")

    n = st.slider("Number of legs", 2, 8, 3)
    probs = []
    odds_list = []
    for i in range(n):
        c1, c2 = st.columns(2)
        with c1:
            p = st.slider(f"Leg {i+1} estimated probability", 1, 99, 60, key=f"prob_{i}") / 100
            probs.append(p)
        with c2:
            o = st.number_input(f"Leg {i+1} sportsbook odds", value=-110, step=5, key=f"odds_{i}")
            odds_list.append(int(o))

    hit_prob = math.prod(probs)
    decimal_price = math.prod([american_to_decimal(o) for o in odds_list])
    sportsbook_american = (decimal_price - 1) * 100 if decimal_price >= 2 else -100 / (decimal_price - 1)
    fair_decimal = 1 / hit_prob
    fair_american = (fair_decimal - 1) * 100 if fair_decimal >= 2 else -100 / (fair_decimal - 1)

    a,b,c = st.columns(3)
    a.metric("Estimated Hit Probability", f"{hit_prob:.2%}")
    b.metric("Sportsbook Parlay Odds", f"{sportsbook_american:+.0f}")
    c.metric("Fair Odds From Your Estimates", f"{fair_american:+.0f}")
    st.caption("This assumes the legs are independent. Same-game or correlated legs can make the estimate inaccurate.")

elif page == "Bet Tracker":
    st.subheader("Bet Tracker")
    bets = load_bets()

    with st.form("add_bet", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            bet_date = st.date_input("Date", date.today())
            sport = st.selectbox("Sport", ["NBA","WNBA","NFL","MLB","NCAA Basketball","NCAA Football","Other"])
        with c2:
            market = st.selectbox("Market", ["Moneyline","Spread","Total","Player Prop","Parlay","Other"])
            pick = st.text_input("Pick")
        with c3:
            odds = st.number_input("American odds", value=-110, step=5)
            stake = st.number_input("Stake", min_value=0.0, value=100.0, step=10.0)
        result = st.selectbox("Result", ["Pending","Win","Loss","Push"])
        submitted = st.form_submit_button("Add Bet")

    if submitted and pick.strip():
        if result == "Win":
            pnl = profit_for_stake(stake, int(odds))
        elif result == "Loss":
            pnl = -stake
        else:
            pnl = 0.0
        row = pd.DataFrame([{
            "Date":str(bet_date),
            "Sport":sport,
            "Market":market,
            "Pick":pick.strip(),
            "Odds":int(odds),
            "Stake":float(stake),
            "Result":result,
            "Profit/Loss":round(float(pnl),2)
        }])
        bets = pd.concat([bets, row], ignore_index=True)
        save_bets(bets)
        st.success("Bet added.")

    if not bets.empty:
        st.dataframe(bets, use_container_width=True, hide_index=True)
        total_stake = pd.to_numeric(bets["Stake"], errors="coerce").fillna(0).sum()
        total_pnl = pd.to_numeric(bets["Profit/Loss"], errors="coerce").fillna(0).sum()
        wins = (bets["Result"] == "Win").sum()
        losses = (bets["Result"] == "Loss").sum()
        settled = wins + losses
        win_rate = wins / settled if settled else 0
        roi = total_pnl / total_stake if total_stake else 0

        a,b,c,d = st.columns(4)
        a.metric("Record", f"{wins}-{losses}")
        b.metric("Win Rate", f"{win_rate:.1%}")
        c.metric("Profit/Loss", f"${total_pnl:,.2f}")
        d.metric("ROI", f"{roi:.1%}")

        csv = bets.to_csv(index=False).encode("utf-8")
        st.download_button("Download Bet Log", csv, "parlay_mac_bet_log.csv", "text/csv")

        if st.button("Clear Entire Bet Log"):
            save_bets(pd.DataFrame(columns=bets.columns))
            st.rerun()
    else:
        st.info("No bets added yet.")

elif page == "Bankroll Guide":
    st.subheader("Bankroll Guide")
    bankroll = st.number_input("Current bankroll", min_value=1.0, value=1000.0, step=100.0)
    unit_pct = st.slider("Unit size", 0.5, 5.0, 1.0, 0.5) / 100
    unit = bankroll * unit_pct

    a,b,c = st.columns(3)
    a.metric("1 Unit", f"${unit:,.2f}")
    b.metric("0.5 Unit", f"${unit/2:,.2f}")
    c.metric("2 Units", f"${unit*2:,.2f}")

    st.markdown("""
    **Suggested approach**
    - Standard bet: 1 unit
    - Small lean: 0.5 unit
    - Strongest play: up to 2 units
    - Avoid chasing losses
    - Keep parlays smaller than straight bets
    """)

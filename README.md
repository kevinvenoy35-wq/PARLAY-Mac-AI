
# Parlay Mac AI — Phase 1 Starter

This is a simple Streamlit web app that includes:

- American odds to implied probability
- No-vig probability
- Expected value and ROI
- Basic bet grading
- Parlay hit-probability calculator
- Manual bet tracker with CSV export

## Run on Windows

1. Install Python from python.org and check **Add Python to PATH**.
2. Open the folder containing these files.
3. Click the address bar in File Explorer, type `cmd`, and press Enter.
4. Run:

   pip install -r requirements.txt

5. Then run:

   streamlit run app.py

Your browser should open automatically.

## Important

This prototype does not predict games by itself yet. It calculates from the probabilities and odds you enter. Automated NBA/WNBA statistics, injuries, line movement, and model predictions will be added in later phases.

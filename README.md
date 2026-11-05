# Lab 19 — Legend Panel

A Streamlit panel that evaluates the same SEC EDGAR 10-K facts through Buffett, Graham, and Burry checks.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Start with `COST`. The saved COST report and three memos reproduce the class known answer: Buffett 3/3, Graham 2/3 at the 2.0 current-ratio threshold, and Burry 2/2. Changing Graham's threshold to 1.0 makes his COST screen pass.

The panel flags any number in any memo that was not printed by the EDGAR extraction script.

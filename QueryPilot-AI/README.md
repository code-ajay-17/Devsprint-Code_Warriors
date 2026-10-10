# QueryPilotAI — Member 2 Triage Engine

## Files
- `triage_engine.py`: explainable rule-based triage functions.
- `tests.py`: 10 unit tests for the agreed interface.
- `requirements.txt`: runtime dependency.

## Run tests
```powershell
python -m pip install -r requirements.txt
python -m unittest tests -v
```

## API
```python
from triage_engine import triage_keyword, triage_dataframe
result = triage_keyword({
    "clicks": 50,
    "impressions": 1000,
    "conversions": 5,
    "spend": 100,
    "revenue": 250,
})
```

`triage_keyword` returns `decision`, `risk_level`, `reason`, `risk_score`,
`suggested_action`, `evidence`, and `needs_review`.

`triage_dataframe(df)` preserves original columns and appends `triage_decision`,
`triage_risk_level`, `triage_reason`, `triage_risk_score`,
`triage_suggested_action`, `triage_evidence`, and `triage_needs_review`.

The engine accepts either `spend`/`revenue` or `cost`/`conversion_value`.
`relevance_score` is optional and must be in [0, 1]. A score below
`low_relevance_threshold` returns `BLOCK` with `needs_review=True`.

## Business-rule caution
This is an explainable heuristic, not a trained or calibrated predictive model.
The default promotion example checks whether revenue exceeds spend; replace this
with an approved ROAS/margin target before production use. Low relevance is only
used if a relevance score is actually supplied. Blocking decisions should be
reviewed by the team before live campaign changes.

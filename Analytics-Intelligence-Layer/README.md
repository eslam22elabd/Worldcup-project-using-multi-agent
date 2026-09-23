# Analytics Intelligence Layer (Week 4)

## What this does

1. **Loads and validates** a Week 3 `week4_disc_*.json` export 
   — fails clearly on genuinely unusable input (empty discussion,
   invalid JSON), and collects warnings for individually skippable
   problems (a malformed snapshot, a duplicate round, an agent with no
   data) without aborting the whole run.
2. **Builds a numeric stance series** per agent, per round 
   — by reusing Week 3's own already-computed `stance.polarity`
   value rather than recomputing a new score from the opinion text.
3. **Computes opinion change** between an agent's consecutive available rounds.
4. **Calculates Agreement** (consensus score) for each round.
5. **Calculates Influence** for each agent based on how others shift their opinions after interactions.
6. **Analyzes Sentiment** of each message using an LLM (via OpenRouter API).
7. **Generates a comprehensive Markdown report** summarising all 4 metrics.
8. **Produces Visualizations** (Opinion Trajectory Chart and Interaction Graph).

## Repository layout

```
Analytics-Intelligence-Layer-main/
├── main.py                                  # Pipeline entry point
├── .env                                     # Environment variables (OpenRouter API key)
├── requirements.txt
├── docs/                                    
│   ├── DESIGN.md                            # Opinion change design
│   └── DESIGN_SENTIMENT_ANALYTICS.md        # Sentiment & Unified Engine design
    ├── DESIGN_AGREEMENT_INFLUENCE.md
├── data/sample/                             # Sample discussion exports
├── src/
│   ├── ingestion/discussion_loader.py     
│   └── opinion_change/
│       ├── stance_series.py                 
│       └── change_calculator.py             
│   ├── agreement/calculator.py              
│   ├── influence/calculator.py              
│   ├── sentiment/calculator.py              # LLM-based sentiment scoring
│   ├── analytics/engine.py                  # Unified analytics engine
│   └── reporting/
│       ├── report_generator.py              # Markdown report generator
│       └── visualizations.py                # NetworkX / Matplotlib charts
└── tests/                                   # Full test suite covering all modules
```

## How to run

1. Create a `.env` file in the project root and add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_key_here
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the pipeline:
   ```bash
   # Using a bundled sample:
   python main.py data/sample/week4_disc_7e76495b7d96.json
   
   # Using your own Week 3 export:
   python main.py path/to/week4_disc_xxxxxxxx.json
   ```

4. Check the generated outputs:
   - `reports/discussion_report.md`
   - `outputs/opinion_trajectory.png`
   - `outputs/interaction_graph.png`

## Running the tests

```bash
python -m pytest tests/ -v
```

The test suite thoroughly covers data validation, edge cases (missing data, non-computable metrics), API mocking for sentiment analysis, and file generation for reporting.

"""main.py — Analytics demo: Opinion Change + Agreement + Influence + Sentiment.

Usage:
    python main.py path/to/week4_disc_xxxx.json
    python main.py                              # uses the bundled sample

Pipeline demonstrated:
    1. Load + validate a Week 3 discussion export (sections 4, 27).
    2. Build a per-agent, per-round numeric stance series (section 6, 7).
    3. Compute round-to-round opinion change (section 8, 28).
    4. Compute per-round agreement scores (sections 9-11).
    5. Compute per-agent influence scores (sections 12-16).
    6. Compute LLM sentiment scores (section 26).
    7. Generate Markdown report (sections 20-22).
    8. Generate opinion trajectory chart (section 24).
    9. Generate interaction graph (section 25).
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.ingestion.discussion_loader import DiscussionValidationError, load_discussion_export
from src.opinion_change.change_calculator import compute_opinion_change
from src.opinion_change.stance_series import build_stance_series
from src.agreement.calculator import compute_agreement
from src.influence.calculator import compute_influence
from src.analytics.engine import run_analytics
from src.reporting.report_generator import generate_report
from src.reporting.visualizations import generate_opinion_trajectory, generate_interaction_graph

DEFAULT_SAMPLE = Path(__file__).resolve().parent / "data" / "sample" / "week4_disc_443594805eb2.json"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE

    try:
        discussion = load_discussion_export(path)
    except DiscussionValidationError as exc:
        print(f"Could not load discussion: {exc}")
        sys.exit(1)

    print(f"Discussion: {discussion.discussion_id}")
    print(f"Topic: {discussion.topic}")
    print(f"Participants: {discussion.participants}")

    if discussion.report.has_warnings:
        print(f"\n{len(discussion.report.warnings)} validation warning(s):")
        for w in discussion.report.warnings:
            print(f"  - {w}")

    series = build_stance_series(discussion)

    print("\n--- Stance series (section 6/7) ---")
    for agent_id, agent_series in series.items():
        if not agent_series.has_data:
            print(f"  {agent_id}: NO DATA")
            continue
        points_str = ", ".join(f"round {p.round_number}={p.stance:+.3f}" for p in agent_series.points)
        print(f"  {agent_id}: {points_str}")

    changes = compute_opinion_change(series)

    print("\n--- Opinion change (section 8/28) ---")
    for agent_id, result in changes.items():
        if not result.is_computable:
            print(f"  {agent_id}: not computable ({result.reason})")
            continue
        changes_str = ", ".join(
            f"[{c.from_round}->{c.to_round}]={c.change:+.3f}" for c in result.changes
        )
        print(f"  {agent_id}: {changes_str}")

    # --- Step 4: Agreement (sections 9-11) ---
    agreement = compute_agreement(series, num_rounds=discussion.num_rounds)

    print("\n--- Agreement scores (section 9-11) ---")
    for r in agreement:
        if not r.is_computable:
            print(f"  Round {r.round_number}: not computable ({r.reason})")
        else:
            print(f"  Round {r.round_number}: {r.score:.4f}  ({r.num_agents} agents)")

    # --- Step 5: Influence (sections 12-16) ---
    influence = compute_influence(series, discussion)

    print("\n--- Influence scores (section 12-16) ---")
    for agent_id, result in influence.items():
        if not result.is_computable:
            print(f"  {agent_id}: not computable ({result.reason})")
        else:
            print(f"  {agent_id}: {result.score:+.4f}  ({result.num_observations} observations)")

    # --- Step 6: Unified Analytics + Sentiment (section 26) ---
    print("\n--- Sentiment scores (LLM via OpenRouter) ---")
    analytics = run_analytics(discussion)
    for result in analytics.sentiment:
        if not result.is_computable:
            print(f"  {result.message_id}: not computable ({result.reason})")
        else:
            print(f"  {result.message_id}: {result.score:+.4f}")

    # --- Step 7: Markdown Report (sections 20-22) ---
    print("\n--- Generating report ---")
    report_path = Path(__file__).resolve().parent / "reports" / "discussion_report.md"
    generate_report(analytics, discussion, output_path=report_path)
    print(f"  Report saved → {report_path}")

    # --- Step 8: Opinion Trajectory Chart (section 24) ---
    print("\n--- Generating visualizations ---")
    traj_path = Path(__file__).resolve().parent / "outputs" / "opinion_trajectory.png"
    generate_opinion_trajectory(series, discussion.discussion_id, output_path=traj_path)
    print(f"  Opinion trajectory → {traj_path}")

    # --- Step 9: Interaction Graph (section 25) ---
    graph_path = Path(__file__).resolve().parent / "outputs" / "interaction_graph.png"
    generate_interaction_graph(discussion, influence, output_path=graph_path)
    print(f"  Interaction graph  → {graph_path}")


if __name__ == "__main__":
    main()

"""main.py — Runs a real multi-round discussion using match-specific personas.

The user types anything about a football match (Arabic or English) and the
system detects which match they mean, loads the appropriate match-specific
personas, and runs a full multi-agent discussion simulation.

Supported matches (2026 World Cup):
  • Argentina × Spain — Final
  • France × England — Third Place

Any other input triggers a generic web-search-based discussion.

Prerequisites:
    - Week 2's dependencies installed (openrouter/tavily keys in Week 2's .env,
      plus psycopg2-binary, pgvector, sentence-transformers, python-dotenv).
    - WEEK2_PROJECT_PATH env var set if Week 2 isn't a sibling folder of
      this project (see src/adapters/week2_agent_adapter.py).

Usage:
    python main.py
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore

    # Load Week 2's own .env (where OPENROUTER_API_KEY / TAVILY_API_KEY live).
    from src.adapters.week2_agent_adapter import _WEEK2_PATH

    load_dotenv(_WEEK2_PATH / ".env")
except ImportError:
    pass

from src.adapters.match_personas_registry import resolve_personas_for_topic, list_known_matches
from src.adapters.week2_agent_adapter import build_week2_agents
from src.graph.agent_graph import AgentGraph
from src.opinion.analyzer import OpinionEvolutionAnalyzer
from src.opinion.tracker import OpinionTracker
from src.orchestration.orchestrator import DiscussionOrchestrator
from src.persistence.discussion_store import DiscussionStore

# Primary tool each persona uses — for retrieval logging.
_AGENT_TOOL_MAP: dict[str, str] = {
    # Argentina × Spain personas
    "arg_esp_tactical_analyst":     "web_search",
    "arg_esp_referee_expert":       "web_search",
    "arg_esp_argentina_fan":        "web_search",
    "arg_esp_spain_fan":            "web_search",
    "arg_esp_neutral_journalist":   "web_search",
    "arg_esp_goalkeeper_expert":    "web_search",
    # France × England personas
    "fra_eng_tactical_analyst":     "web_search",
    "fra_eng_motivation_analyst":   "web_search",
    "fra_eng_france_fan":           "web_search",
    "fra_eng_england_fan":          "web_search",
    "fra_eng_stats_expert":         "web_search",
    "fra_eng_neutral_journalist":   "web_search",
    # Generic fallback personas
    "tactical_analyst":             "web_search",
    "historical_context_analyst":   "web_search",
    "player_spotlight_analyst":     "web_search",
    "fan_narrative_analyst":        "web_search",
    "web_search_analyst":           "web_search",
}


# ---------------------------------------------------------------------------
# User prompt — free-text input
# ---------------------------------------------------------------------------

def _prompt_user_question() -> str:
    """Ask the user to describe the match they want to discuss.

    Accepts any free-text input in Arabic or English. The match is then
    detected automatically from keywords in the input.
    """
    width = 62

    print()
    print("╔" + "═" * width + "╗")
    print(f"║{'  ⚽  FOOTBALL MATCH DISCUSSION SIMULATOR  ⚽':^{width}}║")
    print("╠" + "═" * width + "╣")
    print(f"║  {'اسأل عن أي ماتش تبيه تتناقش فيه:':<{width - 2}}║")
    print(f"║  {'Ask about any match you want to discuss:':<{width - 2}}║")
    print("╠" + "═" * width + "╣")

    known = list_known_matches()
    print(f"║  {'الماتشات المتاحة دلوقتي / Available matches:':<{width - 2}}║")
    for m in known:
        label_line = f"    • {m['label']}"
        print(f"║  {label_line:<{width - 2}}║")

    print("╠" + "═" * width + "╣")
    print(f"║  {'مثال: \"إسبانيا كسبت الأرجنتين\"':<{width - 2}}║")
    print(f"║  {'Example: \"Spain beat Argentina in the final\"':<{width - 2}}║")
    print("╚" + "═" * width + "╝")
    print()

    user_input = input("  سؤالك / Your question: ").strip()
    return user_input


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def _print_match_detected(match_label: str, persona_ids: list[str]) -> None:
    """Print which match was detected and which personas will participate."""
    width = 62
    print()
    print("╔" + "═" * width + "╗")
    print(f"║{'  ✔  MATCH DETECTED':^{width}}║")
    print("╠" + "═" * width + "╣")
    print(f"║  {'Match:':<12}{match_label:<{width - 14}}║")
    print("╠" + "═" * width + "╣")
    print(f"║  {'Personas joining the discussion:':<{width - 2}}║")
    for pid in persona_ids:
        print(f"║      › {pid:<{width - 8}}║")
    print("╚" + "═" * width + "╝")
    print()


def _print_discussion_messages(trace) -> None:
    """Print every agent message, grouped by round, to stdout."""
    for message in trace.messages:
        print(f"\n{'=' * 70}")
        print(f"[Round {message.round_number}] {message.sender_id} -> {message.recipient_ids}")
        print(f"{'=' * 70}")
        print(message.content)


def _print_summary(trace, report: dict, saved_path: Path, export_path: Path) -> None:
    """Print a structured summary box after the discussion completes."""
    trend = report.get("overall_trend", "n/a")
    shifts = report.get("total_shifts_detected", 0)
    rounds = trace.current_round
    num_rounds = trace.num_rounds
    participants = ", ".join(trace.participants)

    width = 70
    line = "═" * width

    def row(label: str, value: str) -> str:
        label_col = f"  {label:<16}"
        val_col = f": {value}"
        content = f"{label_col}{val_col}"
        return f"║{content:<{width}}║"

    print(f"\n╔{line}╗")
    print(f"║{'  DISCUSSION SUMMARY':^{width}}║")
    print(f"╠{line}╣")
    print(row("Discussion ID", trace.discussion_id))
    print(row("Topic", trace.topic[:width - 20]))
    print(row("Participants", participants[:width - 20]))
    print(row("Rounds", f"{rounds}/{num_rounds}"))
    print(row("Termination", trace.termination_reason[:width - 20]))
    print(f"╠{line}╣")
    print(f"║{'  OPINION EVOLUTION':^{width}}║")
    print(f"╠{line}╣")
    print(row("Overall trend", trend))
    print(row("Shifts found", str(shifts)))

    for agent_id, agent_shifts in report.get("agent_trajectories", {}).items():
        short_id = agent_id.replace("_analyst", "").replace("arg_esp_", "").replace("fra_eng_", "")
        shift_labels = [s.get("shift_type", "?") for s in agent_shifts]
        label_str = " → ".join(shift_labels) if shift_labels else "no data yet"
        print(row(f"  {short_id}", label_str[:width - 22]))

    print(f"╠{line}╣")
    print(f"║{'  PERSISTENCE':^{width}}║")
    print(f"╠{line}╣")
    print(row("Saved to", str(saved_path)[:width - 20]))
    print(row("Week 4 export", str(export_path)[:width - 20]))
    print(f"╚{line}╝")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # ── User asks about a match in free text (Arabic or English) ──────────
    user_input = _prompt_user_question()

    if not user_input:
        print("\n  ⚠  No input provided. Exiting.")
        return

    # ── Detect match and resolve personas ────────────────────────────────
    persona_ids, match_label, canonical_topic = resolve_personas_for_topic(user_input)
    _print_match_detected(match_label, persona_ids)

    # ── Build agent graph (ring topology) ────────────────────────────────
    graph = AgentGraph.ring(persona_ids)

    # ── Build the LLM-backed agents ───────────────────────────────────────
    # All new personas use web_search only → game_id is always None.
    conversation_id = f"discussion_{'_'.join(user_input.split()[:3])}"
    print("Building agents (calling the LLM — this may take a while)...\n")
    agents = build_week2_agents(
        topic=canonical_topic,
        game_id=None,
        conversation_id=conversation_id,
        persona_keys=persona_ids,
    )

    # ── Run the discussion ────────────────────────────────────────────────
    orchestrator = DiscussionOrchestrator(graph=graph, agents=agents, num_rounds=3)
    trace = orchestrator.run(topic=canonical_topic)

    # Print every agent message
    _print_discussion_messages(trace)
    print(f"\n{'=' * 70}")
    print("Termination:", trace.termination_reason)

    # ── Mid-discussion retrieval logging ──────────────────────────────────
    for message in trace.messages:
        tool_name = _AGENT_TOOL_MAP.get(message.sender_id, "web_search")
        trace.record_retrieval(
            agent_id=message.sender_id,
            round_number=message.round_number,
            query=f"[{message.sender_id}] tool call for round {message.round_number}: {canonical_topic}",
            evidence=f"[response captured inside agent.speak() via '{tool_name}']",
            tool_name=tool_name,
        )

    # ── Opinion tracking ──────────────────────────────────────────────────
    tracker = OpinionTracker()
    tracked_count = tracker.track_from_messages(trace)
    print(f"\n[Opinion Tracker] Recorded {tracked_count} opinion snapshots.")

    # ── Opinion evolution analysis ────────────────────────────────────────
    analyzer = OpinionEvolutionAnalyzer()
    report = analyzer.generate_evolution_report(trace)

    # ── Persist the discussion ────────────────────────────────────────────
    store = DiscussionStore()
    saved_path = store.save(trace)
    export_path = store.export_for_week4(trace)

    # ── Final summary ─────────────────────────────────────────────────────
    _print_summary(trace, report, saved_path, export_path)


if __name__ == "__main__":
    main()

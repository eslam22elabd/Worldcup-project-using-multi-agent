from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analytics.engine import AnalyticsResult
from src.ingestion.discussion_loader import LoadedDiscussion

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REPORTS_DIR = _PROJECT_ROOT / "reports"


def generate_report(
    analytics: AnalyticsResult,
    discussion: LoadedDiscussion,
    output_path: Path | None = None,
) -> str:
    """Generate and save a Markdown analytics report (Sections 20-22).

    Args:
        analytics: The computed analytics result.
        discussion: The loaded discussion object.
        output_path: Override the default save path (useful for testing).

    Returns:
        The full Markdown string (non-empty as required by Section 21).
    """
    lines: list[str] = []

    # ── Header ─────────────────────────────────────────────────────────────
    lines += [
        f"# Analytics Report — {analytics.discussion_id}",
        "",
        f"**Topic:** {discussion.topic}  ",
        f"**Participants:** {', '.join(discussion.participants)}  ",
        f"**Rounds:** {discussion.num_rounds}  ",
        "",
        "---",
        "",
    ]

    # ── Section 1: Opinion Change ──────────────────────────────────────────
    lines += [
        "## Opinion Change",
        "",
        "Round-to-round stance shifts per agent.",
        "",
        "| Agent | From Round | To Round | Δ Stance |",
        "|-------|-----------|---------|---------|",
    ]
    for agent_id, result in analytics.opinion_change.items():
        if not result.is_computable:
            lines.append(f"| {agent_id} | — | — | *{result.reason}* |")
        else:
            for change in result.changes:
                lines.append(
                    f"| {agent_id} | {change.from_round} | {change.to_round} "
                    f"| {change.change:+.4f} |"
                )
    lines += ["", "---", ""]

    # ── Section 2: Agreement ───────────────────────────────────────────────
    lines += [
        "## Agreement",
        "",
        "Consensus score per round (1.0 = full agreement, 0.0 = maximum polarization).",
        "",
        "| Round | Score | Agents |",
        "|-------|-------|--------|",
    ]
    for item in analytics.agreement:
        if not item.is_computable:
            lines.append(f"| {item.round_number} | *{item.reason}* | — |")
        else:
            lines.append(
                f"| {item.round_number} | {item.score:.4f} | {item.num_agents} |"
            )
    lines += ["", "---", ""]

    # ── Section 3: Influence ───────────────────────────────────────────────
    lines += [
        "## Influence",
        "",
        "DeGroot-inspired influence score per agent (range: [-1.0, 1.0]).",
        "",
        "| Agent | Score | Observations |",
        "|-------|-------|-------------|",
    ]
    for agent_id, result in analytics.influence.items():
        if not result.is_computable:
            lines.append(f"| {agent_id} | *{result.reason}* | — |")
        else:
            lines.append(
                f"| {agent_id} | {result.score:+.4f} | {result.num_observations} |"
            )
    lines += ["", "---", ""]

    # ── Section 4: Sentiment ───────────────────────────────────────────────
    lines += [
        "## Sentiment",
        "",
        "LLM-scored sentiment per message (range: [-1.0, 1.0]).",
        "",
        "| Message ID | Round | Sender | Score |",
        "|-----------|-------|--------|-------|",
    ]
    for result in analytics.sentiment:
        if not result.is_computable:
            lines.append(
                f"| {result.message_id} | {result.round_number} "
                f"| {result.sender} | *{result.reason}* |"
            )
        else:
            lines.append(
                f"| {result.message_id} | {result.round_number} "
                f"| {result.sender} | {result.score:+.4f} |"
            )
    lines += ["", "---", ""]

    report_md = "\n".join(lines)

    # Section 21: validate non-empty
    assert report_md.strip(), "Generated report is unexpectedly empty."

    # Save to disk
    save_path = output_path or (_REPORTS_DIR / "discussion_report.md")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(report_md, encoding="utf-8")

    return report_md

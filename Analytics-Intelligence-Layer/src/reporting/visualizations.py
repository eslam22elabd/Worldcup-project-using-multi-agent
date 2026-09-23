from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — no GUI window needed.

from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_OUTPUTS_DIR = _PROJECT_ROOT / "outputs"


def generate_opinion_trajectory(
    series: dict[str, Any],
    discussion_id: str,
    output_path: Path | None = None,
) -> Path:
    """Plot each agent's stance trajectory across rounds (Section 24).

    Args:
        series: Dict of agent_id -> AgentStanceSeries (from build_stance_series).
        discussion_id: Used in the chart title.
        output_path: Override the default save path (useful for testing).

    Returns:
        The path where the PNG was saved.
    """
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np

    fig, ax = plt.subplots(figsize=(10, 6))

    agents_with_data = [
        (agent_id, s) for agent_id, s in series.items() if s.has_data
    ]

    if not agents_with_data:
        ax.text(0.5, 0.5, "No stance data available", ha="center", va="center",
                transform=ax.transAxes, fontsize=14, color="gray")
    else:
        colours = cm.tab10(np.linspace(0, 1, len(agents_with_data)))
        for (agent_id, agent_series), colour in zip(agents_with_data, colours):
            rounds = [p.round_number for p in agent_series.points]
            stances = [p.stance for p in agent_series.points]
            ax.plot(rounds, stances, marker="o", linewidth=2,
                    label=agent_id, color=colour)
            # Annotate last point with agent name
            ax.annotate(
                agent_id,
                xy=(rounds[-1], stances[-1]),
                xytext=(4, 0),
                textcoords="offset points",
                fontsize=7,
                color=colour,
            )

    ax.axhline(0, color="grey", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.set_xlabel("Round", fontsize=12)
    ax.set_ylabel("Stance (polarity)", fontsize=12)
    ax.set_title(f"Opinion Trajectory — {discussion_id}", fontsize=14, fontweight="bold")
    ax.set_ylim(-1.1, 1.1)
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    save_path = output_path or (_OUTPUTS_DIR / "opinion_trajectory.png")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    return save_path


def generate_interaction_graph(
    discussion: Any,
    influence: dict[str, Any],
    output_path: Path | None = None,
) -> Path:
    """Draw the agent interaction graph (Section 25).

    Nodes = agents. Directed edges = message flows (sender → recipient).
    Edge width is proportional to number of messages. Node colour encodes
    influence score when computable.

    Args:
        discussion: LoadedDiscussion (for rounds_data / participants).
        influence: Dict of agent_id -> AgentInfluenceResult.
        output_path: Override the default save path (useful for testing).

    Returns:
        The path where the PNG was saved.
    """
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    import networkx as nx

    # ── Build directed graph from rounds_data ──────────────────────────────
    G: nx.DiGraph = nx.DiGraph()

    rounds_data = getattr(discussion, "rounds_data", {}) or {}
    edge_counts: dict[tuple[str, str], int] = {}

    for round_key, messages in rounds_data.items():
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            sender = msg.get("sender", "")
            for recipient in msg.get("recipients", []):
                key = (sender, recipient)
                edge_counts[key] = edge_counts.get(key, 0) + 1

    for agent_id in discussion.participants:
        G.add_node(agent_id)

    for (sender, recipient), count in edge_counts.items():
        G.add_edge(sender, recipient, weight=count)

    # ── Node colours from influence score ──────────────────────────────────
    cmap = cm.RdYlGn  # red (negative) → yellow (0) → green (positive)
    norm = mcolors.Normalize(vmin=-1.0, vmax=1.0)
    node_colours = []
    for node in G.nodes():
        infl = influence.get(node)
        if infl and infl.is_computable and infl.score is not None:
            node_colours.append(cmap(norm(infl.score)))
        else:
            node_colours.append("lightgrey")

    # ── Layout + drawing ───────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 8))

    pos = nx.spring_layout(G, seed=42, k=2.5)

    edge_widths = [max(0.5, edge_counts.get((u, v), 1) * 0.5)
                   for u, v in G.edges()]

    nx.draw_networkx_nodes(G, pos, node_color=node_colours,
                           node_size=1200, ax=ax, alpha=0.9)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=7, font_weight="bold")
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edge_color="steelblue",
        width=edge_widths,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=20,
        connectionstyle="arc3,rad=0.1",
        alpha=0.7,
    )

    # Colour bar for influence
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label("Influence Score", fontsize=10)

    ax.set_title(
        f"Interaction Graph — {discussion.discussion_id}\n"
        "(node colour = influence score; edge width = message count)",
        fontsize=13, fontweight="bold",
    )
    ax.axis("off")
    fig.tight_layout()

    save_path = output_path or (_OUTPUTS_DIR / "interaction_graph.png")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    return save_path

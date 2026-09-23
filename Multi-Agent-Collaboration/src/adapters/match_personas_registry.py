"""match_personas_registry.py — Maps user free-text input to match-specific persona sets.

The user types anything naturally (Arabic or English) describing a match.
This module detects which of the two known matches they mean and returns
the correct list of persona IDs for that match.

Supported matches:
  1. Argentina × Spain (2026 World Cup Final)
  2. France × England (2026 World Cup Third Place)

If no known match is detected, falls back to a generic 4-persona web-search set.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Persona ID sets — one per known match
# ---------------------------------------------------------------------------

_ARG_ESP_PERSONAS: list[str] = [
    "arg_esp_tactical_analyst",
    "arg_esp_referee_expert",
    "arg_esp_argentina_fan",
    "arg_esp_spain_fan",
    "arg_esp_neutral_journalist",
    "arg_esp_goalkeeper_expert",
]

_FRA_ENG_PERSONAS: list[str] = [
    "fra_eng_tactical_analyst",
    "fra_eng_motivation_analyst",
    "fra_eng_france_fan",
    "fra_eng_england_fan",
    "fra_eng_stats_expert",
    "fra_eng_neutral_journalist",
]

# Generic fallback personas (all web_search based) — used when the user
# asks about a match that is not one of the two known matches above.
_GENERIC_PERSONAS: list[str] = [
    "tactical_analyst",
    "historical_context_analyst",
    "player_spotlight_analyst",
    "fan_narrative_analyst",
    "web_search_analyst",
]

# ---------------------------------------------------------------------------
# Keyword detection tables
# Arabic + English keywords for each match
# ---------------------------------------------------------------------------

_ARG_ESP_KEYWORDS: list[str] = [
    # English
    "argentina", "spain", "español", "espana", "final",
    "messi", "scaloni", "yamal", "lamine", "de la fuente",
    "enzo", "fernandez", "martinez", "dibu",
    # Arabic
    "الأرجنتين", "اسبانيا", "إسبانيا", "الارجنتين",
    "ميسي", "سكالوني", "يامال", "لامين",
    "النهائي", "الفاينل", "مارتينيز",
]

_FRA_ENG_KEYWORDS: list[str] = [
    # English
    "france", "england", "french", "english", "third",
    "bronze", "third place", "mbappe", "saka", "bellingham",
    "kane", "deschamps", "southgate",
    # Arabic
    "فرنسا", "انجلترا", "إنجلترا",
    "مبابي", "ساكا", "بيلينجهام",
    "المركز الثالث", "البرونزية", "الثالث",
]

# ---------------------------------------------------------------------------
# Match metadata for display purposes
# ---------------------------------------------------------------------------

MATCH_REGISTRY: dict[str, dict] = {
    "argentina_spain": {
        "label": "Argentina × Spain — 2026 World Cup Final",
        "topic": "Argentina vs Spain — 2026 FIFA World Cup Final",
        "persona_ids": _ARG_ESP_PERSONAS,
        "keywords": _ARG_ESP_KEYWORDS,
    },
    "france_england": {
        "label": "France × England — 2026 World Cup Third Place",
        "topic": "France vs England — 2026 FIFA World Cup Third Place Play-off",
        "persona_ids": _FRA_ENG_PERSONAS,
        "keywords": _FRA_ENG_KEYWORDS,
    },
}


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

def detect_match(user_input: str) -> str | None:
    """Detect which known match the user is asking about.

    Checks user_input (case-insensitive, Arabic or English) against each
    match's keyword list. Returns the match key (e.g. 'argentina_spain') or
    None if no match is detected.

    Tie-breaking: if both matches somehow match (shouldn't happen), returns
    the match with the highest keyword hit count.
    """
    normalized = user_input.lower()
    scores: dict[str, int] = {}

    for match_key, info in MATCH_REGISTRY.items():
        score = sum(
            1 for kw in info["keywords"] if kw.lower() in normalized
        )
        if score > 0:
            scores[match_key] = score

    if not scores:
        return None

    # Return the match with the most keyword hits
    return max(scores, key=lambda k: scores[k])


def resolve_personas_for_topic(user_input: str) -> tuple[list[str], str, str]:
    """Resolve persona IDs and canonical topic from free-text user input.

    Args:
        user_input: The raw text the user typed (Arabic or English).

    Returns:
        A tuple of:
            - persona_ids: list of persona YAML ids to load
            - match_label: human-readable match name for display
            - canonical_topic: clean topic string to pass to agents
    """
    match_key = detect_match(user_input)

    if match_key is None:
        # Unknown match — return generic fallback
        return (
            _GENERIC_PERSONAS,
            f"Custom Match: {user_input}",
            user_input,
        )

    info = MATCH_REGISTRY[match_key]
    return (
        info["persona_ids"],
        info["label"],
        info["topic"],
    )


def list_known_matches() -> list[dict]:
    """Return a display list of all known matches and their personas."""
    return [
        {
            "key": k,
            "label": v["label"],
            "persona_count": len(v["persona_ids"]),
            "persona_ids": v["persona_ids"],
        }
        for k, v in MATCH_REGISTRY.items()
    ]

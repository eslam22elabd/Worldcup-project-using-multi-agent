"""Loader/validation tests — README section 27.

Covers: missing opinion snapshots, missing agent IDs, missing round
numbers, duplicate snapshots, empty discussions, and invalid stance
values.
"""

from __future__ import annotations

import json

import pytest

from src.ingestion.discussion_loader import DiscussionValidationError, _validate_and_extract


def _base_export(**overrides) -> dict:
    base = {
        "discussion_id": "disc_test",
        "topic": "Test topic",
        "participants": ["agent_a", "agent_b"],
        "num_rounds": 3,
        "opinion_history": {
            "agent_a": [
                {"agent_id": "agent_a", "round": 1, "stance": {"polarity": 0.2}},
                {"agent_id": "agent_a", "round": 2, "stance": {"polarity": 0.5}},
            ],
            "agent_b": [
                {"agent_id": "agent_b", "round": 1, "stance": {"polarity": -0.3}},
            ],
        },
    }
    base.update(overrides)
    return base


def test_valid_export_loads_with_no_warnings():
    loaded = _validate_and_extract(_base_export(), source="test")
    assert loaded.discussion_id == "disc_test"
    assert len(loaded.snapshots) == 3
    assert not loaded.report.has_warnings


def test_empty_discussion_is_fatal():
    with pytest.raises(DiscussionValidationError):
        _validate_and_extract({"participants": [], "opinion_history": {}}, source="test")


def test_opinion_history_not_a_dict_is_fatal():
    with pytest.raises(DiscussionValidationError):
        _validate_and_extract(
            {"participants": ["a"], "opinion_history": "not a dict"}, source="test"
        )


def test_participant_with_no_opinion_data_produces_warning_not_crash():
    export = _base_export(participants=["agent_a", "agent_b", "agent_c"])
    loaded = _validate_and_extract(export, source="test")
    assert any("agent_c" in w for w in loaded.report.warnings)
    # agent_c should still be a known participant, just with no snapshots later.
    assert "agent_c" in loaded.participants


def test_missing_round_number_is_skipped_with_warning():
    export = _base_export()
    export["opinion_history"]["agent_a"].append(
        {"agent_id": "agent_a", "stance": {"polarity": 0.1}}  # no "round" key
    )
    loaded = _validate_and_extract(export, source="test")
    assert len(loaded.snapshots) == 3  # the malformed one was skipped
    assert any("missing round number" in w for w in loaded.report.warnings)


def test_missing_stance_is_skipped_with_warning():
    export = _base_export()
    export["opinion_history"]["agent_a"].append({"agent_id": "agent_a", "round": 3})
    loaded = _validate_and_extract(export, source="test")
    assert len(loaded.snapshots) == 3
    assert any("missing/malformed stance" in w for w in loaded.report.warnings)


def test_duplicate_round_keeps_first_and_warns():
    export = _base_export()
    export["opinion_history"]["agent_a"].append(
        {"agent_id": "agent_a", "round": 1, "stance": {"polarity": 0.9}}
    )
    loaded = _validate_and_extract(export, source="test")
    agent_a_snapshots = [s for s in loaded.snapshots if s.agent_id == "agent_a" and s.round_number == 1]
    assert len(agent_a_snapshots) == 1
    assert agent_a_snapshots[0].stance == 0.2  # first occurrence kept, not 0.9
    assert any("duplicate snapshot" in w for w in loaded.report.warnings)


def test_out_of_range_stance_is_clamped_with_warning():
    export = _base_export()
    export["opinion_history"]["agent_a"].append(
        {"agent_id": "agent_a", "round": 3, "stance": {"polarity": 5.0}}
    )
    loaded = _validate_and_extract(export, source="test")
    clamped = next(s for s in loaded.snapshots if s.agent_id == "agent_a" and s.round_number == 3)
    assert clamped.stance == 1.0
    assert any("clamped" in w for w in loaded.report.warnings)


def test_all_snapshots_invalid_is_fatal():
    export = {
        "discussion_id": "disc_test",
        "participants": ["agent_a"],
        "opinion_history": {"agent_a": [{"agent_id": "agent_a", "round": None}]},
    }
    with pytest.raises(DiscussionValidationError):
        _validate_and_extract(export, source="test")


def test_agent_with_opinions_but_not_a_listed_participant_is_included_with_warning():
    export = _base_export()
    export["opinion_history"]["agent_c"] = [
        {"agent_id": "agent_c", "round": 1, "stance": {"polarity": 0.1}}
    ]
    loaded = _validate_and_extract(export, source="test")
    assert any(s.agent_id == "agent_c" for s in loaded.snapshots)
    assert any("not listed in" in w for w in loaded.report.warnings)

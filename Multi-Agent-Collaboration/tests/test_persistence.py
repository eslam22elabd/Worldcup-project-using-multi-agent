from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.discussion.message import Message
from src.persistence.discussion_store import DiscussionStore
from src.state.discussion_state import DiscussionState, DiscussionStatus


@pytest.fixture
def temp_store(tmp_path: Path) -> tuple[DiscussionStore, Path]:
    store = DiscussionStore(base_dir=tmp_path)
    return store, tmp_path


@pytest.fixture
def sample_state() -> DiscussionState:
    state = DiscussionState(
        topic="World Cup Tactical Analysis",
        graph_config={"nodes": ["analyst_a", "analyst_b"], "edges": {"analyst_a": ["analyst_b"], "analyst_b": ["analyst_a"]}},
        num_rounds=3,
        metadata={"match_id": 1953853},
    )
    state.start_round(1)

    msg1 = Message(
        round_number=1,
        sender_id="analyst_a",
        recipient_ids=["analyst_b"],
        content="South Africa played disciplined in the opening 20 minutes.",
    )
    msg2 = Message(
        round_number=1,
        sender_id="analyst_b",
        recipient_ids=["analyst_a"],
        content="Mexico's transition speed caused immediate problems on counter-attacks.",
    )
    state.add_message(msg1)
    state.add_message(msg2)

    state.record_opinion(
        agent_id="analyst_a",
        round_number=1,
        opinion="South Africa organized defensively.",
        stance={"polarity": 0.4, "confidence": 0.85},
    )
    state.record_opinion(
        agent_id="analyst_b",
        round_number=1,
        opinion="Mexico controls tempo.",
        stance={"polarity": 0.7, "confidence": 0.90},
    )

    state.record_retrieval(
        agent_id="analyst_a",
        round_number=1,
        query="South Africa vs Mexico 2010 goals",
        evidence=["Tshabalala scored in 55th min", "Marquez equalized in 79th min"],
        tool_name="get_knowledge",
    )

    state.finish_round(1)
    state.complete("Finished 3-round test run.")
    return state


def test_save_and_load_roundtrip_lossless(temp_store: tuple[DiscussionStore, Path], sample_state: DiscussionState) -> None:
    store, tmp_path = temp_store

    saved_path = store.save(sample_state)
    assert saved_path.exists()
    assert saved_path.name == f"{sample_state.discussion_id}.json"

    loaded_state = store.load(sample_state.discussion_id)

    assert loaded_state.discussion_id == sample_state.discussion_id
    assert loaded_state.topic == sample_state.topic
    assert loaded_state.status == DiscussionStatus.COMPLETED
    assert loaded_state.current_round == sample_state.current_round
    assert loaded_state.num_rounds == sample_state.num_rounds
    assert loaded_state.participants == sample_state.participants
    assert loaded_state.termination_reason == sample_state.termination_reason
    assert len(loaded_state.messages) == 2
    assert loaded_state.messages[0].content == sample_state.messages[0].content
    assert loaded_state.messages[1].sender_id == "analyst_b"
    assert len(loaded_state.opinions["analyst_a"]) == 1
    assert loaded_state.opinions["analyst_a"][0]["stance"]["polarity"] == 0.4
    assert len(loaded_state.retrieval_events) == 1
    assert loaded_state.retrieval_events[0]["query"] == "South Africa vs Mexico 2010 goals"
    assert loaded_state.metadata == {"match_id": 1953853}


def test_exists_and_delete(temp_store: tuple[DiscussionStore, Path], sample_state: DiscussionState) -> None:
    store, _ = temp_store

    assert not store.exists(sample_state.discussion_id)
    store.save(sample_state)
    assert store.exists(sample_state.discussion_id)

    deleted = store.delete(sample_state.discussion_id)
    assert deleted is True
    assert not store.exists(sample_state.discussion_id)
    assert store.delete("nonexistent_id") is False


def test_list_discussions(temp_store: tuple[DiscussionStore, Path], sample_state: DiscussionState) -> None:
    store, _ = temp_store

    state2 = DiscussionState(
        topic="Second Topic",
        participants=["analyst_c"],
        num_rounds=3,
    )
    state2.complete("Done")

    store.save(sample_state)
    store.save(state2)

    summaries = store.list_discussions()
    assert len(summaries) == 2

    disc_ids = {s["discussion_id"] for s in summaries}
    assert sample_state.discussion_id in disc_ids
    assert state2.discussion_id in disc_ids

    sample_summary = next(s for s in summaries if s["discussion_id"] == sample_state.discussion_id)
    assert sample_summary["topic"] == "World Cup Tactical Analysis"
    assert sample_summary["message_count"] == 2
    assert sample_summary["opinions_count"] == 2
    assert sample_summary["retrievals_count"] == 1
    assert sample_summary["status"] == DiscussionStatus.COMPLETED.value


def test_load_nonexistent_raises_filenotfound(temp_store: tuple[DiscussionStore, Path]) -> None:
    store, _ = temp_store
    with pytest.raises(FileNotFoundError, match="not found at"):
        store.load("unknown_discussion_123")


def test_save_empty_id_raises_value_error(temp_store: tuple[DiscussionStore, Path]) -> None:
    store, _ = temp_store
    state = DiscussionState(topic="Test", num_rounds=3)
    state.discussion_id = ""
    with pytest.raises(ValueError, match="empty discussion_id"):
        store.save(state)


def test_corrupted_json_raises_value_error(temp_store: tuple[DiscussionStore, Path]) -> None:
    store, tmp_path = temp_store
    corrupted_file = tmp_path / "corrupted_run.json"
    with open(corrupted_file, "w") as f:
        f.write("{ invalid json content ...")

    with pytest.raises(ValueError, match="Corrupted discussion file"):
        store.load("corrupted_run")


def test_export_for_week4(temp_store: tuple[DiscussionStore, Path], sample_state: DiscussionState, tmp_path: Path) -> None:
    store, _ = temp_store
    export_file = tmp_path / "week4_test_export.json"

    out_path = store.export_for_week4(sample_state, output_path=export_file)
    assert out_path.exists()

    with open(out_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["discussion_id"] == sample_state.discussion_id
    assert data["topic"] == sample_state.topic
    assert "round_1" in data["rounds"]
    assert len(data["rounds"]["round_1"]) == 2
    assert "analyst_a" in data["opinion_history"]
    assert len(data["opinion_history"]["analyst_a"]) == 1
    assert len(data["retrieval_events"]) == 1

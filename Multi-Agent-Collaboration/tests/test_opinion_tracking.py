from __future__ import annotations

import pytest

from src.discussion.message import Message
from src.opinion.analyzer import OpinionEvolutionAnalyzer
from src.opinion.models import (
    OpinionShift,
    OpinionShiftType,
    OpinionSnapshot,
    Stance,
)
from src.opinion.tracker import OpinionTracker
from src.state.discussion_state import DiscussionState


@pytest.fixture
def state() -> DiscussionState:
    return DiscussionState(
        topic="Mexico vs South Africa — World Cup",
        participants=["analyst_a", "analyst_b", "analyst_c"],
        num_rounds=3,
    )


@pytest.fixture
def tracker() -> OpinionTracker:
    # Tests always supply an explicit Stance, so the LLM judge is never called.
    return OpinionTracker()


@pytest.fixture
def analyzer() -> OpinionEvolutionAnalyzer:
    return OpinionEvolutionAnalyzer(polarity_threshold=0.10)


def test_initial_and_multi_round_opinion_recording(state: DiscussionState, tracker: OpinionTracker) -> None:
    init_snap = tracker.record_initial_opinion(
        state=state,
        agent_id="analyst_a",
        opinion="Mexico has superior attacking talent but vulnerable defensive transitions.",
        stance=Stance(polarity=0.3),
    )
    assert init_snap.is_initial is True
    assert init_snap.round_number == 0
    assert init_snap.agent_id == "analyst_a"
    assert init_snap.stance.polarity == 0.3

    tracker.record_round_opinion(
        state=state,
        agent_id="analyst_a",
        round_number=1,
        opinion="First-half metrics show Mexico controlling midfield possession decisively.",
        stance=Stance(polarity=0.6),
    )
    tracker.record_round_opinion(
        state=state,
        agent_id="analyst_a",
        round_number=2,
        opinion="South Africa scored on a rapid counter; Mexico's defense broke down.",
        stance=Stance(polarity=-0.2),
    )
    tracker.record_round_opinion(
        state=state,
        agent_id="analyst_a",
        round_number=3,
        opinion="Marquez equalizer salvaged a fair draw; both teams showed equal tactical merits.",
        stance=Stance(polarity=0.05),
    )

    history = tracker.get_agent_history(state, "analyst_a")
    assert len(history) == 4
    assert [s.round_number for s in history] == [0, 1, 2, 3]
    assert [s.stance.polarity for s in history] == [0.3, 0.6, -0.2, 0.05]


def test_stance_numerical_bounds() -> None:
    """Polarity is clamped to [-1, 1]."""
    extreme_stance = Stance(polarity=2.5)
    assert extreme_stance.polarity == 1.0

    neg_extreme = Stance(polarity=-3.0)
    assert neg_extreme.polarity == -1.0

    data = extreme_stance.to_dict()
    assert set(data.keys()) == {"polarity"}
    reconstructed = Stance.from_dict(data)
    assert reconstructed.polarity == 1.0


def test_stance_from_dict_ignores_old_fields() -> None:
    """from_dict should silently ignore confidence/agreement_score from old exports."""
    old_record = {"polarity": -0.5, "confidence": 0.8, "agreement_score": 0.6, "key_arguments": []}
    s = Stance.from_dict(old_record)
    assert s.polarity == -0.5
    # Only polarity key in new output
    assert list(s.to_dict().keys()) == ["polarity"]


def test_opinion_shift_classification_strengthened(analyzer: OpinionEvolutionAnalyzer) -> None:
    s1 = OpinionSnapshot(agent_id="a", round_number=1, opinion_text="Good", stance=Stance(polarity=0.4))
    s2 = OpinionSnapshot(agent_id="a", round_number=2, opinion_text="Great", stance=Stance(polarity=0.7))

    shift = analyzer.detect_shift(s1, s2)
    assert shift.shift_type == OpinionShiftType.STRENGTHENED
    assert shift.from_round == 1
    assert shift.to_round == 2
    assert shift.delta_polarity == pytest.approx(0.3)
    # No delta_confidence in the shift anymore
    assert not hasattr(shift, "delta_confidence")


def test_opinion_shift_classification_weakened(analyzer: OpinionEvolutionAnalyzer) -> None:
    s1 = OpinionSnapshot(agent_id="a", round_number=1, opinion_text="Very positive", stance=Stance(polarity=0.8))
    s2 = OpinionSnapshot(agent_id="a", round_number=2, opinion_text="Somewhat positive", stance=Stance(polarity=0.4))

    shift = analyzer.detect_shift(s1, s2)
    assert shift.shift_type == OpinionShiftType.WEAKENED
    assert shift.delta_polarity == pytest.approx(-0.4)


def test_opinion_shift_classification_reversed(analyzer: OpinionEvolutionAnalyzer) -> None:
    s1 = OpinionSnapshot(agent_id="a", round_number=1, opinion_text="Favoring Mexico", stance=Stance(polarity=0.5))
    s2 = OpinionSnapshot(agent_id="a", round_number=2, opinion_text="Favoring South Africa", stance=Stance(polarity=-0.5))

    shift = analyzer.detect_shift(s1, s2)
    assert shift.shift_type == OpinionShiftType.REVERSED


def test_opinion_shift_classification_unchanged(analyzer: OpinionEvolutionAnalyzer) -> None:
    s1 = OpinionSnapshot(agent_id="a", round_number=1, opinion_text="Balanced", stance=Stance(polarity=0.30))
    s2 = OpinionSnapshot(agent_id="a", round_number=2, opinion_text="Balanced again", stance=Stance(polarity=0.32))

    shift = analyzer.detect_shift(s1, s2)
    assert shift.shift_type == OpinionShiftType.UNCHANGED


def test_section_19_acceptance_criteria_inspection(state: DiscussionState, tracker: OpinionTracker, analyzer: OpinionEvolutionAnalyzer) -> None:
    tracker.record_initial_opinion(state, "analyst_a", "Initial: Mexico has the edge.", Stance(polarity=0.5))
    tracker.record_round_opinion(state, "analyst_a", 1, "R1: Reaffirmed Mexico's superiority.", Stance(polarity=0.7))
    tracker.record_round_opinion(state, "analyst_a", 2, "R2: Tshabalala goal shifted my view.", Stance(polarity=-0.3))
    tracker.record_round_opinion(state, "analyst_a", 3, "R3: Final draw settles the debate.", Stance(polarity=0.0))

    shifts = analyzer.analyze_agent_evolution(state, "analyst_a")

    assert len(shifts) == 3

    assert shifts[0].from_round == 0
    assert shifts[0].to_round == 1
    assert shifts[0].shift_type == OpinionShiftType.STRENGTHENED

    assert shifts[1].from_round == 1
    assert shifts[1].to_round == 2
    assert shifts[1].shift_type == OpinionShiftType.REVERSED

    assert shifts[2].from_round == 2
    assert shifts[2].to_round == 3
    assert shifts[2].shift_type in {OpinionShiftType.SHIFTED, OpinionShiftType.WEAKENED}


def test_group_consensus_trajectory(state: DiscussionState, tracker: OpinionTracker, analyzer: OpinionEvolutionAnalyzer) -> None:
    tracker.record_round_opinion(state, "analyst_a", 1, "Pro", Stance(polarity=0.8))
    tracker.record_round_opinion(state, "analyst_b", 1, "Anti", Stance(polarity=-0.8))

    tracker.record_round_opinion(state, "analyst_a", 2, "Compromise", Stance(polarity=0.1))
    tracker.record_round_opinion(state, "analyst_b", 2, "Compromise", Stance(polarity=-0.1))

    trajectory = analyzer.compute_consensus_trajectory(state)

    assert 1 in trajectory
    assert 2 in trajectory
    assert trajectory[1]["std_polarity"] > trajectory[2]["std_polarity"]
    assert trajectory[2]["consensus_index"] > trajectory[1]["consensus_index"]
    # No mean_confidence in trajectory anymore
    assert "mean_confidence" not in trajectory[1]


def test_track_from_messages_uses_provided_stance(state: DiscussionState, tracker: OpinionTracker) -> None:
    """record_round_opinion with explicit stance bypasses the LLM judge entirely."""
    tracker.record_round_opinion(
        state=state,
        agent_id="analyst_a",
        round_number=1,
        opinion="Mexico dominated the first half.",
        stance=Stance(polarity=0.8),
    )
    assert tracker.has_opinion(state, "analyst_a", 1)
    history = tracker.get_agent_history(state, "analyst_a")
    assert history[0].stance.polarity == 0.8
    assert history[0].metadata.get("extracted_automatically") is False


def test_stance_serialization_roundtrip() -> None:
    """Stance survives a to_dict / from_dict round-trip cleanly."""
    original = Stance(polarity=-0.73)
    restored = Stance.from_dict(original.to_dict())
    assert restored.polarity == pytest.approx(-0.73, abs=0.0001)





def test_initial_and_multi_round_opinion_recording(state: DiscussionState, tracker: OpinionTracker) -> None:
    init_snap = tracker.record_initial_opinion(
        state=state,
        agent_id="analyst_a",
        opinion="Mexico has superior attacking talent but vulnerable defensive transitions.",
        stance=Stance(polarity=0.3, confidence=0.75, key_arguments=["Transition vulnerability"]),
    )
    assert init_snap.is_initial is True
    assert init_snap.round_number == 0
    assert init_snap.agent_id == "analyst_a"
    assert init_snap.stance.polarity == 0.3

    tracker.record_round_opinion(
        state=state,
        agent_id="analyst_a",
        round_number=1,
        opinion="First-half metrics show Mexico controlling midfield possession decisively.",
        stance=Stance(polarity=0.6, confidence=0.85),
    )
    tracker.record_round_opinion(
        state=state,
        agent_id="analyst_a",
        round_number=2,
        opinion="South Africa scored on a rapid counter; Mexico's defense broke down.",
        stance=Stance(polarity=-0.2, confidence=0.90),
    )
    tracker.record_round_opinion(
        state=state,
        agent_id="analyst_a",
        round_number=3,
        opinion="Marquez equalizer salvaged a fair draw; both teams showed equal tactical merits.",
        stance=Stance(polarity=0.05, confidence=0.80),
    )

    history = tracker.get_agent_history(state, "analyst_a")
    assert len(history) == 4
    assert [s.round_number for s in history] == [0, 1, 2, 3]
    assert [s.stance.polarity for s in history] == [0.3, 0.6, -0.2, 0.05]


def test_stance_numerical_bounds_and_semantics() -> None:
    extreme_stance = Stance(polarity=2.5, confidence=-0.5, agreement_score=1.5)
    assert extreme_stance.polarity == 1.0
    assert extreme_stance.confidence == 0.0
    assert extreme_stance.agreement_score == 1.0

    data = extreme_stance.to_dict()
    reconstructed = Stance.from_dict(data)
    assert reconstructed.polarity == 1.0
    assert reconstructed.confidence == 0.0


def test_offline_heuristic_stance_extractor() -> None:
    extractor = StanceExtractor()

    pos_stance = extractor.extract(
        "Mexico displayed dominant ball control, superior passing, and masterclass tactical execution."
    )
    assert pos_stance.polarity > 0.3
    assert pos_stance.confidence >= 0.7

    neg_stance = extractor.extract(
        "South Africa suffered from weak pressing, poor marking, and a defensive collapse."
    )
    assert neg_stance.polarity < -0.3

    uncertain_stance = extractor.extract(
        "Perhaps there could be an error, or maybe the data suggests a preliminary risk."
    )
    assert uncertain_stance.confidence < 0.7


def test_opinion_shift_classification_strengthened(analyzer: OpinionEvolutionAnalyzer) -> None:
    s1 = OpinionSnapshot(agent_id="a", round_number=1, opinion_text="Good", stance=Stance(polarity=0.4, confidence=0.7))
    s2 = OpinionSnapshot(agent_id="a", round_number=2, opinion_text="Great", stance=Stance(polarity=0.7, confidence=0.85))

    shift = analyzer.detect_shift(s1, s2)
    assert shift.shift_type == OpinionShiftType.STRENGTHENED
    assert shift.from_round == 1
    assert shift.to_round == 2
    assert shift.delta_polarity == pytest.approx(0.3)


def test_opinion_shift_classification_weakened(analyzer: OpinionEvolutionAnalyzer) -> None:
    s1 = OpinionSnapshot(agent_id="a", round_number=1, opinion_text="Very positive", stance=Stance(polarity=0.8, confidence=0.9))
    s2 = OpinionSnapshot(agent_id="a", round_number=2, opinion_text="Somewhat positive", stance=Stance(polarity=0.4, confidence=0.7))

    shift = analyzer.detect_shift(s1, s2)
    assert shift.shift_type == OpinionShiftType.WEAKENED
    assert shift.delta_polarity == pytest.approx(-0.4)


def test_opinion_shift_classification_reversed(analyzer: OpinionEvolutionAnalyzer) -> None:
    s1 = OpinionSnapshot(agent_id="a", round_number=1, opinion_text="Favoring Mexico", stance=Stance(polarity=0.5, confidence=0.8))
    s2 = OpinionSnapshot(agent_id="a", round_number=2, opinion_text="Favoring South Africa", stance=Stance(polarity=-0.5, confidence=0.8))

    shift = analyzer.detect_shift(s1, s2)
    assert shift.shift_type == OpinionShiftType.REVERSED


def test_opinion_shift_classification_unchanged(analyzer: OpinionEvolutionAnalyzer) -> None:
    s1 = OpinionSnapshot(agent_id="a", round_number=1, opinion_text="Balanced", stance=Stance(polarity=0.30, confidence=0.80))
    s2 = OpinionSnapshot(agent_id="a", round_number=2, opinion_text="Balanced again", stance=Stance(polarity=0.32, confidence=0.82))

    shift = analyzer.detect_shift(s1, s2)
    assert shift.shift_type == OpinionShiftType.UNCHANGED


def test_section_19_acceptance_criteria_inspection(state: DiscussionState, tracker: OpinionTracker, analyzer: OpinionEvolutionAnalyzer) -> None:
    tracker.record_initial_opinion(state, "analyst_a", "Initial: Mexico has the edge.", Stance(polarity=0.5))
    tracker.record_round_opinion(state, "analyst_a", 1, "R1: Reaffirmed Mexico's superiority.", Stance(polarity=0.7))
    tracker.record_round_opinion(state, "analyst_a", 2, "R2: Tshabalala goal shifted my view.", Stance(polarity=-0.3))
    tracker.record_round_opinion(state, "analyst_a", 3, "R3: Final draw settles the debate.", Stance(polarity=0.0))

    shifts = analyzer.analyze_agent_evolution(state, "analyst_a")

    assert len(shifts) == 3

    assert shifts[0].from_round == 0
    assert shifts[0].to_round == 1
    assert shifts[0].shift_type == OpinionShiftType.STRENGTHENED

    assert shifts[1].from_round == 1
    assert shifts[1].to_round == 2
    assert shifts[1].shift_type == OpinionShiftType.REVERSED

    assert shifts[2].from_round == 2
    assert shifts[2].to_round == 3
    assert shifts[2].shift_type in {OpinionShiftType.SHIFTED, OpinionShiftType.WEAKENED}


def test_group_consensus_trajectory(state: DiscussionState, tracker: OpinionTracker, analyzer: OpinionEvolutionAnalyzer) -> None:
    tracker.record_round_opinion(state, "analyst_a", 1, "Pro", Stance(polarity=0.8))
    tracker.record_round_opinion(state, "analyst_b", 1, "Anti", Stance(polarity=-0.8))

    tracker.record_round_opinion(state, "analyst_a", 2, "Compromise", Stance(polarity=0.1))
    tracker.record_round_opinion(state, "analyst_b", 2, "Compromise", Stance(polarity=-0.1))

    trajectory = analyzer.compute_consensus_trajectory(state)

    assert 1 in trajectory
    assert 2 in trajectory
    assert trajectory[1]["std_polarity"] > trajectory[2]["std_polarity"]
    assert trajectory[2]["consensus_index"] > trajectory[1]["consensus_index"]


def test_track_from_messages_integration(state: DiscussionState, tracker: OpinionTracker) -> None:
    state.start_round(1)
    state.add_message(Message(round_number=1, sender_id="analyst_a", recipient_ids=["analyst_b"], content="Mexico dominant."))
    state.add_message(Message(round_number=1, sender_id="analyst_b", recipient_ids=["analyst_a"], content="Defense is weak."))

    added = tracker.track_from_messages(state)
    assert added == 2

    added_again = tracker.track_from_messages(state)
    assert added_again == 0

    assert tracker.has_opinion(state, "analyst_a", 1)
    assert tracker.has_opinion(state, "analyst_b", 1)

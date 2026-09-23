/**
 * normalizeDiscussion — adapts the real backend's DiscussionResponse
 * shape (arrays, "agent"/"text" fields) to the same shape as a raw
 * Week 3 export (object keyed by "round_N", "sender"/"content" fields),
 * which is what DiscussionView.jsx / sample_discussion.json already use.
 *
 * This means DiscussionView never needs to know or care whether its
 * data came from the bundled sample file or the live backend --
 * exactly one shape in, regardless of source.
 */

export function normalizeDiscussion(raw) {
  if (!raw) return raw;

  // Already in the Week 3 export shape (e.g. the bundled sample) --
  // nothing to do.
  if (raw.rounds && !Array.isArray(raw.rounds)) {
    return raw;
  }

  const rounds = {};
  for (const round of raw.rounds || []) {
    rounds[`round_${round.round}`] = (round.messages || []).map((m) => ({
      round: round.round,
      sender: m.agent,
      recipients: [], // the real backend doesn't expose per-message recipients yet
      content: m.text,
      id: m.message_id,
    }));
  }

  return {
    discussion_id: raw.discussion_id,
    topic: raw.topic,
    participants: raw.agents || [],
    num_rounds: raw.num_rounds,
    rounds,
  };
}
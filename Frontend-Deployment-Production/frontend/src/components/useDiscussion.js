/**
 * useDiscussion — loads a discussion for DiscussionView to render.
 *
 * Two sources, one output shape (see normalizeDiscussion.js):
 *   - source: "sample"  -> the bundled real Week 3 export. Kept per
 *                          README section 27 (mock data is explicitly
 *                          allowed) as a fallback for offline dev/demo.
 *   - source: "backend" -> the real backend's GET /discussions/{id}.
 *
 * Call sites decide which to use (e.g. a toggle in App.jsx) --
 * DiscussionView itself never knows which source was used.
 */

import { useEffect, useState } from "react";
import sampleDiscussion from "../data/sample_discussion.json";
import { fetchDiscussion } from "../api/discussionApi";
import { normalizeDiscussion } from "./normalizeDiscussion";

export function useDiscussion(discussionId, source = "sample") {
  const [discussion, setDiscussion] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    async function load() {
      try {
        if (source === "sample") {
          if (!cancelled) setDiscussion(normalizeDiscussion(sampleDiscussion));
          return;
        }
        const data = await fetchDiscussion(discussionId);
        if (!cancelled) setDiscussion(normalizeDiscussion(data));
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load discussion.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [discussionId, source]);

  return { discussion, error, loading };
}
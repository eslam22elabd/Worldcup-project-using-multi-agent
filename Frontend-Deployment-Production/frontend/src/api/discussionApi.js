/**
 * API client for endpoints this person's UI consumes but does not own.
 *
 * GET /topics and GET /discussions/{id} belong to Person 1 (Backend
 * Core) per the team split. This file only documents/calls the
 * contract; it never implements backend logic.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchTopics() {
  const res = await fetch(`${API_BASE}/topics`);
  if (!res.ok) {
    throw new Error(`Failed to load topics (${res.status})`);
  }
  return res.json();
}

export async function fetchDiscussion(discussionId) {
  const res = await fetch(`${API_BASE}/discussions/${discussionId}`);
  if (!res.ok) {
    throw new Error(`Failed to load discussion ${discussionId} (${res.status})`);
  }
  return res.json();
}

export async function createDiscussion(topic) {
  const res = await fetch(`${API_BASE}/discussions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  if (!res.ok) {
    throw new Error(`Failed to start discussion (${res.status})`);
  }
  return res.json();
}

export async function searchKnowledgeBase(query, topK = 3) {
  const res = await fetch(`${API_BASE}/retrieval/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) {
    throw new Error(`Retrieval request failed (${res.status})`);
  }
  return res.json();
}

export async function fetchAnalytics(discussionId) {
  const res = await fetch(`${API_BASE}/discussions/${discussionId}/analytics`);
  if (!res.ok) {
    throw new Error(`Failed to load analytics for ${discussionId} (${res.status})`);
  }
  return res.json();
}

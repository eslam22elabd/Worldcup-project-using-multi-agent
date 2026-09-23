/**
 * DiscussionView — README sections 10, 11, 12.
 *
 * Renders a Week 3 discussion as a match-day analysis rundown: one
 * timeline entry per round, with each agent's message attributed
 * clearly and rounds visually separated.
 *
 * Each message is collapsed by default, showing only the agent name
 * and a short preview; clicking it expands to show the full message
 * content (details-on-demand, per the user's request).
 *
 * Mode: Replay only (README section 12 explicitly allows this). This
 * component takes a fully-loaded discussion object as a prop.
 */

import { useState } from "react";
import "./DiscussionView.css";
import { stripMarkdown } from "./stripMarkdown";

const AGENT_COLOR_COUNT = 6;
const PREVIEW_LENGTH = 60;

function agentColorVar(agentId) {
  let hash = 0;
  for (let i = 0; i < agentId.length; i++) {
    hash = (hash * 31 + agentId.charCodeAt(i)) >>> 0;
  }
  return `var(--agent-color-${hash % AGENT_COLOR_COUNT})`;
}

function formatAgentName(agentId) {
  return agentId.replace(/_/g, " ");
}

function sortedRoundKeys(rounds) {
  return Object.keys(rounds).sort(
    (a, b) => parseInt(a.split("_")[1], 10) - parseInt(b.split("_")[1], 10)
  );
}

function RoundMarker({ roundNumber }) {
  return (
    <div className="round-block__marker" aria-hidden="true">
      {roundNumber}
    </div>
  );
}

function MessageEntry({ message }) {
  const [expanded, setExpanded] = useState(false);
  const cleanContent = stripMarkdown(message.content);
  const preview =
    cleanContent.length > PREVIEW_LENGTH
      ? `${cleanContent.slice(0, PREVIEW_LENGTH)}…`
      : cleanContent;

  return (
    <div
      className="message-entry"
      style={{ "--agent-color": agentColorVar(message.sender) }}
    >
      <button
        type="button"
        className="message-entry__header"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span
          className={`message-entry__chevron${expanded ? " message-entry__chevron--open" : ""}`}
        >
          ▸
        </span>
        <span className="message-entry__agent">
          {formatAgentName(message.sender)}
          {message.recipients && message.recipients.length > 0 && (
            <span className="message-entry__recipients">
              {" "}
              → {message.recipients.map(formatAgentName).join(", ")}
            </span>
          )}
        </span>
        {!expanded && <span className="message-entry__preview">{preview}</span>}
      </button>
      {expanded && <p className="message-entry__content">{cleanContent}</p>}
    </div>
  );
}

export default function DiscussionView({ discussion }) {
  if (!discussion) {
    return <div className="discussion-view__empty">No discussion loaded.</div>;
  }

  const roundKeys = sortedRoundKeys(discussion.rounds || {});

  if (roundKeys.length === 0) {
    return <div className="discussion-view__empty">This discussion has no rounds yet.</div>;
  }

  return (
    <div className="discussion-view">
      <header className="discussion-view__header">
        <h1 className="discussion-view__topic">{discussion.topic}</h1>
        <div className="discussion-view__participants">
          {(discussion.participants || []).map((agentId) => (
            <span key={agentId} className="participant-tag">
              {formatAgentName(agentId)}
            </span>
          ))}
        </div>
      </header>

      {roundKeys.map((roundKey) => {
        const roundNumber = roundKey.split("_")[1];
        const messages = discussion.rounds[roundKey];
        return (
          <div className="round-block" key={roundKey}>
            <RoundMarker roundNumber={roundNumber} />
            <div className="round-block__body">
              {messages.map((message) => (
                <MessageEntry key={message.id || `${message.sender}-${message.round}`} message={message} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

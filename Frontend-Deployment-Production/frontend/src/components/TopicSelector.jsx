/**
 * TopicSelector — README section 9.
 *
 * Combines a predefined-topics dropdown with a free-text field (both
 * options the README explicitly allows), so a reviewer can either pick
 * a known sample discussion or type a new topic to start one.
 */

import { useState } from "react";
import "./TopicSelector.css";

export default function TopicSelector({ predefinedTopics = [], onStart }) {
  const [customTopic, setCustomTopic] = useState("");
  const [selected, setSelected] = useState("");

  function handleStart() {
    const topic = customTopic.trim() || selected;
    if (topic) onStart(topic);
  }

  return (
    <div className="topic-selector">
      <h2 className="topic-selector__title">Select a discussion topic</h2>

      {predefinedTopics.length > 0 && (
        <label className="topic-selector__field">
          <span>Choose a sample match</span>
          <select
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              setCustomTopic("");
            }}
          >
            <option value="">— Select —</option>
            {predefinedTopics.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className="topic-selector__field">
        <span>Or enter your own</span>
        <input
          type="text"
          placeholder="e.g. Mexico vs South Africa — World Cup Grp. A"
          value={customTopic}
          onChange={(e) => {
            setCustomTopic(e.target.value);
            setSelected("");
          }}
        />
      </label>

      <button
        className="topic-selector__submit"
        disabled={!customTopic.trim() && !selected}
        onClick={handleStart}
      >
        Start discussion
      </button>
    </div>
  );
}

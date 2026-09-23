import { useState } from "react";
import "./AnalyticsView.css";

function formatAgentName(id) {
  if (!id) return "Unknown";
  return id
    .replace(/^arg_esp_|^fra_eng_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AnalyticsView({ analytics, discussion }) {
  const [activeTab, setActiveTab] = useState("overview");

  if (!analytics) {
    return (
      <div className="analytics-empty">
        <p>No analytics data available for this discussion.</p>
      </div>
    );
  }

  const {
    discussion_id,
    opinion_change = {},
    agreement = [],
    influence = {},
    sentiment = [],
    stances = {},
    interaction_graph = {},
  } = analytics;

  const participants =
    discussion?.participants ||
    interaction_graph.nodes ||
    Object.keys(stances).length > 0
      ? Object.keys(stances)
      : Object.keys(opinion_change);

  // Compute average agreement
  const computableAgreements = agreement.filter((a) => a.is_computable && typeof a.score === "number");
  const avgAgreement =
    computableAgreements.length > 0
      ? (
          computableAgreements.reduce((sum, a) => sum + a.score, 0) /
          computableAgreements.length
        ).toFixed(2)
      : "N/A";

  // Influence sorted
  const sortedInfluence = Object.entries(influence)
    .filter(([_, data]) => data && (data.is_computable !== false || typeof data.score === "number"))
    .sort((a, b) => (b[1].score || 0) - (a[1].score || 0));

  return (
    <div className="analytics-container">
      {/* Header */}
      <header className="analytics-header">
        <div>
          <span className="analytics-badge">Intelligence & Analytics Engine</span>
          <h2 className="analytics-title">Discussion Intelligence & Analytics</h2>
          <p className="analytics-subtitle">
            Discussion: <code>{discussion_id}</code> | Participants: {participants.length} agents
          </p>
        </div>
      </header>

      {/* KPI Cards */}
      <div className="analytics-kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Rounds Analyzed</span>
          <span className="kpi-value">{agreement.length || discussion?.num_rounds || 3}</span>
          <span className="kpi-subtext">Complete round history</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Final Agreement Score</span>
          <span className="kpi-value">
            {agreement.length > 0 && agreement[agreement.length - 1].is_computable
              ? `${(agreement[agreement.length - 1].score * 100).toFixed(0)}%`
              : `${avgAgreement}`}
          </span>
          <span className="kpi-subtext">Group convergence status</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Top Influencer</span>
          <span className="kpi-value kpi-value--highlight">
            {sortedInfluence.length > 0 ? formatAgentName(sortedInfluence[0][0]) : "N/A"}
          </span>
          <span className="kpi-subtext">Highest peer stance sway</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Sentiment Records</span>
          <span className="kpi-value">{sentiment.length}</span>
          <span className="kpi-subtext">Evaluated messages</span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <nav className="analytics-nav">
        <button
          className={`nav-tab ${activeTab === "overview" ? "nav-tab--active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          Overview & Trajectory
        </button>
        <button
          className={`nav-tab ${activeTab === "agreement" ? "nav-tab--active" : ""}`}
          onClick={() => setActiveTab("agreement")}
        >
          Agreement Convergence
        </button>
        <button
          className={`nav-tab ${activeTab === "influence" ? "nav-tab--active" : ""}`}
          onClick={() => setActiveTab("influence")}
        >
          Influence Ranking
        </button>
        <button
          className={`nav-tab ${activeTab === "sentiment" ? "nav-tab--active" : ""}`}
          onClick={() => setActiveTab("sentiment")}
        >
          Sentiment & Stances
        </button>
        <button
          className={`nav-tab ${activeTab === "graph" ? "nav-tab--active" : ""}`}
          onClick={() => setActiveTab("graph")}
        >
          Interaction Graph
        </button>
      </nav>

      {/* Tab Content */}
      <main className="analytics-content">
        {/* TAB 1: OVERVIEW & OPINION TRAJECTORY */}
        {activeTab === "overview" && (
          <section className="analytics-section">
            <div className="section-header">
              <h3>Opinion Trajectory (Stance Evolution)</h3>
              <p>
                Traces how each agent’s stance shifted across discussion rounds on a scale from -1.0 (Critical) to +1.0 (Favorable).
              </p>
            </div>

            <div className="trajectory-list">
              {Object.entries(stances).length > 0 ? (
                Object.entries(stances).map(([agentId, points]) => {
                  const changeData = opinion_change[agentId] || {};
                  return (
                    <div key={agentId} className="agent-trajectory-card">
                      <div className="agent-trajectory-header">
                        <span className="agent-name">{formatAgentName(agentId)}</span>
                        <code className="agent-id-tag">{agentId}</code>
                      </div>

                      <div className="trajectory-timeline">
                        {points.map((pt) => {
                          const percent = Math.min(Math.max(((pt.stance + 1) / 2) * 100, 0), 100);
                          const polarityClass =
                            pt.stance > 0.2
                              ? "stance--positive"
                              : pt.stance < -0.2
                              ? "stance--negative"
                              : "stance--neutral";
                          return (
                            <div key={pt.round} className="trajectory-step">
                              <span className="step-round">Round {pt.round}</span>
                              <div className="step-bar-wrapper">
                                <div
                                  className={`step-bar ${polarityClass}`}
                                  style={{ width: `${percent}%` }}
                                ></div>
                              </div>
                              <span className={`step-value ${polarityClass}`}>
                                {pt.stance > 0 ? `+${pt.stance.toFixed(2)}` : pt.stance.toFixed(2)}
                              </span>
                            </div>
                          );
                        })}
                      </div>

                      {changeData.changes && changeData.changes.length > 0 && (
                        <div className="agent-deltas">
                          <span className="deltas-title">Round Shifts:</span>
                          {changeData.changes.map((c, idx) => (
                            <span
                              key={idx}
                              className={`delta-chip ${c.change > 0 ? "delta--up" : c.change < 0 ? "delta--down" : ""}`}
                            >
                              R{c.from_round}→R{c.to_round}: {c.change > 0 ? `+${c.change.toFixed(2)}` : c.change.toFixed(2)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <p className="empty-subtext">No trajectory stance series available.</p>
              )}
            </div>
          </section>
        )}

        {/* TAB 2: AGREEMENT CONVERGENCE */}
        {activeTab === "agreement" && (
          <section className="analytics-section">
            <div className="section-header">
              <h3>Group Agreement & Alignment</h3>
              <p>
                Measures how closely aligned all agents were during each round (0.00 = Complete Divergence, 1.00 = Consensus).
              </p>
            </div>

            <div className="agreement-cards">
              {agreement.map((item) => {
                const score = typeof item.score === "number" ? item.score : 0;
                const percent = Math.round(score * 100);
                return (
                  <div key={item.round_number} className="agreement-card">
                    <div className="agreement-card-header">
                      <h4>Round {item.round_number}</h4>
                      <span className="agent-count-badge">{item.num_agents || participants.length} Agents</span>
                    </div>

                    <div className="meter-wrapper">
                      <div className="meter-fill" style={{ width: `${percent}%` }}></div>
                    </div>

                    <div className="agreement-card-footer">
                      <span className="score-number">{(score).toFixed(3)}</span>
                      <span className="score-percent">({percent}% alignment)</span>
                    </div>
                    {item.reason && <p className="agreement-reason">{item.reason}</p>}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* TAB 3: INFLUENCE RANKING */}
        {activeTab === "influence" && (
          <section className="analytics-section">
            <div className="section-header">
              <h3>Agent Influence Rankings</h3>
              <p>
                Calculates which agents had the strongest sway on their peers’ stance changes over time.
              </p>
            </div>

            <div className="influence-table-wrapper">
              <table className="analytics-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Agent</th>
                    <th>Influence Score</th>
                    <th>Observations</th>
                    <th>Impact Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedInfluence.map(([agentId, info], index) => {
                    const score = typeof info.score === "number" ? info.score : 0;
                    return (
                      <tr key={agentId}>
                        <td>
                          <span className={`rank-badge rank-${index + 1}`}>#{index + 1}</span>
                        </td>
                        <td>
                          <strong>{formatAgentName(agentId)}</strong>
                          <div className="sub-id">{agentId}</div>
                        </td>
                        <td>
                          <span className="influence-metric">
                            {score > 0 ? `+${score.toFixed(3)}` : score.toFixed(3)}
                          </span>
                        </td>
                        <td>{info.num_observations || "N/A"}</td>
                        <td>
                          {score > 0.5 ? (
                            <span className="status-tag status-tag--high">High Persuasion</span>
                          ) : score > 0 ? (
                            <span className="status-tag status-tag--moderate">Moderate</span>
                          ) : (
                            <span className="status-tag status-tag--neutral">Counter-aligned / Neutral</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* TAB 4: SENTIMENT & ARGUMENTS */}
        {activeTab === "sentiment" && (
          <section className="analytics-section">
            <div className="section-header">
              <h3>Sentiment & Key Stance Arguments</h3>
              <p>Extracted argument stances, sentiment scores, and lexical polarity across rounds.</p>
            </div>

            <div className="sentiment-grid">
              {sentiment.map((item, index) => {
                const score = typeof item.score === "number" ? item.score : 0;
                const polarityClass =
                  score > 0.2 ? "sentiment--pos" : score < -0.2 ? "sentiment--neg" : "sentiment--neu";

                return (
                  <div key={item.message_id || index} className="sentiment-card">
                    <div className="sentiment-card-header">
                      <div>
                        <strong>{formatAgentName(item.agent)}</strong>
                        <span className="sentiment-round-tag">Round {item.round}</span>
                      </div>
                      <span className={`sentiment-score-badge ${polarityClass}`}>
                        {score > 0 ? `+${score.toFixed(2)}` : score.toFixed(2)}
                      </span>
                    </div>

                    {item.key_arguments && item.key_arguments.length > 0 && (
                      <div className="arguments-list">
                        <span className="arg-label">Key Arguments:</span>
                        <ul>
                          {item.key_arguments.map((arg, aIdx) => (
                            <li key={aIdx}>{arg}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* TAB 5: INTERACTION GRAPH */}
        {activeTab === "graph" && (
          <section className="analytics-section">
            <div className="section-header">
              <h3>Agent Interaction Topology Graph</h3>
              <p>Communication connections, routing topology, and peer messaging channels.</p>
            </div>

            <div className="graph-container">
              <div className="nodes-overview">
                <h4>Participating Network Nodes ({interaction_graph.nodes?.length || participants.length})</h4>
                <div className="nodes-chips">
                  {(interaction_graph.nodes || participants).map((node) => (
                    <div key={node} className="node-chip">
                      <span className="node-dot"></span>
                      <span>{formatAgentName(node)}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="edges-overview">
                <h4>Topology Edges & Message Routing</h4>
                <div className="edges-grid">
                  {interaction_graph.edges &&
                    Object.entries(interaction_graph.edges).map(([source, targets]) => (
                      <div key={source} className="edge-card">
                        <span className="edge-source">{formatAgentName(source)}</span>
                        <span className="edge-arrow">➔</span>
                        <div className="edge-targets">
                          {Array.isArray(targets) && targets.length > 0 ? (
                            targets.map((tgt) => (
                              <span key={tgt} className="edge-target-chip">
                                {formatAgentName(tgt)}
                              </span>
                            ))
                          ) : (
                            <span className="edge-target-none">All peers (broadcast)</span>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
